"""
Test script for Player Baseline & Personalization (Phase 5.1)

This script validates:
1. Historical session loading
2. Baseline computation from historical data
3. Relative comparison (current vs baseline)
4. Graceful degradation with insufficient data
5. Metric aggregation and statistical computations
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
from vision.compare import (
    compute_player_baseline,
    compare_to_baseline
)


def test_baseline_computation():
    """Test baseline computation from historical sessions."""
    print("=" * 60)
    print("TEST 1: Baseline Computation")
    print("=" * 60)
    
    # Mock historical sessions
    historical_sessions = [
        {
            'session_id': '2025-12-25_10-00-00',
            'technique_score': 75.0,
            'readiness_score': 70.0,
            'metrics': {'elbow_angle': 150.0, 'hip_rotation': 45.0}
        },
        {
            'session_id': '2025-12-26_10-00-00',
            'technique_score': 78.0,
            'readiness_score': 72.0,
            'metrics': {'elbow_angle': 152.0, 'hip_rotation': 47.0}
        },
        {
            'session_id': '2025-12-27_10-00-00',
            'technique_score': 76.0,
            'readiness_score': 71.0,
            'metrics': {'elbow_angle': 151.0, 'hip_rotation': 46.0}
        }
    ]
    
    baseline = compute_player_baseline(historical_sessions, min_sessions=3)
    
    print(f"\nHas Baseline: {baseline['has_baseline']}")
    print(f"Session Count: {baseline['session_count']}")
    print(f"Baseline Technique: {baseline['baseline_technique_score']}")
    print(f"Baseline Readiness: {baseline['baseline_readiness_score']}")
    
    if baseline['baseline_metrics']:
        print("\nBaseline Metrics:")
        for metric, stats in baseline['baseline_metrics'].items():
            print(f"  {metric}: mean={stats['mean']:.1f}, std={stats['std']:.1f}")
    
    assert baseline['has_baseline'] == True, "Should have baseline with 3 sessions"
    assert baseline['session_count'] == 3
    assert 75.0 < baseline['baseline_technique_score'] < 78.0, "Baseline should be in range"
    assert 70.0 < baseline['baseline_readiness_score'] < 72.0, "Baseline should be in range"
    
    # Check metric aggregation
    assert 'elbow_angle' in baseline['baseline_metrics']
    assert baseline['baseline_metrics']['elbow_angle']['sample_size'] == 3
    
    print("\n✓ Test passed!\n")


def test_insufficient_data():
    """Test graceful degradation with insufficient historical data."""
    print("=" * 60)
    print("TEST 2: Insufficient Data (Graceful Degradation)")
    print("=" * 60)
    
    # Only 2 sessions (need 3)
    historical_sessions = [
        {
            'session_id': '2025-12-25_10-00-00',
            'technique_score': 75.0,
            'readiness_score': 70.0,
            'metrics': {}
        },
        {
            'session_id': '2025-12-26_10-00-00',
            'technique_score': 78.0,
            'readiness_score': 72.0,
            'metrics': {}
        }
    ]
    
    baseline = compute_player_baseline(historical_sessions, min_sessions=3)
    
    print(f"\nHas Baseline: {baseline['has_baseline']}")
    print(f"Reason: {baseline.get('reason', 'N/A')}")
    
    assert baseline['has_baseline'] == False, "Should not have baseline with insufficient data"
    assert 'reason' in baseline
    
    print("\n✓ Test passed!\n")


def test_comparison_above_baseline():
    """Test comparison when current value is above baseline."""
    print("=" * 60)
    print("TEST 3: Comparison Above Baseline")
    print("=" * 60)
    
    comparison = compare_to_baseline(
        current_value=85.0,
        baseline_value=75.0,
        metric_name='Technique score'
    )
    
    print(f"\nDelta Absolute: {comparison['delta_absolute']}")
    print(f"Delta Percent: {comparison['delta_percent']}%")
    print(f"Direction: {comparison['delta_direction']}")
    print(f"Interpretation: {comparison['interpretation']}")
    
    assert comparison['delta_absolute'] == 10.0
    assert abs(comparison['delta_percent'] - 13.3) < 0.1  # ~13.3%
    assert comparison['delta_direction'] == 'above'
    assert 'above baseline' in comparison['interpretation']
    
    print("\n✓ Test passed!\n")


def test_comparison_below_baseline():
    """Test comparison when current value is below baseline."""
    print("=" * 60)
    print("TEST 4: Comparison Below Baseline")
    print("=" * 60)
    
    comparison = compare_to_baseline(
        current_value=65.0,
        baseline_value=75.0,
        metric_name='Technique score'
    )
    
    print(f"\nDelta Absolute: {comparison['delta_absolute']}")
    print(f"Delta Percent: {comparison['delta_percent']}%")
    print(f"Direction: {comparison['delta_direction']}")
    print(f"Interpretation: {comparison['interpretation']}")
    
    assert comparison['delta_absolute'] == -10.0
    assert abs(comparison['delta_percent'] - (-13.3)) < 0.1  # ~-13.3%
    assert comparison['delta_direction'] == 'below'
    assert 'below baseline' in comparison['interpretation']
    
    print("\n✓ Test passed!\n")


def test_comparison_stable():
    """Test comparison when current value is stable (within 5%)."""
    print("=" * 60)
    print("TEST 5: Comparison Stable (within 5%)")
    print("=" * 60)
    
    comparison = compare_to_baseline(
        current_value=77.0,
        baseline_value=75.0,
        metric_name='Technique score'
    )
    
    print(f"\nDelta Absolute: {comparison['delta_absolute']}")
    print(f"Delta Percent: {comparison['delta_percent']}%")
    print(f"Direction: {comparison['delta_direction']}")
    print(f"Interpretation: {comparison['interpretation']}")
    
    assert comparison['delta_absolute'] == 2.0
    assert abs(comparison['delta_percent'] - 2.7) < 0.1  # ~2.7%
    assert comparison['delta_direction'] == 'stable'
    assert 'stable' in comparison['interpretation']
    
    print("\n✓ Test passed!\n")


def test_baseline_with_missing_data():
    """Test baseline computation with some sessions missing certain data."""
    print("=" * 60)
    print("TEST 6: Baseline with Missing Data")
    print("=" * 60)
    
    historical_sessions = [
        {
            'session_id': '2025-12-25_10-00-00',
            'technique_score': 75.0,
            'readiness_score': None,  # Missing
            'metrics': {'elbow_angle': 150.0}
        },
        {
            'session_id': '2025-12-26_10-00-00',
            'technique_score': 78.0,
            'readiness_score': 72.0,
            'metrics': {'elbow_angle': 152.0}
        },
        {
            'session_id': '2025-12-27_10-00-00',
            'technique_score': None,  # Missing
            'readiness_score': 71.0,
            'metrics': {'hip_rotation': 46.0}  # Different metric
        }
    ]
    
    baseline = compute_player_baseline(historical_sessions, min_sessions=3)
    
    print(f"\nHas Baseline: {baseline['has_baseline']}")
    print(f"Baseline Technique: {baseline['baseline_technique_score']}")
    print(f"Baseline Readiness: {baseline['baseline_readiness_score']}")
    
    if baseline['baseline_metrics']:
        print("\nBaseline Metrics:")
        for metric, stats in baseline['baseline_metrics'].items():
            print(f"  {metric}: mean={stats['mean']:.1f}, sample_size={stats['sample_size']}")
    
    assert baseline['has_baseline'] == True
    assert baseline['baseline_technique_score'] is not None  # Average of 75 and 78
    assert baseline['baseline_readiness_score'] is not None  # Average of 72 and 71
    
    # Elbow angle should have 2 samples
    assert baseline['baseline_metrics']['elbow_angle']['sample_size'] == 2
    # Hip rotation should have 1 sample
    assert baseline['baseline_metrics']['hip_rotation']['sample_size'] == 1
    
    print("\n✓ Test passed!\n")


def test_baseline_statistics():
    """Test statistical aggregation (mean, std) in baseline computation."""
    print("=" * 60)
    print("TEST 7: Baseline Statistics")
    print("=" * 60)
    
    # Sessions with known values
    historical_sessions = [
        {
            'session_id': '2025-12-25_10-00-00',
            'technique_score': 70.0,
            'readiness_score': 70.0,
            'metrics': {'elbow_angle': 150.0}
        },
        {
            'session_id': '2025-12-26_10-00-00',
            'technique_score': 80.0,
            'readiness_score': 80.0,
            'metrics': {'elbow_angle': 160.0}
        },
        {
            'session_id': '2025-12-27_10-00-00',
            'technique_score': 90.0,
            'readiness_score': 90.0,
            'metrics': {'elbow_angle': 170.0}
        }
    ]
    
    baseline = compute_player_baseline(historical_sessions, min_sessions=3)
    
    print(f"\nBaseline Technique: {baseline['baseline_technique_score']}")
    print(f"Expected: 80.0 (mean of 70, 80, 90)")
    
    elbow_stats = baseline['baseline_metrics']['elbow_angle']
    print(f"\nElbow Angle Mean: {elbow_stats['mean']}")
    print(f"Elbow Angle Std: {elbow_stats['std']}")
    print(f"Expected Mean: 160.0 (mean of 150, 160, 170)")
    
    assert abs(baseline['baseline_technique_score'] - 80.0) < 0.1
    assert abs(baseline['baseline_readiness_score'] - 80.0) < 0.1
    assert abs(elbow_stats['mean'] - 160.0) < 0.1
    assert elbow_stats['std'] > 0  # Should have some variance
    
    print("\n✓ Test passed!\n")


def test_comparison_zero_baseline():
    """Test comparison with zero baseline (edge case)."""
    print("=" * 60)
    print("TEST 8: Comparison with Zero Baseline (Edge Case)")
    print("=" * 60)
    
    comparison = compare_to_baseline(
        current_value=50.0,
        baseline_value=0.0,  # Zero baseline
        metric_name='Test metric'
    )
    
    print(f"\nDelta Direction: {comparison['delta_direction']}")
    print(f"Interpretation: {comparison['interpretation']}")
    
    assert comparison['delta_direction'] == 'stable'
    assert 'baseline is zero' in comparison['interpretation']
    
    print("\n✓ Test passed!\n")


def run_all_tests():
    """Run all test cases."""
    print("\n")
    print("█" * 60)
    print("PLAYER BASELINE & PERSONALIZATION - TEST SUITE")
    print("█" * 60)
    print("\n")
    
    try:
        test_baseline_computation()
        test_insufficient_data()
        test_comparison_above_baseline()
        test_comparison_below_baseline()
        test_comparison_stable()
        test_baseline_with_missing_data()
        test_baseline_statistics()
        test_comparison_zero_baseline()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nPlayer Baseline & Personalization Intelligence is working correctly.")
        print("The system can:")
        print("  • Compute player baselines from historical sessions")
        print("  • Handle missing data gracefully")
        print("  • Compare current values to baseline")
        print("  • Generate human-readable interpretations")
        print("  • Compute accurate statistics (mean, std)")
        print("  • Handle edge cases (zero baseline, insufficient data)")
        
        return True
        
    except AssertionError as e:
        print("\n" + "=" * 60)
        print("✗ TEST FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

