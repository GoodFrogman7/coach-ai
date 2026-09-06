"""
comparison.py

Two ways to score a stroke.

ReferenceComparison (the original behaviour): the user's metrics are compared
frame-for-frame against a professional reference clip. Used whenever the
reference library has a clip for the stroke, or the caller passes one.

RangeComparison: used when no reference clip exists for the stroke. Each metric
is compared against the stroke profile's expected range (vision/stroke_profiles).
Deviation is the distance outside the range and zero inside it. Rather than
teach every downstream consumer (scoring, cues, ML similarity, the report) a
second code path, the strategy builds a *synthetic reference*: the user's own
metrics clamped into the expected ranges. A metric inside its range compares
against itself (deviation 0, similarity 100); a metric outside compares against
the nearest range edge, which is exactly the distance-outside-range definition.
Metrics with no profile range (shoulder angles, stance width) pass through
unchanged and therefore never generate deviation in range mode.

Hip rotation is signed (shoulder line minus hip line); the profile ranges are
on its magnitude, so clamping preserves the sign.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from vision.stroke_profiles import STROKE_PROFILES, get_stroke_aware_threshold

STRATEGY_REFERENCE = "reference"
STRATEGY_RANGE = "range"

# Metrics the profile ranges cover, mapped through get_stroke_aware_threshold.
RANGE_METRICS = (
    "left_elbow_angle", "right_elbow_angle",
    "left_knee_angle", "right_knee_angle",
    "hip_rotation", "spine_lean",
)
SIGNED_MAGNITUDE_METRICS = ("hip_rotation",)


def expected_range(metric: str, stroke: str) -> Optional[Tuple[float, float]]:
    """(low, high) for a metric under a stroke profile, or None if uncovered."""
    if metric not in RANGE_METRICS:
        return None
    rng = get_stroke_aware_threshold(metric, stroke, "expected_range")
    if not rng or len(rng) != 2:
        return None
    lo, hi = float(rng[0]), float(rng[1])
    return (min(lo, hi), max(lo, hi))


def clamp_to_range(metric: str, value: float, stroke: str) -> float:
    """The user's value pulled to the nearest edge of its expected range."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return value
    rng = expected_range(metric, stroke)
    if rng is None:
        return value
    lo, hi = rng
    if metric in SIGNED_MAGNITUDE_METRICS:
        sign = -1.0 if value < 0 else 1.0
        return sign * min(max(abs(value), lo), hi)
    return min(max(float(value), lo), hi)


def range_deviation(metric: str, value: float, stroke: str) -> float:
    """Distance outside the expected range (0 when inside or uncovered)."""
    clamped = clamp_to_range(metric, value, stroke)
    if clamped is None or value is None:
        return 0.0
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    return abs(float(value) - float(clamped))


def build_range_reference(user_metrics: Dict[str, float], stroke: str) -> Dict[str, float]:
    """Synthetic reference metrics: the user's metrics clamped into the stroke's ranges."""
    return {k: clamp_to_range(k, v, stroke) for k, v in user_metrics.items()}


def build_range_phase_reference(user_phase_metrics: Dict[str, Dict[str, float]],
                                stroke: str) -> Dict[str, Dict[str, float]]:
    """Per-phase synthetic reference (same clamp applied within every phase)."""
    return {phase: build_range_reference(metrics, stroke)
            for phase, metrics in (user_phase_metrics or {}).items()}


def describe_strategy(strategy: str, stroke: str, reference_player: str = None) -> str:
    """One sentence for the report explaining what the numbers are compared against."""
    if strategy == STRATEGY_RANGE:
        name = STROKE_PROFILES.get(stroke, STROKE_PROFILES["backhand"])["name"]
        return (f"No professional {name.lower()} clip is in the reference library, so your "
                f"metrics are compared against the expected biomechanical ranges for a {name.lower()}. "
                "A metric inside its range scores 100; outside, the score falls with the distance "
                "beyond the nearest edge.")
    who = reference_player or "a professional reference"
    return f"Your metrics are compared frame-for-frame against {who}."
