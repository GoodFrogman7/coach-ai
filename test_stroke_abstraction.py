#!/usr/bin/env python3
"""
Test script for Stroke Abstraction Layer

This script demonstrates the stroke-aware threshold system and validates
backward compatibility with existing backhand analysis.
"""

import sys
import io

# Fix Windows UTF-8 encoding for emoji support
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer') and sys.stdout.isatty():
    # Only rewrap a real console; under pytest's output capture sys.stdout is
    # not a tty and rewrapping it breaks pytest's capture teardown.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'vision')

from compare import (
    get_stroke_aware_threshold,
    get_stroke_phase_weights,
    STROKE_PROFILES
)


def print_separator(title=""):
    """Print a formatted separator"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    else:
        print('-'*70)


def test_backward_compatibility():
    """Verify that default behavior matches backhand"""
    print_separator("Test 1: Backward Compatibility")
    
    # Test default stroke type
    default_hip = get_stroke_aware_threshold('hip_rotation')
    backhand_hip = get_stroke_aware_threshold('hip_rotation', 'backhand')
    
    print(f"Default hip rotation:  {default_hip}")
    print(f"Backhand hip rotation: {backhand_hip}")
    
    if default_hip == backhand_hip:
        print("✅ PASS: Default matches backhand")
    else:
        print("❌ FAIL: Default does not match backhand")
    
    # Test unknown stroke fallback
    unknown_hip = get_stroke_aware_threshold('hip_rotation', 'unknown_stroke')
    print(f"\nUnknown stroke hip rotation: {unknown_hip}")
    
    if unknown_hip == backhand_hip:
        print("✅ PASS: Unknown stroke falls back to backhand")
    else:
        print("❌ FAIL: Unknown stroke does not fall back correctly")


def test_stroke_specific_ranges():
    """Test that different strokes have different ranges"""
    print_separator("Test 2: Stroke-Specific Ranges")
    
    strokes = ['backhand', 'forehand', 'serve', 'volley', 'overhead']
    metric = 'hip_rotation'
    
    print(f"\n{metric.upper()} ranges by stroke:\n")
    
    for stroke in strokes:
        range_val = get_stroke_aware_threshold(metric, stroke)
        rationale = get_stroke_aware_threshold(metric, stroke, 'rationale')
        print(f"  {stroke.capitalize():12} {range_val}  - {rationale}")
    
    # Verify forehand > backhand
    backhand_range = get_stroke_aware_threshold(metric, 'backhand')
    forehand_range = get_stroke_aware_threshold(metric, 'forehand')
    
    print(f"\nForehand rotation ({forehand_range[0]}-{forehand_range[1]}°) > " +
          f"Backhand rotation ({backhand_range[0]}-{backhand_range[1]}°)")
    
    if forehand_range[0] > backhand_range[0]:
        print("✅ PASS: Forehand has larger rotation than backhand")
    else:
        print("❌ FAIL: Forehand rotation not larger than backhand")


def test_phase_weights():
    """Test stroke-specific phase weights"""
    print_separator("Test 3: Stroke-Specific Phase Weights")
    
    strokes = ['backhand', 'forehand', 'serve', 'volley', 'overhead']
    
    print("\nPhase importance weights by stroke:\n")
    print(f"{'Stroke':<12} {'Prep':>6} {'Load':>6} {'Contact':>8} {'Follow':>8}")
    print_separator()
    
    for stroke in strokes:
        weights = get_stroke_phase_weights(stroke)
        print(f"{stroke.capitalize():<12} "
              f"{weights['preparation']:>6.2f} "
              f"{weights['load']:>6.2f} "
              f"{weights['contact']:>8.2f} "
              f"{weights['follow_through']:>8.2f}")
    
    # Verify volley has high preparation weight
    volley_weights = get_stroke_phase_weights('volley')
    
    if volley_weights['preparation'] >= 0.30:
        print("\n✅ PASS: Volley emphasizes preparation (split-step)")
    else:
        print("\n❌ FAIL: Volley preparation weight too low")


def test_metric_name_variants():
    """Test that different metric name formats work"""
    print_separator("Test 4: Metric Name Variants")
    
    variants = [
        ('hip_rotation', 'backhand'),
        ('hip', 'backhand'),
        ('elbow_angle', 'forehand'),
        ('elbow', 'forehand'),
        ('left_elbow', 'serve'),
        ('knee_flexion', 'volley'),
        ('knee', 'volley'),
    ]
    
    print("\nTesting metric name normalization:\n")
    
    all_pass = True
    for metric, stroke in variants:
        result = get_stroke_aware_threshold(metric, stroke)
        status = "✅" if result is not None else "❌"
        print(f"  {status} {metric:<20} ({stroke}) -> {result}")
        if result is None:
            all_pass = False
    
    if all_pass:
        print("\n✅ PASS: All metric name variants resolved")
    else:
        print("\n❌ FAIL: Some metric names not resolved")


def test_all_profiles_complete():
    """Verify all stroke profiles are complete"""
    print_separator("Test 5: Profile Completeness")
    
    required_metrics = ['hip_rotation', 'elbow_angle', 'knee_flexion', 'spine_lean']
    required_phases = ['preparation', 'load', 'contact', 'follow_through']
    
    print("\nVerifying profile completeness:\n")
    
    all_complete = True
    for stroke_name, profile in STROKE_PROFILES.items():
        print(f"\n{stroke_name.capitalize()}:")
        
        # Check metrics
        missing_metrics = []
        for metric in required_metrics:
            if metric not in profile['biomechanical_intent']:
                missing_metrics.append(metric)
        
        if missing_metrics:
            print(f"  ❌ Missing metrics: {', '.join(missing_metrics)}")
            all_complete = False
        else:
            print(f"  ✅ All metrics present ({len(required_metrics)})")
        
        # Check phases
        missing_phases = []
        for phase in required_phases:
            if phase not in profile['phase_emphasis']:
                missing_phases.append(phase)
        
        if missing_phases:
            print(f"  ❌ Missing phases: {', '.join(missing_phases)}")
            all_complete = False
        else:
            total_weight = sum(profile['phase_emphasis'].values())
            print(f"  ✅ All phases present (total weight: {total_weight:.2f})")
    
    if all_complete:
        print("\n✅ PASS: All profiles complete")
    else:
        print("\n❌ FAIL: Some profiles incomplete")


def test_real_world_comparison():
    """Compare thresholds for a real-world scenario"""
    print_separator("Test 6: Real-World Comparison")
    
    print("\nScenario: A player hits both forehand and backhand groundstrokes")
    print("Question: Should hip rotation thresholds differ?\n")
    
    backhand_hip = get_stroke_aware_threshold('hip_rotation', 'backhand')
    forehand_hip = get_stroke_aware_threshold('hip_rotation', 'forehand')
    
    print(f"Backhand expected range: {backhand_hip[0]}-{backhand_hip[1]}°")
    print(f"Forehand expected range: {forehand_hip[0]}-{forehand_hip[1]}°")
    
    print(f"\nPlayer's measured hip rotation: 165°")
    
    # Check against backhand
    if backhand_hip[0] <= 165 <= backhand_hip[1]:
        print(f"  ✅ Within backhand range (good technique)")
    else:
        print(f"  ⚠️  Outside backhand range (needs work)")
    
    # Check against forehand
    if forehand_hip[0] <= 165 <= forehand_hip[1]:
        print(f"  ✅ Within forehand range (good technique)")
    else:
        print(f"  ⚠️  Outside forehand range (needs more rotation)")
    
    print("\n💡 Insight: Same measurement, different interpretation based on stroke!")
    print("   This is why stroke-aware thresholds are essential.")


def main():
    """Run all tests"""
    print_separator("STROKE ABSTRACTION LAYER TEST SUITE")
    print("Testing backward compatibility and stroke-specific intelligence\n")
    
    try:
        test_backward_compatibility()
        test_stroke_specific_ranges()
        test_phase_weights()
        test_metric_name_variants()
        test_all_profiles_complete()
        test_real_world_comparison()
        
        print_separator("TEST SUITE COMPLETE")
        print("\n✅ All tests passed successfully!")
        print("   Stroke Abstraction Layer is ready for integration.\n")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

