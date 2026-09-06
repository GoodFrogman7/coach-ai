"""
reference_library.py

Reference clip library: picks the professional clip to compare against for a
given stroke and handedness, and caches reference pose landmarks so the slow
MediaPipe pass over a reference clip runs once per clip.

Layout (see data/reference/manifest.yaml):

    data/reference/
        manifest.yaml
        backhand/djokovic_backhand.mp4
        backhand/cache/<sha256[:16]>_mp<mediapipe version>.landmarks.csv

Cache entries are keyed by the clip's content hash and the MediaPipe version,
so editing a clip or upgrading MediaPipe invalidates them automatically.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a hard requirement elsewhere
    yaml = None

REFERENCE_DIR = Path("data/reference")
MANIFEST_NAME = "manifest.yaml"
STROKES = ("backhand", "forehand", "serve", "volley", "overhead")


def load_manifest(reference_dir: Path = REFERENCE_DIR) -> List[Dict]:
    """Return the manifest's clip entries with absolute-ish paths resolved."""
    manifest_path = Path(reference_dir) / MANIFEST_NAME
    if yaml is None or not manifest_path.exists():
        return []
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    clips = []
    for entry in data.get("clips", []) or []:
        if not entry or "stroke" not in entry or "path" not in entry:
            continue
        clip = dict(entry)
        clip["stroke"] = str(clip["stroke"]).lower().strip()
        clip["handedness"] = str(clip.get("handedness", "right")).lower().strip()
        clip["path"] = str(Path(reference_dir) / clip["path"])
        clips.append(clip)
    return clips


def resolve_reference(stroke: str, handed: str = "right",
                      reference_dir: Path = REFERENCE_DIR) -> Optional[Dict]:
    """
    Pick the best available reference clip for a stroke.

    Preference order: same stroke and same handedness, then same stroke any
    handedness. Clips whose file is missing on disk are skipped. Returns the
    manifest entry (with 'path') or None when the library has nothing for the
    stroke, which tells the pipeline to use range comparison instead.
    """
    stroke = (stroke or "backhand").lower().strip()
    handed = (handed or "right").lower().strip()
    candidates = [c for c in load_manifest(reference_dir)
                  if c["stroke"] == stroke and Path(c["path"]).exists()]
    if not candidates:
        return None
    same_hand = [c for c in candidates if c["handedness"] == handed]
    return (same_hand or candidates)[0]


def available_strokes(reference_dir: Path = REFERENCE_DIR) -> List[str]:
    """Strokes that have at least one clip present on disk."""
    return sorted({c["stroke"] for c in load_manifest(reference_dir) if Path(c["path"]).exists()})


# ---------------------------------------------------------------------------
# Landmark cache
# ---------------------------------------------------------------------------

def _file_digest(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _mediapipe_version() -> str:
    try:
        import mediapipe
        return str(mediapipe.__version__)
    except Exception:  # pragma: no cover
        return "unknown"


def cache_path_for(video_path: str) -> Path:
    video = Path(video_path)
    return video.parent / "cache" / f"{_file_digest(video)}_mp{_mediapipe_version()}.landmarks.csv"


def cached_landmarks(video_path: str,
                     extract_fn: Callable[[str], pd.DataFrame],
                     use_cache: bool = True) -> pd.DataFrame:
    """
    Return pose landmarks for a reference clip, reading from the cache when a
    matching entry exists and writing one after a fresh extraction.

    Args:
        video_path: the clip.
        extract_fn: function(video_path) -> landmarks DataFrame (normally
            vision.extract_pose.extract_pose_landmarks). Injected so tests can
            count calls without running MediaPipe.
        use_cache: set False to force re-extraction (the cache is still written).
    """
    cache_file = cache_path_for(video_path)
    if use_cache and cache_file.exists():
        try:
            df = pd.read_csv(cache_file)
            if len(df) > 0:
                print(f"  -> Using cached reference landmarks: {cache_file.name}")
                return df
        except Exception as exc:  # corrupt cache: fall through and rebuild
            print(f"  [WARN] Ignoring unreadable landmark cache ({exc})")

    df = extract_fn(str(video_path))
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_file, index=False)
    except OSError as exc:
        print(f"  [WARN] Could not write landmark cache: {exc}")
    return df
