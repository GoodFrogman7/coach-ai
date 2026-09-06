"""Tests for range comparison (scoring against stroke profile ranges) and cue templates."""
import math

import numpy as np
import pandas as pd
import pytest

from vision.comparison import (
    STRATEGY_RANGE,
    build_range_phase_reference,
    build_range_reference,
    clamp_to_range,
    describe_strategy,
    expected_range,
    range_deviation,
)
from vision.cue_templates import BACKHAND, CUES, get_cue
from vision.features import compute_features_from_landmarks
from vision.similarity import compute_similarity_score, generate_coaching_cues, generate_drills


def test_expected_range_covers_profile_metrics_only():
    assert expected_range("left_elbow_angle", "backhand") == (90.0, 140.0)
    assert expected_range("hip_rotation", "serve") == (15.0, 60.0)
    assert expected_range("stance_width_normalized", "backhand") is None
    assert expected_range("left_shoulder_angle", "forehand") is None


def test_clamp_inside_range_is_identity_outside_is_nearest_edge():
    assert clamp_to_range("left_elbow_angle", 120.0, "backhand") == 120.0
    assert clamp_to_range("left_elbow_angle", 170.0, "backhand") == 140.0
    assert clamp_to_range("left_elbow_angle", 40.0, "backhand") == 40.0 + 50.0
    assert range_deviation("left_elbow_angle", 170.0, "backhand") == 30.0
    assert range_deviation("left_elbow_angle", 120.0, "backhand") == 0.0
    # Uncovered metrics never deviate.
    assert range_deviation("stance_width_normalized", 9.0, "backhand") == 0.0


def test_hip_rotation_clamps_magnitude_and_keeps_sign():
    # Backhand range is (5, 35) on |shoulder - hip|.
    assert clamp_to_range("hip_rotation", -2.0, "backhand") == -5.0
    assert clamp_to_range("hip_rotation", 50.0, "backhand") == 35.0
    assert clamp_to_range("hip_rotation", -20.0, "backhand") == -20.0
    assert range_deviation("hip_rotation", -2.0, "backhand") == 3.0


def test_nan_passes_through():
    assert math.isnan(clamp_to_range("left_elbow_angle", float("nan"), "backhand"))
    assert range_deviation("left_elbow_angle", float("nan"), "backhand") == 0.0


def test_inside_range_scores_100_outside_scores_lower():
    inside = {"left_elbow_angle": 120.0, "right_elbow_angle": 110.0,
              "left_knee_angle": 160.0, "right_knee_angle": 158.0,
              "hip_rotation": -15.0, "spine_lean": 5.0, "stance_width_normalized": 2.0,
              "left_shoulder_angle": 50.0, "right_shoulder_angle": 55.0}
    ref = build_range_reference(inside, "backhand")
    assert ref == inside
    assert compute_similarity_score(inside, ref) == 100.0

    outside = dict(inside, left_elbow_angle=175.0, spine_lean=40.0)
    ref = build_range_reference(outside, "backhand")
    assert ref["left_elbow_angle"] == 140.0 and ref["spine_lean"] == 15.0
    assert compute_similarity_score(outside, ref) < 100.0


def test_stroke_changes_range_outcome():
    metrics = {"left_elbow_angle": 150.0, "right_elbow_angle": 150.0,
               "left_knee_angle": 160.0, "right_knee_angle": 160.0,
               "hip_rotation": 12.0, "spine_lean": 5.0, "stance_width_normalized": 2.0}
    # 150 deg elbow is outside the backhand range (90-140) but inside the forehand's (100-160).
    assert range_deviation("left_elbow_angle", 150.0, "backhand") == 10.0
    assert range_deviation("left_elbow_angle", 150.0, "forehand") == 0.0
    backhand = compute_similarity_score(metrics, build_range_reference(metrics, "backhand"))
    forehand = compute_similarity_score(metrics, build_range_reference(metrics, "forehand"))
    assert forehand > backhand


def test_phase_reference_applies_per_phase():
    phases = {"load": {"left_elbow_angle": 170.0, "hip_rotation": 1.0},
              "contact": {"left_elbow_angle": 120.0, "hip_rotation": 20.0}}
    ref = build_range_phase_reference(phases, "backhand")
    assert ref["load"] == {"left_elbow_angle": 140.0, "hip_rotation": 5.0}
    assert ref["contact"] == phases["contact"]


def test_describe_strategy_mentions_stroke():
    text = describe_strategy(STRATEGY_RANGE, "serve")
    assert "serve" in text and "range" in text.lower()


# --------------------------------------------------------------------- cue templates

def test_every_stroke_falls_back_to_backhand_keys():
    for stroke, table in CUES.items():
        for key in table:
            assert key in BACKHAND, f"{stroke} defines unknown cue key {key}"
        for key in BACKHAND:
            assert get_cue(stroke, key), f"{stroke} has no wording for {key}"
    assert get_cue("cartwheel", "load.hip") == BACKHAND["load.hip"]


def test_cues_and_drills_change_wording_by_stroke():
    user = {"left_elbow_angle": 170.0, "right_elbow_angle": 100.0,
            "left_knee_angle": 175.0, "right_knee_angle": 175.0,
            "hip_rotation": -1.0, "spine_lean": 30.0, "stance_width_normalized": 1.0}
    ref = {"left_elbow_angle": 120.0, "right_elbow_angle": 135.0,
           "left_knee_angle": 150.0, "right_knee_angle": 150.0,
           "hip_rotation": -18.0, "spine_lean": 6.0, "stance_width_normalized": 2.4}
    _, backhand_cues, _ = generate_coaching_cues(user, ref)
    _, serve_cues, _ = generate_coaching_cues(user, ref, stroke="serve")
    assert backhand_cues != serve_cues
    assert any("trophy" in c.lower() for c in serve_cues)
    assert generate_drills(user, ref) != generate_drills(user, ref, stroke="serve")
    # Default argument keeps the backhand wording exactly.
    assert generate_coaching_cues(user, ref) == generate_coaching_cues(user, ref, stroke="backhand")


# --------------------------------------------------------------------- hip rotation wrap

def _two_line_pose(shoulder_deg: float, hip_deg: float) -> pd.DataFrame:
    """Shoulders and hips as lines at the given angles; other joints fixed."""
    def endpoints(deg, cy):
        r = np.radians(deg)
        return (0.5 - 0.1 * np.cos(r), cy - 0.1 * np.sin(r)), (0.5 + 0.1 * np.cos(r), cy + 0.1 * np.sin(r))
    (lsx, lsy), (rsx, rsy) = endpoints(shoulder_deg, 0.3)
    (lhx, lhy), (rhx, rhy) = endpoints(hip_deg, 0.6)
    coords = {11: (lsx, lsy), 12: (rsx, rsy), 13: (0.3, 0.45), 14: (0.7, 0.45),
              15: (0.25, 0.6), 16: (0.75, 0.6), 23: (lhx, lhy), 24: (rhx, rhy),
              25: (0.45, 0.8), 26: (0.55, 0.8), 27: (0.45, 0.95), 28: (0.55, 0.95)}
    return pd.DataFrame([{"frame": 0, "landmark_id": k, "x": x, "y": y, "z": 0.0, "visibility": 1.0}
                         for k, (x, y) in coords.items()])


def test_hip_rotation_is_wrapped_across_the_seam():
    # Shoulder line at +179 deg and hip line at -179 deg differ by 2 deg physically.
    val = compute_features_from_landmarks(_two_line_pose(179.0, -179.0)).iloc[0].hip_rotation
    assert abs(val) == pytest.approx(2.0, abs=1e-6)
    # A plain 10 degree separation is reported as 10.
    val = compute_features_from_landmarks(_two_line_pose(10.0, 0.0)).iloc[0].hip_rotation
    assert abs(val) == pytest.approx(10.0, abs=1e-6)
