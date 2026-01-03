"""
Test script for Training Load & Session Planning Intelligence (Phase 4.2)

This script validates:
1. Training load decision logic for various readiness/fatigue combinations
2. Session type and intensity recommendations
3. Focus areas and avoid areas generation
4. Human-readable rationale generation
5. Graceful degradation with missing data
6. Confidence scoring
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from vision.compare import compute_training_load_recommendation


def test_excellent_readiness_match_sim():
    """Test match simulation recommendation for excellent readiness."""
    print("=" * 60)
    print("TEST 1: Excellent Readiness → Match Simulation")
    print("=" * 60)
    
    # Excellent readiness, low fatigue
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 92.0,
            'readiness_level': 'Excellent',
            'confidence': 0.95
        },
        fatigue_analysis={
            'fatigue_score': 15.0,
            'affected_metrics': []
        },
        signal_quality={
            'quality_score': 0.92
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    if training_load['focus_areas']:
        print("\nFocus Areas:")
        for area in training_load['focus_areas']:
            print(f"  - {area}")
    
    assert training_load['session_type'] == 'Match-sim', f"Expected Match-sim, got {training_load['session_type']}"
    assert training_load['intensity'] == 'High', f"Expected High intensity, got {training_load['intensity']}"
    assert len(training_load['focus_areas']) > 0, "Should have focus areas"
    assert 'Match simulation' in training_load['focus_areas']
    
    print("\n✓ Test passed!\n")


def test_good_readiness_full_training():
    """Test full training recommendation for good readiness."""
    print("=" * 60)
    print("TEST 2: Good Readiness + Low Fatigue → Full Training")
    print("=" * 60)
    
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 78.0,
            'readiness_level': 'Good',
            'confidence': 0.88
        },
        fatigue_analysis={
            'fatigue_score': 25.0,
            'affected_metrics': []
        },
        signal_quality={
            'quality_score': 0.85
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    assert training_load['session_type'] == 'Full', f"Expected Full, got {training_load['session_type']}"
    assert training_load['intensity'] == 'High', f"Expected High intensity, got {training_load['intensity']}"
    
    print("\n✓ Test passed!\n")


def test_fair_readiness_technique_focus():
    """Test technique focus for fair readiness."""
    print("=" * 60)
    print("TEST 3: Fair Readiness → Technique Focus")
    print("=" * 60)
    
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 62.0,
            'readiness_level': 'Fair',
            'confidence': 0.75
        },
        fatigue_analysis={
            'fatigue_score': 35.0,
            'affected_metrics': ['recovery_time']
        },
        signal_quality={
            'quality_score': 0.80
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    if training_load['focus_areas']:
        print("\nFocus Areas:")
        for area in training_load['focus_areas']:
            print(f"  - {area}")
    
    assert training_load['session_type'] == 'Technique', f"Expected Technique, got {training_load['session_type']}"
    assert training_load['intensity'] == 'Moderate', f"Expected Moderate intensity, got {training_load['intensity']}"
    assert len(training_load['focus_areas']) > 0, "Should have focus areas"
    
    print("\n✓ Test passed!\n")


def test_high_fatigue_recovery():
    """Test recovery recommendation for high fatigue."""
    print("=" * 60)
    print("TEST 4: High Fatigue → Recovery Session")
    print("=" * 60)
    
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 72.0,
            'readiness_level': 'Good',
            'confidence': 0.85
        },
        fatigue_analysis={
            'fatigue_score': 80.0,  # Very high fatigue to trigger warning
            'affected_metrics': ['recovery_time', 'balance_drift', 'rotation_range', 'elbow_angle']
        },
        signal_quality={
            'quality_score': 0.88
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    if training_load['avoid_areas']:
        print("\nAvoid Areas:")
        for area in training_load['avoid_areas']:
            print(f"  - {area}")
    
    if training_load['warnings']:
        print("\nWarnings:")
        for warning in training_load['warnings']:
            print(f"  - {warning}")
    
    assert training_load['session_type'] == 'Recovery', f"Expected Recovery, got {training_load['session_type']}"
    assert training_load['intensity'] == 'Low', f"Expected Low intensity, got {training_load['intensity']}"
    assert len(training_load['avoid_areas']) > 0, "Should have avoid areas for recovery"
    assert len(training_load['warnings']) > 0, "Should have warnings for very high fatigue"
    
    print("\n✓ Test passed!\n")


def test_low_readiness_light_technique():
    """Test light technique for low readiness."""
    print("=" * 60)
    print("TEST 5: Low Readiness → Light Technique")
    print("=" * 60)
    
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 48.0,
            'readiness_level': 'Poor',
            'confidence': 0.65
        },
        fatigue_analysis={
            'fatigue_score': 30.0,
            'affected_metrics': []
        },
        signal_quality={
            'quality_score': 0.78
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    if training_load['avoid_areas']:
        print("\nAvoid Areas:")
        for area in training_load['avoid_areas']:
            print(f"  - {area}")
    
    assert training_load['session_type'] == 'Technique', f"Expected Technique, got {training_load['session_type']}"
    assert training_load['intensity'] == 'Low', f"Expected Low intensity, got {training_load['intensity']}"
    assert 'Match simulation' in training_load['avoid_areas']
    
    print("\n✓ Test passed!\n")


def test_low_signal_quality():
    """Test recommendation for low signal quality."""
    print("=" * 60)
    print("TEST 6: Low Signal Quality → Re-record Recommendation")
    print("=" * 60)
    
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 75.0,
            'readiness_level': 'Good',
            'confidence': 0.45  # Low due to signal quality
        },
        fatigue_analysis={
            'fatigue_score': 20.0,
            'affected_metrics': []
        },
        signal_quality={
            'quality_score': 0.45  # Low quality
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    if training_load['warnings']:
        print("\nWarnings:")
        for warning in training_load['warnings']:
            print(f"  - {warning}")
    
    assert training_load['intensity'] == 'Low', f"Expected Low intensity with low trust, got {training_load['intensity']}"
    assert len(training_load['warnings']) > 0, "Should have warning about measurement quality"
    assert any('quality' in w.lower() or 're-record' in w.lower() for w in training_load['warnings'])
    
    print("\n✓ Test passed!\n")


def test_graceful_degradation():
    """Test graceful degradation with minimal data."""
    print("=" * 60)
    print("TEST 7: Graceful Degradation (Minimal Data)")
    print("=" * 60)
    
    # Only basic match readiness, no other data
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 70.0,
            'readiness_level': 'Good',
            'confidence': 0.50
        },
        fatigue_analysis=None,
        signal_quality=None,
        adaptive_coaching=None
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    # Should still provide valid recommendation
    assert training_load['session_type'] in ['Recovery', 'Technique', 'Movement', 'Conditioning', 'Full', 'Match-sim']
    assert training_load['intensity'] in ['Low', 'Moderate', 'High']
    assert len(training_load['rationale']) > 0
    
    # Confidence should be reduced due to missing data
    assert training_load['confidence'] < 0.6, f"Confidence should be lower with minimal data, got {training_load['confidence']}"
    
    print("\n✓ Test passed!\n")


def test_good_readiness_moderate_fatigue():
    """Test conditioning session for good readiness but moderate fatigue."""
    print("=" * 60)
    print("TEST 8: Good Readiness + Moderate Fatigue → Conditioning")
    print("=" * 60)
    
    training_load = compute_training_load_recommendation(
        match_readiness={
            'readiness_score': 77.0,
            'readiness_level': 'Good',
            'confidence': 0.90
        },
        fatigue_analysis={
            'fatigue_score': 45.0,
            'affected_metrics': ['recovery_time', 'balance_drift']
        },
        signal_quality={
            'quality_score': 0.87
        }
    )
    
    print(f"\nSession Type: {training_load['session_type']}")
    print(f"Intensity: {training_load['intensity']}")
    print(f"Confidence: {training_load['confidence']:.0%}")
    print(f"\nRationale: {training_load['rationale']}")
    
    # Should recommend Conditioning instead of Full due to moderate fatigue
    assert training_load['session_type'] == 'Conditioning', f"Expected Conditioning, got {training_load['session_type']}"
    assert training_load['intensity'] == 'Moderate', f"Expected Moderate intensity, got {training_load['intensity']}"
    
    if training_load['avoid_areas']:
        print("\nAvoid Areas:")
        for area in training_load['avoid_areas']:
            print(f"  - {area}")
        assert 'Max-intensity rallies' in training_load['avoid_areas']
    
    print("\n✓ Test passed!\n")


def run_all_tests():
    """Run all test cases."""
    print("\n")
    print("█" * 60)
    print("TRAINING LOAD & SESSION PLANNING - TEST SUITE")
    print("█" * 60)
    print("\n")
    
    try:
        test_excellent_readiness_match_sim()
        test_good_readiness_full_training()
        test_fair_readiness_technique_focus()
        test_high_fatigue_recovery()
        test_low_readiness_light_technique()
        test_low_signal_quality()
        test_graceful_degradation()
        test_good_readiness_moderate_fatigue()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nTraining Load & Session Planning Intelligence is working correctly.")
        print("The system can:")
        print("  • Recommend appropriate session types based on readiness")
        print("  • Adjust intensity based on fatigue levels")
        print("  • Generate human-readable rationales")
        print("  • Provide focus areas and avoid areas")
        print("  • Issue warnings when necessary")
        print("  • Handle low signal quality appropriately")
        print("  • Gracefully degrade with missing data")
        print("  • Adjust confidence scores based on data availability")
        
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

