"""
kb_metadata.py

Knowledge-base document metadata: YAML-style front matter on kb/*.md files
and the stroke boost applied at retrieval time.

A knowledge-base file may start with:

    ---
    strokes: [forehand]
    ---

`strokes` lists the strokes the document is about. A file with no front
matter (or no `strokes` key) is general and applies to every stroke. The
front matter is stripped before chunking so it never appears in retrieved
text, and each chunk carries the document's `strokes` list.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

STROKES = ("backhand", "forehand", "serve", "volley", "overhead")
STROKE_BOOST = 1.25  # multiplier for chunks tagged with the session's stroke

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_front_matter(content: str) -> Tuple[Dict, str]:
    """
    Split optional front matter from a markdown document.

    Returns (metadata, body). Metadata is a plain dict; `strokes` is always a
    list of lowercase stroke names (possibly empty). Parsing is deliberately
    tiny (key: value and key: [a, b]) so it needs no YAML dependency.
    """
    match = _FRONT_MATTER.match(content)
    if not match:
        return {"strokes": []}, content

    meta: Dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"").lower() for v in value[1:-1].split(",")]
            meta[key] = [v for v in items if v]
        else:
            meta[key] = value.strip("'\"")

    strokes = meta.get("strokes", [])
    if isinstance(strokes, str):
        strokes = [strokes.lower()]
    meta["strokes"] = [s for s in strokes if s in STROKES]
    return meta, content[match.end():]


def applies_to_stroke(doc_strokes: Optional[List[str]], stroke: Optional[str]) -> bool:
    """General docs apply to everything; tagged docs only to their strokes."""
    if not doc_strokes or not stroke:
        return True
    return stroke.lower().strip() in doc_strokes


def boost_for_stroke(results: List[Dict], stroke: Optional[str]) -> List[Dict]:
    """
    Re-rank retrieval results for the session's stroke.

    Chunks tagged with the stroke get their score multiplied by STROKE_BOOST.
    Chunks tagged with a *different* stroke are dropped: a forehand session
    should not be coached from the serve fundamentals. Untagged chunks are
    unchanged. Returns a new list sorted by score, descending.
    """
    if not stroke:
        return results
    stroke = stroke.lower().strip()
    out = []
    for r in results:
        tags = r.get("strokes") or []
        if tags and stroke not in tags:
            continue
        r = dict(r)
        if tags:
            for key in ("score", "combined_score"):
                if key in r and r[key] is not None:
                    r[key] = float(r[key]) * STROKE_BOOST
            r["stroke_boosted"] = True
        out.append(r)
    out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return out
