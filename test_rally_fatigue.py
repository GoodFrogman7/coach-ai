#!/usr/bin/env python3
"""
Test script for Rally & Fatigue Intelligence (Phase 2.3)
"""

import sys
import io

# Fix Windows UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'vision')

from compare import (
    segment_session_into_rallies,
    compute_metric_trajectory,
    infer_fatigue_from_biomechanics,
    classify_issue_with_fatigue_context
)

print("="*80)
print("Rally & Fatigue Intelligence - Test Suite")
print("="*80)

# Test 1: Rally Segmentation
print("\n[Test 1] Rally Segmentation")
print("-"*80)

# Simulate timestamps (seconds): 3 rallies with gaps
timestamps = [
    0.5, 1.0, 1.5, 2.0,  # Rally 1 (4 strokes)
    15.0, 15.5, 16.0,     # Rally 2 (3 strokes, 13s gap)
    30.0, 30.5, 31.0, 31.5, 32.0  # Rally 3 (5 strokes, 14s gap)
]

rallies = segment_session_into_rallies(timestamps, inter_rally_gap_seconds=10.0)

print(f"Timestamps: {timestamps}")
print(f"Detected {len(rallies)} rallies:")
for i, rally in enumerate(rallies, 1):
    print(f"  Rally {i}: strokes {rally['start_idx']}-{rally['end_idx']} "
          f"({rally['stroke_count']} strokes, {rally['duration']:.1f}s duration)")

assert len(rallies) == 3, "Should detect 3 rallies"
print("✅ Rally segmentation works correctly")

# Test 2: Metric Trajectory (No Fatigue)
print("\n[Test 2] Metric Trajectory - Stable Performance")
print("-"*80)

stable_values = [180, 178, 182, 179, 181]  # Consistent hip rotation
trajectory = compute_metric_trajectory(stable_values)

print(f"Hip rotation values: {stable_values}")
print(f"  Trend: {trajectory['trend']:.2f}")
print(f"  Variability: {trajectory['variability']:.1f}%")
print(f"  Early mean: {trajectory['early_mean']:.1f}°")
print(f"  Late mean: {trajectory['late_mean']:.1f}°")
print(f"  Degradation ratio: {trajectory['degradation_ratio']:.3f}")

assert abs(trajectory['trend']) < 2.0, "Trend should be near zero for stable performance"
assert trajectory['variability'] < 5.0, "Variability should be low"
print("✅ Stable trajectory detected correctly")

# Test 3: Metric Trajectory (Fatigue Pattern)
print("\n[Test 3] Metric Trajectory - Fatigue Pattern")
print("-"*80)

degrading_values = [180, 175, 170, 165, 160, 155]  # Degrading hip rotation
trajectory = compute_metric_trajectory(degrading_values)

print(f"Hip rotation values: {degrading_values}")
print(f"  Trend: {trajectory['trend']:.2f} (negative = degrading)")
print(f"  Variability: {trajectory['variability']:.1f}%")
print(f"  Early mean: {trajectory['early_mean']:.1f}°")
print(f"  Late mean: {trajectory['late_mean']:.1f}°")
print(f"  Degradation ratio: {trajectory['degradation_ratio']:.3f} (< 1.0 = decline)")

assert trajectory['trend'] < -3.0, "Trend should be negative for degrading performance"
assert trajectory['degradation_ratio'] < 0.95, "Degradation ratio should indicate decline"
print("✅ Fatigue pattern detected correctly")

# Test 4: Fatigue Inference (No Fatigue)
print("\n[Test 4] Fatigue Inference - No Fatigue Signals")
print("-"*80)

no_fatigue_metrics = {
    'recovery_time': [0.7, 0.7, 0.7, 0.7, 0.7],  # Stable
    'hip_rotation': [180, 178, 182, 179, 181],   # Stable
    'balance_drift': [5, 5, 5, 5, 5]             # Stable
}

fatigue_result = infer_fatigue_from_biomechanics(no_fatigue_metrics)

print(f"Fatigue score: {fatigue_result['fatigue_score']:.1f}/100")
print(f"Confidence: {fatigue_result['confidence']}")
print(f"Signals detected: {len(fatigue_result['fatigue_signals'])}")
print(f"Recommendation: {fatigue_result['recommendation']}")

assert fatigue_result['fatigue_score'] < 30, "Should have low fatigue score"
assert fatigue_result['confidence'] in ['low', 'insufficient_data'], "Low confidence expected"
print("✅ No false fatigue detection")

# Test 5: Fatigue Inference (Strong Fatigue)
print("\n[Test 5] Fatigue Inference - Strong Fatigue Signals")
print("-"*80)

strong_fatigue_metrics = {
    'recovery_time': [0.7, 0.8, 0.9, 1.0, 1.1, 1.2],  # Increasing (fatigue)
    'hip_rotation': [180, 175, 170, 165, 160, 155],   # Decreasing (fatigue)
    'balance_drift': [5, 6, 8, 10, 12, 15]            # Increasing (fatigue)
}

fatigue_result = infer_fatigue_from_biomechanics(strong_fatigue_metrics)

print(f"Fatigue score: {fatigue_result['fatigue_score']:.1f}/100")
print(f"Confidence: {fatigue_result['confidence']}")
print(f"Signals detected: {len(fatigue_result['fatigue_signals'])}")
print(f"Affected metrics: {', '.join(fatigue_result['affected_metrics'])}")
print(f"Recommendation: {fatigue_result['recommendation']}")

if fatigue_result['fatigue_signals']:
    print("\nFatigue patterns:")
    for signal in fatigue_result['fatigue_signals']:
        print(f"  • {signal}")

assert fatigue_result['fatigue_score'] > 50, "Should have high fatigue score"
assert fatigue_result['confidence'] in ['high', 'medium'], "High confidence expected"
assert len(fatigue_result['fatigue_signals']) >= 2, "Multiple signals expected"
print("✅ Strong fatigue detected correctly")

# Test 6: Issue Classification with Fatigue Context
print("\n[Test 6] Issue Classification with Fatigue Context")
print("-"*80)

# Scenario: Recovery time issue that's fatigue-driven
fatigue_inference = {
    'fatigue_score': 75,
    'affected_metrics': ['recovery_time', 'hip_rotation'],
    'confidence': 'high',
    'recommendation': 'CONDITIONING_FOCUS'
}

classification = classify_issue_with_fatigue_context(
    metric_name='recovery_time',
    current_deviation=0.3,
    reliability_level='High',
    phase_stability=80.0,
    progress_delta=None,
    fatigue_inference=fatigue_inference
)

print("Metric: recovery_time")
print(f"Classification: {classification['classification']}")
print(f"Fatigue flag: {classification['fatigue_flag']}")
print(f"Intervention type: {classification['intervention_type']}")
print(f"Recommendation: {classification['recommendation'][:80]}...")

assert classification['fatigue_flag'] == True, "Should flag as fatigue-driven"
assert classification['intervention_type'] == 'conditioning', "Should recommend conditioning"
assert 'FATIGUE' in classification['recommendation'], "Should mention fatigue in recommendation"
print("✅ Fatigue-aware classification works correctly")

# Test 7: Graceful Degradation (Sparse Data)
print("\n[Test 7] Graceful Degradation - Sparse Data")
print("-"*80)

sparse_metrics = {
    'recovery_time': [0.7, 0.8],  # Only 2 data points
}

fatigue_result = infer_fatigue_from_biomechanics(sparse_metrics)

print("Data points: 2")
print(f"Fatigue score: {fatigue_result['fatigue_score']:.1f}/100")
print(f"Confidence: {fatigue_result['confidence']}")

assert fatigue_result['confidence'] == 'insufficient_data', "Should indicate insufficient data"
print("✅ Graceful handling of sparse data")

# Test 8: Graceful Degradation (No Rally Data)
print("\n[Test 8] Graceful Degradation - No Rally Data")
print("-"*80)

empty_timestamps = []
rallies = segment_session_into_rallies(empty_timestamps)

print(f"Empty timestamps: {empty_timestamps}")
print(f"Rallies detected: {len(rallies)}")

assert len(rallies) == 0, "Should return empty list for no data"
print("✅ Graceful handling of no rally data")

# Summary
print("\n" + "="*80)
print("✅ All Rally & Fatigue Intelligence tests passed!")
print("="*80)
print("\nKey Capabilities Validated:")
print("  ✓ Rally segmentation from timestamps")
print("  ✓ Metric trajectory analysis")
print("  ✓ Fatigue pattern detection")
print("  ✓ Fatigue-aware issue classification")
print("  ✓ Graceful degradation with sparse/missing data")
print("  ✓ No false positives for stable performance")
print("\n💡 Fatigue intelligence ready for integration!")

