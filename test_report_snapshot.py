"""
Backhand report snapshot.

Renders a full coaching report from fixed synthetic inputs and compares it,
byte for byte (minus the timestamp line), to tests/snapshots/backhand_report.md.
Any change to backhand wording, ordering, or scoring shows up here. Regenerate
deliberately with:

    python test_report_snapshot.py --update
"""
import sys
from pathlib import Path

import pytest

from vision.report import generate_report

SNAPSHOT = Path(__file__).parent / "tests" / "snapshots" / "backhand_report.md"

USER_METRICS = {
    "left_shoulder_angle": 48.0, "right_shoulder_angle": 62.0,
    "left_elbow_angle": 165.0, "right_elbow_angle": 128.0,
    "left_knee_angle": 172.0, "right_knee_angle": 168.0,
    "hip_rotation": -4.0, "spine_lean": 21.0, "stance_width_normalized": 1.6,
}
REF_METRICS = {
    "left_shoulder_angle": 55.0, "right_shoulder_angle": 58.0,
    "left_elbow_angle": 120.0, "right_elbow_angle": 135.0,
    "left_knee_angle": 150.0, "right_knee_angle": 152.0,
    "hip_rotation": -18.0, "spine_lean": 6.0, "stance_width_normalized": 2.4,
}
USER_PHASES = {"preparation": (0, 20), "load": (21, 40), "contact": (41, 50), "follow_through": (51, 80)}
REF_PHASES = {"preparation": (0, 24), "load": (25, 45), "contact": (46, 54), "follow_through": (55, 90)}


def _phase_metrics(base: dict, offsets: dict) -> dict:
    out = {}
    for phase, delta in offsets.items():
        out[phase] = {k: v + delta.get(k, 0.0) for k, v in base.items()}
    return out


USER_PHASE_METRICS = _phase_metrics(USER_METRICS, {
    "preparation": {"left_shoulder_angle": -30.0, "stance_width_normalized": -0.6},
    "load": {"hip_rotation": 2.0, "left_knee_angle": 4.0, "right_knee_angle": 4.0},
    "contact": {},
    "follow_through": {"left_elbow_angle": -40.0, "spine_lean": 8.0},
})
REF_PHASE_METRICS = _phase_metrics(REF_METRICS, {
    "preparation": {"left_shoulder_angle": 5.0},
    "load": {"hip_rotation": -6.0, "left_knee_angle": -8.0, "right_knee_angle": -8.0},
    "contact": {},
    "follow_through": {"left_elbow_angle": 10.0},
})


def render_backhand_report() -> str:
    report = generate_report(
        USER_METRICS, REF_METRICS, 45, 50,
        USER_PHASES, REF_PHASES, USER_PHASE_METRICS, REF_PHASE_METRICS,
        session_id="2026-01-01_10-00-00",
        ref_video="data/reference/backhand/djokovic_backhand.mp4",
        stroke_type="backhand",
        phase_weighted_score=58.3,
    )
    lines = [ln for ln in report.splitlines() if not ln.startswith("generated_at:")]
    return "\n".join(lines) + "\n"


def test_backhand_report_matches_snapshot():
    assert SNAPSHOT.exists(), f"missing snapshot {SNAPSHOT}; run: python test_report_snapshot.py --update"
    expected = SNAPSHOT.read_text(encoding="utf-8")
    actual = render_backhand_report()
    if actual != expected:
        import difflib
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), actual.splitlines(), "snapshot", "actual", lineterm="", n=2))
        pytest.fail("backhand report changed:\n" + diff[:6000])


if __name__ == "__main__":
    if "--update" in sys.argv:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_backhand_report())
        print(f"wrote {SNAPSHOT}")
    else:
        print(render_backhand_report())
