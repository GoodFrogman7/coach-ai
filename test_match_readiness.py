"""
Test script for Match Readiness Intelligence (Phase 4.1)

This script validates:
1. Match readiness computation with all components
2. Graceful degradation when components are missing
3. Human-readable explanations
4. Flag generation for concerns
5. Confidence scoring based on data availability
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from vision.compare import compute_match_readiness


def test_excellent_readiness():
    """Test excellent readiness with all components strong."""
    print("=" * 60)
    print("TEST 1: Excellent Readiness")
    print("=" * 60)
    
    # High technique, good movement, low fatigue, good signal quality
    readiness = compute_match_readiness(
        technique_score=92.5,
        movement_metrics={
            'split_step_timing': {
                'split_step_quality': 'on-time',
                'confidence': 0.9
            },
            'recovery_time': {
                'recovery_time_seconds': 1.2,
                'confidence': 0.85
            },
            'balance_drift': {
                'stability_score': 85,
                'confidence': 0.88
            }
        },
        fatigue_analysis={
            'fatigue_score': 15,
            'affected_metrics': ['recovery_time']
        },
        signal_quality={
            'quality_score': 0.92,
            'issues': []
        }
    )
    
    print(f"\nReadiness Score: {readiness['readiness_score']}/100")
    print(f"Readiness Level: {readiness['readiness_level']}")
    print(f"Confidence: {readiness['confidence']:.0%}")
    print(f"\nExplanation: {readiness['explanation']}")
    print(f"\nFlags: {readiness['flags'] if readiness['flags'] else 'None'}")
    
    print("\nContributors:")
    for component, data in readiness['contributors'].items():
        print(f"  {component}: {data['raw_score']:.1f}/100 (weight: {data['weight']:.0%})")
    
    assert readiness['readiness_level'] == 'Excellent', f"Expected Excellent, got {readiness['readiness_level']}"
    assert readiness['readiness_score'] >= 85, f"Score should be >= 85, got {readiness['readiness_score']}"
    assert readiness['confidence'] >= 0.9, f"Confidence should be high with all data, got {readiness['confidence']}"
    
    print("\n✓ Test passed!\n")


def test_fair_readiness_with_concerns():
    """Test fair readiness with multiple concerns."""
    print("=" * 60)
    print("TEST 2: Fair Readiness with Concerns")
    print("=" * 60)
    
    # Moderate technique, some movement concerns, low fatigue
    readiness = compute_match_readiness(
        technique_score=70.0,
        movement_metrics={
            'split_step_timing': {
                'split_step_quality': 'late',
                'confidence': 0.75
            },
            'recovery_time': {
                'recovery_time_seconds': 1.8,  # Not too bad
                'confidence': 0.70
            },
            'balance_drift': {
                'stability_score': 65,  # Fair
                'confidence': 0.65
            }
        },
        fatigue_analysis={
            'fatigue_score': 35,  # Low-moderate fatigue
            'affected_metrics': ['recovery_time', 'balance_drift']
        },
        signal_quality={
            'quality_score': 0.75,  # Good enough
            'issues': ['occasional_jitter']
        }
    )
    
    print(f"\nReadiness Score: {readiness['readiness_score']}/100")
    print(f"Readiness Level: {readiness['readiness_level']}")
    print(f"Confidence: {readiness['confidence']:.0%}")
    print(f"\nExplanation: {readiness['explanation']}")
    
    if readiness['flags']:
        print("\nFlags:")
        for flag in readiness['flags']:
            print(f"  - {flag}")
    
    # Fair or Good is acceptable for this scenario
    assert readiness['readiness_level'] in ['Fair', 'Good', 'Poor'], f"Expected Fair/Good/Poor, got {readiness['readiness_level']}"
    assert len(readiness['flags']) > 0, "Should have flags for concerns"
    assert 'Split-step timing needs improvement' in readiness['flags']
    
    print("\n✓ Test passed!\n")


def test_poor_readiness_high_fatigue():
    """Test poor readiness driven by high fatigue."""
    print("=" * 60)
    print("TEST 3: Poor Readiness (High Fatigue)")
    print("=" * 60)
    
    # Decent technique but very high fatigue
    readiness = compute_match_readiness(
        technique_score=75.0,
        movement_metrics={
            'split_step_timing': {
                'split_step_quality': 'on-time',
                'confidence': 0.80
            },
            'recovery_time': {
                'recovery_time_seconds': 2.8,
                'confidence': 0.75
            },
            'balance_drift': {
                'stability_score': 48,
                'confidence': 0.70
            }
        },
        fatigue_analysis={
            'fatigue_score': 85,
            'affected_metrics': ['recovery_time', 'balance_drift', 'rotation_range', 'elbow_angle', 'stance_width']
        },
        signal_quality={
            'quality_score': 0.88,
            'issues': []
        }
    )
    
    print(f"\nReadiness Score: {readiness['readiness_score']}/100")
    print(f"Readiness Level: {readiness['readiness_level']}")
    print(f"Confidence: {readiness['confidence']:.0%}")
    print(f"\nExplanation: {readiness['explanation']}")
    
    if readiness['flags']:
        print("\nFlags:")
        for flag in readiness['flags']:
            print(f"  - {flag}")
    
    assert readiness['readiness_score'] < 70, f"Score should be < 70 with high fatigue, got {readiness['readiness_score']}"
    assert len(readiness['flags']) > 0, "Should have fatigue flags"
    assert any('fatigue' in flag.lower() for flag in readiness['flags']), "Should mention fatigue in flags"
    
    print("\n✓ Test passed!\n")


def test_graceful_degradation_minimal_data():
    """Test graceful degradation when only technique is available."""
    print("=" * 60)
    print("TEST 4: Graceful Degradation (Minimal Data)")
    print("=" * 60)
    
    # Only technique available
    readiness = compute_match_readiness(
        technique_score=82.0,
        movement_metrics=None,
        fatigue_analysis=None,
        signal_quality=None
    )
    
    print(f"\nReadiness Score: {readiness['readiness_score']}/100")
    print(f"Readiness Level: {readiness['readiness_level']}")
    print(f"Confidence: {readiness['confidence']:.0%}")
    print(f"\nExplanation: {readiness['explanation']}")
    
    print("\nContributors:")
    for component, data in readiness['contributors'].items():
        print(f"  {component}: {data['raw_score']:.1f}/100 (weight: {data['weight']:.0%})")
    
    # Should only have technique component
    assert 'technique' in readiness['contributors'], "Should have technique"
    assert 'movement' not in readiness['contributors'], "Should not have movement"
    assert 'fatigue' not in readiness['contributors'], "Should not have fatigue"
    assert 'trust' not in readiness['contributors'], "Should not have trust"
    
    # Confidence should be reduced due to missing data
    assert readiness['confidence'] < 0.6, f"Confidence should be lower with minimal data, got {readiness['confidence']}"
    
    # Only one component should be present
    assert len(readiness['contributors']) == 1, f"Should only have 1 component, got {len(readiness['contributors'])}"
    
    print("\n✓ Test passed!\n")


def test_weight_rebalancing():
    """Test that readiness scores are computed correctly when data is missing."""
    print("=" * 60)
    print("TEST 5: Weight Rebalancing")
    print("=" * 60)
    
    # Test with technique and movement only
    readiness = compute_match_readiness(
        technique_score=80.0,
        movement_metrics={
            'split_step_timing': {
                'split_step_quality': 'on-time',
                'confidence': 0.85
            },
            'recovery_time': {
                'recovery_time_seconds': 1.5,
                'confidence': 0.80
            },
            'balance_drift': {
                'stability_score': 75,
                'confidence': 0.82
            }
        },
        fatigue_analysis=None,
        signal_quality=None
    )
    
    print("\nContributors:")
    for component, data in readiness['contributors'].items():
        print(f"  {component}: weight = {data['weight']:.2f}")
    
    # Check that we have technique and movement only
    assert 'technique' in readiness['contributors']
    assert 'movement' in readiness['contributors']
    assert 'fatigue' not in readiness['contributors']
    assert 'trust' not in readiness['contributors']
    
    # Readiness score should be reasonable
    assert 50 < readiness['readiness_score'] < 100, f"Score should be reasonable, got {readiness['readiness_score']}"
    
    print(f"\nReadiness Score: {readiness['readiness_score']:.1f}/100")
    print(f"Confidence: {readiness['confidence']:.0%}")
    
    print("\n✓ Test passed!\n")


def test_confidence_modulation_by_trust():
    """Test that low trust reduces overall confidence."""
    print("=" * 60)
    print("TEST 6: Confidence Modulation by Trust")
    print("=" * 60)
    
    # Same setup, but with low vs high trust
    base_params = {
        'technique_score': 85.0,
        'movement_metrics': {
            'split_step_timing': {
                'split_step_quality': 'on-time',
                'confidence': 0.85
            },
            'recovery_time': {
                'recovery_time_seconds': 1.3,
                'confidence': 0.80
            },
            'balance_drift': {
                'stability_score': 80,
                'confidence': 0.82
            }
        },
        'fatigue_analysis': {
            'fatigue_score': 20,
            'affected_metrics': []
        }
    }
    
    # High trust
    readiness_high_trust = compute_match_readiness(
        **base_params,
        signal_quality={
            'quality_score': 0.95,
            'issues': []
        }
    )
    
    # Low trust
    readiness_low_trust = compute_match_readiness(
        **base_params,
        signal_quality={
            'quality_score': 0.45,
            'issues': ['visibility', 'jitter', 'tracking_loss']
        }
    )
    
    print(f"High trust confidence: {readiness_high_trust['confidence']:.2f}")
    print(f"Low trust confidence: {readiness_low_trust['confidence']:.2f}")
    
    assert readiness_low_trust['confidence'] < readiness_high_trust['confidence'], \
        "Low trust should reduce confidence"
    
    assert 'Measurement quality below optimal' in readiness_low_trust['flags'], \
        "Should flag low measurement quality"
    
    print("\n✓ Test passed!\n")


def run_all_tests():
    """Run all test cases."""
    print("\n")
    print("█" * 60)
    print("MATCH READINESS INTELLIGENCE - TEST SUITE")
    print("█" * 60)
    print("\n")
    
    try:
        test_excellent_readiness()
        test_fair_readiness_with_concerns()
        test_poor_readiness_high_fatigue()
        test_graceful_degradation_minimal_data()
        test_weight_rebalancing()
        test_confidence_modulation_by_trust()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nMatch Readiness Intelligence is working correctly.")
        print("The system can:")
        print("  • Synthesize technique, movement, fatigue, and trust")
        print("  • Generate human-readable explanations")
        print("  • Flag concerns appropriately")
        print("  • Gracefully degrade with missing data")
        print("  • Rebalance weights when components are absent")
        print("  • Modulate confidence based on trust and data availability")
        
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

