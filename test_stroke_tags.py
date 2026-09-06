"""Tests for stroke tags on knowledge-base docs, retrieval boosting, and drill filtering."""
from pathlib import Path

from rag.kb_metadata import applies_to_stroke, boost_for_stroke, parse_front_matter
from rag.index_kb import load_markdown_files
from vision.drills import (
    drills_for_stroke,
    generate_adaptive_drill_recommendations,
    get_drill_knowledge_base,
)

KB = Path(__file__).parent / "kb"


def test_front_matter_parsed_and_stripped():
    meta, body = parse_front_matter("---\nstrokes: [Forehand, serve]\n---\n# Title\n\ntext\n")
    assert meta["strokes"] == ["forehand", "serve"]
    assert body.startswith("# Title")


def test_no_front_matter_means_general():
    meta, body = parse_front_matter("# Title\n\ntext\n")
    assert meta["strokes"] == []
    assert body.startswith("# Title")
    assert applies_to_stroke([], "serve")
    assert applies_to_stroke(["serve"], "serve")
    assert not applies_to_stroke(["serve"], "forehand")


def test_repo_kb_tags_load_into_documents():
    docs = {d["filename"]: d for d in load_markdown_files(str(KB))}
    assert docs["forehand_fundamentals.md"]["strokes"] == ["forehand"]
    assert docs["serve_fundamentals.md"]["strokes"] == ["serve"]
    assert docs["footwork_fundamentals.md"]["strokes"] == []
    # Front matter never leaks into indexed text.
    assert not docs["forehand_fundamentals.md"]["content"].startswith("---")


def test_boost_promotes_matching_and_drops_other_strokes():
    results = [
        {"filename": "serve.md", "strokes": ["serve"], "score": 0.50},
        {"filename": "general.md", "strokes": [], "score": 0.45},
        {"filename": "forehand.md", "strokes": ["forehand"], "score": 0.40},
    ]
    boosted = boost_for_stroke(results, "forehand")
    names = [r["filename"] for r in boosted]
    assert "serve.md" not in names
    assert names[0] == "forehand.md"          # 0.40 * 1.25 = 0.50 > 0.45
    assert boosted[0]["stroke_boosted"] is True
    assert boost_for_stroke(results, None) == results


def test_drills_for_stroke_filters_tagged_drills():
    drills = [
        {"name": "generic"},
        {"name": "bh-only", "strokes": ["backhand"]},
        {"name": "net", "strokes": ["volley", "overhead"]},
    ]
    assert [d["name"] for d in drills_for_stroke(drills, "backhand")] == ["generic", "bh-only"]
    assert [d["name"] for d in drills_for_stroke(drills, "volley")] == ["generic", "net"]
    assert [d["name"] for d in drills_for_stroke(drills, None)] == ["generic", "bh-only", "net"]


def test_adaptive_drills_respect_stroke():
    kb = get_drill_knowledge_base()
    tagged = [d["name"] for cat in kb.values() for d in cat["drills"] if d.get("strokes")]
    assert tagged, "expected at least one stroke-tagged drill in the knowledge base"

    focus = {
        "critical": [{"metric": "left_knee_angle", "phase": "load", "deviation": 25.0,
                      "reliability": "High", "priority_score": 90.0}],
        "priority": [], "monitor": [], "suppressed": [],
    }
    backhand = generate_adaptive_drill_recommendations(focus, stroke="backhand")
    serve = generate_adaptive_drill_recommendations(focus, stroke="serve")
    assert backhand["critical_drills"][0]["drill_name"] == "Split-Step to Stance Drill"
    assert serve["critical_drills"][0]["drill_name"] != "Split-Step to Stance Drill"
