"""Tests for stroke-aware phase weighting in the scoring pipeline."""
from vision.compare import (
    get_stroke_phase_weights,
    compute_phase_weighted_score,
    compute_ml_overall_similarity,
)

CONFIG_DEFAULT = {"preparation": 0.15, "load": 0.25, "contact": 0.35, "follow_through": 0.25}


def test_backhand_weights_match_config_default():
    # Backward compatibility: backhand keeps the exact config-default weights,
    # so a backhand run scores identically to before this change.
    assert get_stroke_phase_weights("backhand") == CONFIG_DEFAULT


def test_strokes_have_distinct_weights():
    backhand = get_stroke_phase_weights("backhand")
    serve = get_stroke_phase_weights("serve")
    volley = get_stroke_phase_weights("volley")
    assert serve != backhand
    assert volley != backhand
    # Serve/volley emphasize contact more than a backhand does.
    assert serve["contact"] > backhand["contact"]
    assert volley["contact"] > backhand["contact"]
    for weights in (backhand, serve, volley):
        assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_unknown_stroke_falls_back_to_backhand():
    assert get_stroke_phase_weights("cartwheel") == get_stroke_phase_weights("backhand")


def test_explicit_phase_weights_override_config():
    phase_scores = {"preparation": 90, "load": 80, "contact": 60, "follow_through": 70}
    contact_only = {"preparation": 0.0, "load": 0.0, "contact": 1.0, "follow_through": 0.0}
    # All weight on contact -> the score equals the contact phase score.
    assert compute_phase_weighted_score(phase_scores, phase_weights=contact_only) == 60.0


def test_stroke_changes_the_weighted_score():
    # Identical phase performance, different stroke -> different overall score.
    # Contact is the weak phase here; serve weights contact more, so serve scores lower.
    phase_scores = {"preparation": 95, "load": 90, "contact": 40, "follow_through": 80}
    backhand = compute_phase_weighted_score(
        phase_scores, phase_weights=get_stroke_phase_weights("backhand")
    )
    serve = compute_phase_weighted_score(
        phase_scores, phase_weights=get_stroke_phase_weights("serve")
    )
    assert serve < backhand
    # And backhand-via-explicit-weights equals backhand-via-config (no config passed).
    assert backhand == compute_phase_weighted_score(phase_scores)


def test_ml_overall_respects_stroke_weights():
    ml_phase = {"preparation": 95.0, "load": 90.0, "contact": 40.0, "follow_through": 80.0}
    backhand = compute_ml_overall_similarity(
        ml_phase, phase_weights=get_stroke_phase_weights("backhand")
    )
    serve = compute_ml_overall_similarity(
        ml_phase, phase_weights=get_stroke_phase_weights("serve")
    )
    assert serve < backhand
