"""
Test script for Progress Narratives & Coach Summaries (Phase 5.2)

This script validates:
1. Trend detection (improving/stable/declining)
2. Narrative generation
3. Coach's take generation
4. Graceful degradation with insufficient data
5. Conservative thresholds
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from vision.compare import (
    detect_trend,
    generate_progress_narrative,
    _generate_coach_take
)


def test_trend_improving():
    """Test trend detection for improving values."""
    print("=" * 60)
    print("TEST 1: Trend Detection - Improving")
    print("=" * 60)
    
    # Values showing clear improvement
    values = [70.0, 72.0, 74.0, 76.0, 78.0]
    
    trend = detect_trend(values, min_sessions=3, threshold_percent=5.0)
    
    print(f"\nHas Trend: {trend['has_trend']}")
    print(f"Trend: {trend['trend']}")
    print(f"Earlier Avg: {trend['earlier_avg']}")
    print(f"Recent Avg: {trend['recent_avg']}")
    print(f"Percent Change: {trend['percent_change']}%")
    print(f"Confidence: {trend['confidence']}")
    
    assert trend['has_trend'] == True
    assert trend['trend'] == 'improving'
    assert trend['percent_change'] > 5.0  # Should be > threshold
    
    print("\n✓ Test passed!\n")


def test_trend_declining():
    """Test trend detection for declining values."""
    print("=" * 60)
    print("TEST 2: Trend Detection - Declining")
    print("=" * 60)
    
    # Values showing clear decline
    values = [80.0, 78.0, 76.0, 74.0, 72.0]
    
    trend = detect_trend(values, min_sessions=3, threshold_percent=5.0)
    
    print(f"\nHas Trend: {trend['has_trend']}")
    print(f"Trend: {trend['trend']}")
    print(f"Earlier Avg: {trend['earlier_avg']}")
    print(f"Recent Avg: {trend['recent_avg']}")
    print(f"Percent Change: {trend['percent_change']}%")
    
    assert trend['has_trend'] == True
    assert trend['trend'] == 'declining'
    assert trend['percent_change'] < -5.0  # Should be < -threshold
    
    print("\n✓ Test passed!\n")


def test_trend_stable():
    """Test trend detection for stable values."""
    print("=" * 60)
    print("TEST 3: Trend Detection - Stable")
    print("=" * 60)
    
    # Values showing stability (within 5%)
    values = [75.0, 76.0, 74.5, 75.5, 76.5]
    
    trend = detect_trend(values, min_sessions=3, threshold_percent=5.0)
    
    print(f"\nHas Trend: {trend['has_trend']}")
    print(f"Trend: {trend['trend']}")
    print(f"Earlier Avg: {trend['earlier_avg']}")
    print(f"Recent Avg: {trend['recent_avg']}")
    print(f"Percent Change: {trend['percent_change']}%")
    
    assert trend['has_trend'] == True
    assert trend['trend'] == 'stable'
    assert abs(trend['percent_change']) < 5.0  # Should be within threshold
    
    print("\n✓ Test passed!\n")


def test_trend_insufficient_data():
    """Test graceful degradation with insufficient data."""
    print("=" * 60)
    print("TEST 4: Insufficient Data for Trend")
    print("=" * 60)
    
    # Only 2 values (need 3)
    values = [75.0, 76.0]
    
    trend = detect_trend(values, min_sessions=3, threshold_percent=5.0)
    
    print(f"\nHas Trend: {trend['has_trend']}")
    print(f"Reason: {trend.get('reason', 'N/A')}")
    
    assert trend['has_trend'] == False
    assert 'reason' in trend
    
    print("\n✓ Test passed!\n")


def test_narrative_positive_trends():
    """Test narrative generation with positive trends."""
    print("=" * 60)
    print("TEST 5: Narrative with Positive Trends")
    print("=" * 60)
    
    # Mock historical sessions showing improvement
    historical_sessions = [
        {'session_id': 'session5', 'technique_score': 78.0, 'readiness_score': 80.0},
        {'session_id': 'session4', 'technique_score': 76.0, 'readiness_score': 78.0},
        {'session_id': 'session3', 'technique_score': 74.0, 'readiness_score': 76.0},
        {'session_id': 'session2', 'technique_score': 72.0, 'readiness_score': 74.0},
        {'session_id': 'session1', 'technique_score': 70.0, 'readiness_score': 72.0}
    ]
    
    narrative = generate_progress_narrative(historical_sessions, num_sessions=5, min_sessions=3)
    
    print(f"\nHas Narrative: {narrative['has_narrative']}")
    print(f"Session Count: {narrative['session_count']}")
    print(f"\nNarrative Summary:")
    print(f"{narrative['narrative_summary']}")
    print(f"\nCoach's Take:")
    print(f"{narrative['coach_take']}")
    
    assert narrative['has_narrative'] == True
    assert 'improving' in narrative['narrative_summary'].lower() or 'progress' in narrative['narrative_summary'].lower()
    assert len(narrative['coach_take']) > 0
    
    # Check that technique and readiness trends are improving
    assert narrative['trends']['technique']['trend'] == 'improving'
    assert narrative['trends']['readiness']['trend'] == 'improving'
    
    print("\n✓ Test passed!\n")


def test_narrative_mixed_trends():
    """Test narrative generation with mixed trends."""
    print("=" * 60)
    print("TEST 6: Narrative with Mixed Trends")
    print("=" * 60)
    
    # Mock sessions: technique improving, readiness declining
    historical_sessions = [
        {'session_id': 'session5', 'technique_score': 78.0, 'readiness_score': 70.0},
        {'session_id': 'session4', 'technique_score': 76.0, 'readiness_score': 72.0},
        {'session_id': 'session3', 'technique_score': 74.0, 'readiness_score': 74.0},
        {'session_id': 'session2', 'technique_score': 72.0, 'readiness_score': 76.0},
        {'session_id': 'session1', 'technique_score': 70.0, 'readiness_score': 78.0}
    ]
    
    narrative = generate_progress_narrative(historical_sessions, num_sessions=5, min_sessions=3)
    
    print(f"\nNarrative Summary:")
    print(f"{narrative['narrative_summary']}")
    print(f"\nCoach's Take:")
    print(f"{narrative['coach_take']}")
    
    assert narrative['has_narrative'] == True
    # Should mention both positive and concern
    summary_lower = narrative['narrative_summary'].lower()
    assert 'improving' in summary_lower or 'progress' in summary_lower
    assert 'dipped' in summary_lower or 'dropped' in summary_lower or 'noting' in summary_lower
    
    print("\n✓ Test passed!\n")


def test_narrative_stable_performance():
    """Test narrative generation with stable performance."""
    print("=" * 60)
    print("TEST 7: Narrative with Stable Performance")
    print("=" * 60)
    
    # Mock sessions with consistent values
    historical_sessions = [
        {'session_id': 'session5', 'technique_score': 75.5, 'readiness_score': 74.5},
        {'session_id': 'session4', 'technique_score': 75.0, 'readiness_score': 75.0},
        {'session_id': 'session3', 'technique_score': 76.0, 'readiness_score': 75.5},
        {'session_id': 'session2', 'technique_score': 74.5, 'readiness_score': 74.0},
        {'session_id': 'session1', 'technique_score': 75.0, 'readiness_score': 75.0}
    ]
    
    narrative = generate_progress_narrative(historical_sessions, num_sessions=5, min_sessions=3)
    
    print(f"\nNarrative Summary:")
    print(f"{narrative['narrative_summary']}")
    print(f"\nCoach's Take:")
    print(f"{narrative['coach_take']}")
    
    assert narrative['has_narrative'] == True
    # Should mention consistency/stable
    summary_lower = narrative['narrative_summary'].lower()
    assert 'steady' in summary_lower or 'consistent' in summary_lower or 'holding' in summary_lower
    
    print("\n✓ Test passed!\n")


def test_narrative_insufficient_sessions():
    """Test graceful degradation with insufficient sessions."""
    print("=" * 60)
    print("TEST 8: Insufficient Sessions for Narrative")
    print("=" * 60)
    
    # Only 2 sessions (need 3)
    historical_sessions = [
        {'session_id': 'session2', 'technique_score': 76.0, 'readiness_score': 74.0},
        {'session_id': 'session1', 'technique_score': 74.0, 'readiness_score': 72.0}
    ]
    
    narrative = generate_progress_narrative(historical_sessions, num_sessions=5, min_sessions=3)
    
    print(f"\nHas Narrative: {narrative['has_narrative']}")
    print(f"Reason: {narrative.get('reason', 'N/A')}")
    
    assert narrative['has_narrative'] == False
    assert 'reason' in narrative
    
    print("\n✓ Test passed!\n")


def test_coach_take_variations():
    """Test different coach's take scenarios."""
    print("=" * 60)
    print("TEST 9: Coach's Take Variations")
    print("=" * 60)
    
    # Test improving scenario
    trends_improving = {
        'technique': {'trend': 'improving'},
        'readiness': {'trend': 'improving'}
    }
    take1 = _generate_coach_take(trends_improving, 5)
    print(f"\nBoth Improving: {take1}")
    assert 'momentum' in take1.lower() or 'progress' in take1.lower()
    
    # Test declining scenario
    trends_declining = {
        'technique': {'trend': 'declining'},
        'readiness': {'trend': 'declining'}
    }
    take2 = _generate_coach_take(trends_declining, 5)
    print(f"\nBoth Declining: {take2}")
    assert 'dip' in take2.lower() or 'review' in take2.lower()
    
    # Test stable scenario
    trends_stable = {
        'technique': {'trend': 'stable'},
        'readiness': {'trend': 'stable'}
    }
    take3 = _generate_coach_take(trends_stable, 5)
    print(f"\nBoth Stable: {take3}")
    assert 'consistent' in take3.lower() or 'consistency' in take3.lower()
    
    print("\n✓ Test passed!\n")


def test_narrative_with_missing_data():
    """Test narrative generation when some sessions have missing data."""
    print("=" * 60)
    print("TEST 10: Narrative with Missing Data")
    print("=" * 60)
    
    # Some sessions missing technique or readiness
    historical_sessions = [
        {'session_id': 'session5', 'technique_score': 78.0, 'readiness_score': None},
        {'session_id': 'session4', 'technique_score': 76.0, 'readiness_score': 76.0},
        {'session_id': 'session3', 'technique_score': None, 'readiness_score': 74.0},
        {'session_id': 'session2', 'technique_score': 72.0, 'readiness_score': 72.0},
        {'session_id': 'session1', 'technique_score': 70.0, 'readiness_score': 70.0}
    ]
    
    narrative = generate_progress_narrative(historical_sessions, num_sessions=5, min_sessions=3)
    
    print(f"\nHas Narrative: {narrative['has_narrative']}")
    print(f"\nNarrative Summary:")
    print(f"{narrative['narrative_summary']}")
    
    # Should still generate narrative from available data
    assert narrative['has_narrative'] == True
    assert len(narrative['narrative_summary']) > 0
    
    print("\n✓ Test passed!\n")


def run_all_tests():
    """Run all test cases."""
    print("\n")
    print("█" * 60)
    print("PROGRESS NARRATIVES & COACH SUMMARIES - TEST SUITE")
    print("█" * 60)
    print("\n")
    
    try:
        test_trend_improving()
        test_trend_declining()
        test_trend_stable()
        test_trend_insufficient_data()
        test_narrative_positive_trends()
        test_narrative_mixed_trends()
        test_narrative_stable_performance()
        test_narrative_insufficient_sessions()
        test_coach_take_variations()
        test_narrative_with_missing_data()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nProgress Narratives & Coach Summaries are working correctly.")
        print("The system can:")
        print("  • Detect trends (improving/stable/declining)")
        print("  • Generate human-readable progress summaries")
        print("  • Provide coach-style insights")
        print("  • Handle mixed trends appropriately")
        print("  • Work with missing data")
        print("  • Gracefully degrade with insufficient history")
        print("  • Use conservative thresholds (±5%)")
        
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

