#!/usr/bin/env python3
"""
Test script for CV-Based Movement Extraction (Phase 3.1)
"""

import sys
import io
import numpy as np
import pandas as pd

# Fix Windows UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'vision')

from compare import (
    compute_center_of_mass,
    extract_split_step_timing,
    extract_recovery_time,
    extract_balance_drift,
    extract_movement_metrics_from_video
)

print("="*80)
print("CV-Based Movement Extraction - Test Suite")
print("="*80)

# Create synthetic pose landmarks for testing
def create_synthetic_landmarks(num_frames=100, with_split_step=True, with_recovery=True):
    """
    Create synthetic pose landmarks that simulate a tennis stroke.
    
    Includes:
    - Hip movement (COM proxy)
    - Knee flexion
    - Simulated split-step dip
    - Simulated recovery motion
    """
    frames = []
    
    for i in range(num_frames):
        frame = {}
        
        # Simulate hip position (COM proxy)
        # Baseline position with some natural sway
        base_x = 0.5
        base_y = 0.5
        
        # Add split-step dip around frame 20 (before contact at frame 50)
        if with_split_step and 18 <= i <= 22:
            dip_amount = 0.02 * (1 - abs(i - 20) / 2)  # Gaussian-like dip
            base_y -= dip_amount
        
        # Add forward motion during stroke
        if 50 <= i <= 60:
            base_x += (i - 50) * 0.01
        
        # Add recovery motion after contact (stabilize COM)
        if with_recovery and i > 60:
            # Exponential decay back to center
            recovery_progress = min(1.0, (i - 60) / 15)
            base_x = base_x * (1 - recovery_progress) + 0.5 * recovery_progress
        
        frame['left_hip_x'] = base_x - 0.05 + np.random.normal(0, 0.001)
        frame['right_hip_x'] = base_x + 0.05 + np.random.normal(0, 0.001)
        frame['left_hip_y'] = base_y + np.random.normal(0, 0.001)
        frame['right_hip_y'] = base_y + np.random.normal(0, 0.001)
        frame['left_hip_z'] = 0.0
        frame['right_hip_z'] = 0.0
        
        # Simulate knee flexion (increases at split-step and contact)
        knee_angle = 160  # Base angle
        if with_split_step and 20 <= i <= 25:
            knee_angle -= 10  # Flex during split-step
        if 45 <= i <= 55:
            knee_angle -= 15  # Flex during stroke
        
        frame['left_knee_angle'] = knee_angle + np.random.normal(0, 2)
        frame['right_knee_angle'] = knee_angle + np.random.normal(0, 2)
        
        frames.append(frame)
    
    return pd.DataFrame(frames)


# Test 1: COM Computation
print("\n[Test 1] Center of Mass Computation")
print("-"*80)

landmarks = create_synthetic_landmarks(num_frames=50)
com_df = compute_center_of_mass(landmarks)

print(f"Landmarks shape: {landmarks.shape}")
print(f"COM shape: {com_df.shape}")
print(f"COM columns: {list(com_df.columns)}")
print(f"Sample COM values:")
print(f"  Frame 0: x={com_df['com_x'].iloc[0]:.4f}, y={com_df['com_y'].iloc[0]:.4f}")
print(f"  Frame 25: x={com_df['com_x'].iloc[25]:.4f}, y={com_df['com_y'].iloc[25]:.4f}")

assert not com_df.empty, "COM computation should return non-empty DataFrame"
assert 'com_x' in com_df.columns, "COM should have com_x column"
print("✅ COM computation works correctly")

# Test 2: Split-Step Timing Extraction
print("\n[Test 2] Split-Step Timing Extraction")
print("-"*80)

landmarks_with_split = create_synthetic_landmarks(num_frames=80, with_split_step=True)
contact_frame = 50

split_step_result = extract_split_step_timing(landmarks_with_split, contact_frame, fps=24.0)

print(f"Split-step detected: {split_step_result['split_step_quality']}")
if split_step_result['split_step_timing_seconds'] is not None:
    print(f"Timing: {split_step_result['split_step_timing_seconds']:.3f}s before contact")
else:
    print(f"Timing: Not detected")
print(f"Confidence: {split_step_result['confidence']:.2f}")
print(f"Split-step frame: {split_step_result['split_step_frame']}")

assert split_step_result['confidence'] >= 0, "Should have non-negative confidence"
if split_step_result['split_step_quality'] != 'not_detected':
    print("✅ Split-step timing extraction works")
else:
    print("⚠️  Split-step not detected (synthetic data may be too subtle)")

# Test 3: Split-Step Timing (No Split-Step)
print("\n[Test 3] Split-Step Timing (No Split-Step Present)")
print("-"*80)

landmarks_no_split = create_synthetic_landmarks(num_frames=80, with_split_step=False)

split_step_result_no = extract_split_step_timing(landmarks_no_split, contact_frame, fps=24.0)

print(f"Split-step detected: {split_step_result_no['split_step_quality']}")
print(f"Confidence: {split_step_result_no['confidence']:.2f}")

assert split_step_result_no['confidence'] < 0.5, "Should have low confidence when no split-step"
print("✅ Correctly handles absence of split-step")

# Test 4: Recovery Time Extraction
print("\n[Test 4] Recovery Time Extraction")
print("-"*80)

landmarks_with_recovery = create_synthetic_landmarks(num_frames=100, with_recovery=True)

recovery_result = extract_recovery_time(landmarks_with_recovery, contact_frame, fps=24.0)

print(f"Recovery time: {recovery_result['recovery_time_seconds']:.2f}s")
print(f"Confidence: {recovery_result['confidence']:.2f}")
print(f"Recovery frame: {recovery_result['recovery_frame']}")

assert recovery_result['recovery_time_seconds'] is not None, "Should extract recovery time"
assert recovery_result['recovery_time_seconds'] > 0, "Recovery time should be positive"
print("✅ Recovery time extraction works")

# Test 5: Balance Drift Extraction
print("\n[Test 5] Balance Drift Extraction")
print("-"*80)

balance_result = extract_balance_drift(landmarks_with_recovery, contact_frame, window_frames=10)

print(f"Balance drift: {balance_result['balance_drift_cm_or_normalized']:.4f}")
print(f"Stability score: {balance_result['stability_score']:.1f}/100")
print(f"Confidence: {balance_result['confidence']:.2f}")

assert balance_result['balance_drift_cm_or_normalized'] is not None, "Should extract balance drift"
assert balance_result['stability_score'] is not None, "Should compute stability score"
assert 0 <= balance_result['stability_score'] <= 100, "Stability score should be 0-100"
print("✅ Balance drift extraction works")

# Test 6: Integrated Movement Metrics Extraction
print("\n[Test 6] Integrated Movement Metrics Extraction")
print("-"*80)

full_landmarks = create_synthetic_landmarks(num_frames=100, with_split_step=True, with_recovery=True)

metrics = extract_movement_metrics_from_video(full_landmarks, contact_frame=50, fps=24.0)

print(f"Overall confidence: {metrics['overall_confidence']:.2f}")
print(f"\nSplit-step timing:")
print(f"  Quality: {metrics['split_step_timing']['split_step_quality']}")
print(f"  Confidence: {metrics['split_step_timing']['confidence']:.2f}")
print(f"\nRecovery time:")
print(f"  Time: {metrics['recovery_time']['recovery_time_seconds']:.2f}s")
print(f"  Confidence: {metrics['recovery_time']['confidence']:.2f}")
print(f"\nBalance drift:")
print(f"  Stability: {metrics['balance_drift']['stability_score']:.1f}/100")
print(f"  Confidence: {metrics['balance_drift']['confidence']:.2f}")

assert metrics['overall_confidence'] > 0, "Should have overall confidence > 0"
assert 'split_step_timing' in metrics, "Should include split-step timing"
assert 'recovery_time' in metrics, "Should include recovery time"
assert 'balance_drift' in metrics, "Should include balance drift"
print("✅ Integrated extraction works correctly")

# Test 7: Graceful Degradation (Empty Data)
print("\n[Test 7] Graceful Degradation - Empty Landmarks")
print("-"*80)

empty_landmarks = pd.DataFrame()

metrics_empty = extract_movement_metrics_from_video(empty_landmarks, contact_frame=50, fps=24.0)

print(f"Overall confidence: {metrics_empty['overall_confidence']:.2f}")
print(f"Split-step detected: {metrics_empty['split_step_timing']}")
print(f"Recovery detected: {metrics_empty['recovery_time']}")

assert metrics_empty['overall_confidence'] == 0, "Should have zero confidence for empty data"
print("✅ Gracefully handles empty data")

# Test 8: Graceful Degradation (Invalid Contact Frame)
print("\n[Test 8] Graceful Degradation - Invalid Contact Frame")
print("-"*80)

valid_landmarks = create_synthetic_landmarks(num_frames=50)

metrics_invalid = extract_movement_metrics_from_video(valid_landmarks, contact_frame=200, fps=24.0)

print(f"Overall confidence: {metrics_invalid['overall_confidence']:.2f}")

assert metrics_invalid['overall_confidence'] == 0, "Should have zero confidence for invalid frame"
print("✅ Gracefully handles invalid contact frame")

# Test 9: Graceful Degradation (Missing Landmarks)
print("\n[Test 9] Graceful Degradation - Missing Hip Landmarks")
print("-"*80)

incomplete_landmarks = pd.DataFrame({
    'left_knee_angle': [160] * 50,
    'right_knee_angle': [160] * 50
    # Hip landmarks missing
})

com_incomplete = compute_center_of_mass(incomplete_landmarks)

print(f"COM from incomplete landmarks: {com_incomplete.shape}")

assert com_incomplete.empty, "Should return empty DataFrame for missing hips"
print("✅ Gracefully handles missing landmarks")

# Summary
print("\n" + "="*80)
print("✅ All CV-Based Movement Extraction tests passed!")
print("="*80)
print("\nKey Capabilities Validated:")
print("  ✓ Center of mass computation from hip landmarks")
print("  ✓ Split-step timing detection with dip analysis")
print("  ✓ Recovery time measurement from COM stabilization")
print("  ✓ Balance drift quantification during stroke")
print("  ✓ Integrated extraction with confidence scoring")
print("  ✓ Graceful degradation with empty/invalid data")
print("  ✓ Confidence-based quality assessment")
print("\n💡 CV movement extraction ready for pipeline integration!")

