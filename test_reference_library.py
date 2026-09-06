"""Tests for the reference clip library, landmark cache, and handedness mirroring."""
import numpy as np
import pandas as pd
import pytest

from vision.reference_library import (
    available_strokes,
    cache_path_for,
    cached_landmarks,
    load_manifest,
    resolve_reference,
)
from vision.handedness import mirror_landmarks, needs_mirroring, normalize_handedness
from vision.features import compute_features_from_landmarks


@pytest.fixture()
def library(tmp_path):
    """A reference dir with two backhand clips (right + left) and no forehand."""
    ref = tmp_path / "reference"
    (ref / "backhand").mkdir(parents=True)
    (ref / "backhand" / "righty.mp4").write_bytes(b"fake-video-right")
    (ref / "backhand" / "lefty.mp4").write_bytes(b"fake-video-left")
    (ref / "manifest.yaml").write_text(
        "clips:\n"
        "  - {stroke: backhand, path: backhand/righty.mp4, player: R, handedness: right}\n"
        "  - {stroke: backhand, path: backhand/lefty.mp4, player: L, handedness: left}\n"
        "  - {stroke: serve, path: serve/missing.mp4, player: S, handedness: right}\n",
        encoding="utf-8",
    )
    return ref


def test_manifest_loads_and_resolves_paths(library):
    clips = load_manifest(library)
    assert [c["stroke"] for c in clips] == ["backhand", "backhand", "serve"]
    assert clips[0]["path"].endswith("righty.mp4")


def test_resolve_prefers_same_handedness(library):
    assert resolve_reference("backhand", "right", library)["player"] == "R"
    assert resolve_reference("backhand", "left", library)["player"] == "L"


def test_resolve_falls_back_to_other_hand_then_none(library):
    # Remove the lefty clip: a left-handed request still gets the righty clip.
    (library / "backhand" / "lefty.mp4").unlink()
    assert resolve_reference("backhand", "left", library)["player"] == "R"
    # Serve is listed but the file is missing, forehand is not listed at all.
    assert resolve_reference("serve", "right", library) is None
    assert resolve_reference("forehand", "right", library) is None
    assert available_strokes(library) == ["backhand"]


def test_repo_manifest_has_the_backhand_clip():
    clips = load_manifest()
    assert any(c["stroke"] == "backhand" for c in clips)


def test_cache_hit_skips_extraction(library):
    clip = library / "backhand" / "righty.mp4"
    calls = []

    def fake_extract(path):
        calls.append(path)
        return pd.DataFrame({"frame": [0, 0], "landmark_id": [11, 12],
                             "x": [0.4, 0.6], "y": [0.5, 0.5], "z": [0, 0], "visibility": [1, 1]})

    first = cached_landmarks(str(clip), fake_extract)
    second = cached_landmarks(str(clip), fake_extract)
    assert len(calls) == 1
    assert cache_path_for(str(clip)).exists()
    pd.testing.assert_frame_equal(first, second, check_dtype=False)

    # Changing the clip's bytes changes the key, so extraction runs again.
    clip.write_bytes(b"fake-video-right-v2")
    cached_landmarks(str(clip), fake_extract)
    assert len(calls) == 2


def _synthetic_frame(frame: int = 0) -> pd.DataFrame:
    """A plausible standing pose for the 12 landmarks features.py uses."""
    coords = {
        11: (0.40, 0.30), 12: (0.60, 0.31),   # shoulders
        13: (0.35, 0.45), 14: (0.70, 0.42),   # elbows
        15: (0.30, 0.58), 16: (0.78, 0.50),   # wrists
        23: (0.44, 0.60), 24: (0.56, 0.60),   # hips
        25: (0.43, 0.78), 26: (0.58, 0.77),   # knees
        27: (0.42, 0.95), 28: (0.60, 0.95),   # ankles
    }
    rows = [{"frame": frame, "landmark_id": k, "x": x, "y": y, "z": 0.0, "visibility": 1.0}
            for k, (x, y) in coords.items()]
    return pd.DataFrame(rows)


def test_mirror_swaps_sides_and_flips_x():
    df = _synthetic_frame()
    mirrored = mirror_landmarks(df)
    left_wrist = mirrored[mirrored.landmark_id == 15].iloc[0]
    right_wrist_orig = df[df.landmark_id == 16].iloc[0]
    assert left_wrist.x == pytest.approx(1.0 - right_wrist_orig.x)
    assert left_wrist.y == pytest.approx(right_wrist_orig.y)
    # Mirroring twice is the identity.
    pd.testing.assert_frame_equal(mirror_landmarks(mirrored), df.sort_values(["frame", "landmark_id"]).reset_index(drop=True))


def test_mirror_swaps_features_and_flips_rotation_sign():
    df = pd.concat([_synthetic_frame(0), _synthetic_frame(1)], ignore_index=True)
    orig = compute_features_from_landmarks(df).iloc[0]
    mir = compute_features_from_landmarks(mirror_landmarks(df)).iloc[0]
    assert mir.left_elbow_angle == pytest.approx(orig.right_elbow_angle, abs=1e-6)
    assert mir.right_knee_angle == pytest.approx(orig.left_knee_angle, abs=1e-6)
    assert mir.stance_width_normalized == pytest.approx(orig.stance_width_normalized, abs=1e-6)
    # Shoulder/hip separation flips sign under a mirror, magnitude is preserved.
    assert abs(mir.hip_rotation) == pytest.approx(abs(orig.hip_rotation), abs=1e-6)
    assert np.sign(mir.hip_rotation) == -np.sign(orig.hip_rotation)


def test_handedness_helpers():
    assert normalize_handedness("Left ") == "left"
    assert normalize_handedness("ambidextrous") == "right"
    assert needs_mirroring("left", "right")
    assert not needs_mirroring("right", "right")
