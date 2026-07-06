"""
movement.py

Movement & footwork intelligence: metric specs + CV extraction from pose.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
import os
import sys
import json
import math
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union
import numpy as np
import pandas as pd

MOVEMENT_METRICS = {
    'split_step_timing': {
        'name': 'Split-Step Timing',
        'description': 'Timing and execution of the split-step before shot',
        'expected_range': (-0.1, 0.1),  # seconds (negative = early, positive = late)
        'optimal_value': 0.0,  # Perfect timing at opponent contact
        'rationale': 'Split-step should occur at/just before opponent contact for optimal reaction',
        'importance': 'HIGH',
        'stroke_phase_mapping': 'preparation',
        'assessment_criteria': {
            'excellent': (-0.05, 0.05),  # Within 50ms
            'good': (-0.1, 0.1),  # Within 100ms
            'needs_work': None  # Outside 100ms
        }
    },
    
    'lateral_push_off_symmetry': {
        'name': 'Lateral Push-Off Symmetry',
        'description': 'Balance between left and right leg power in lateral movements',
        'expected_range': (0.8, 1.2),  # ratio (1.0 = perfect symmetry)
        'optimal_value': 1.0,
        'rationale': 'Balanced lateral movement prevents injury and enables consistent positioning',
        'importance': 'MEDIUM',
        'stroke_phase_mapping': 'preparation',
        'assessment_criteria': {
            'excellent': (0.9, 1.1),  # Within 10% difference
            'good': (0.8, 1.2),  # Within 20% difference
            'needs_work': None  # > 20% asymmetry
        }
    },
    
    'recovery_time': {
        'name': 'Recovery Time',
        'description': 'Time to return to ready position after shot',
        'expected_range': (0.5, 1.0),  # seconds
        'optimal_value': 0.7,
        'rationale': 'Fast recovery enables preparation for next shot and rally control',
        'importance': 'HIGH',
        'stroke_phase_mapping': 'follow_through',
        'assessment_criteria': {
            'excellent': (0.5, 0.7),  # Quick recovery
            'good': (0.7, 1.0),  # Adequate recovery
            'needs_work': None  # > 1.0s (slow recovery)
        }
    },
    
    'stance_transition_speed': {
        'name': 'Stance Transition Speed',
        'description': 'Speed of transitioning from ready to stroke stance',
        'expected_range': (0.2, 0.5),  # seconds
        'optimal_value': 0.3,
        'rationale': 'Quick stance setup enables optimal stroke mechanics',
        'importance': 'MEDIUM',
        'stroke_phase_mapping': 'preparation',
        'assessment_criteria': {
            'excellent': (0.2, 0.3),  # Very quick
            'good': (0.3, 0.5),  # Adequate speed
            'needs_work': None  # > 0.5s (slow setup)
        }
    },
    
    'balance_drift': {
        'name': 'Balance Drift',
        'description': 'Center of mass stability during shot execution',
        'expected_range': (0, 10),  # cm of lateral drift
        'optimal_value': 5,  # Minimal controlled drift
        'rationale': 'Stable balance enables consistent contact point and power transfer',
        'importance': 'HIGH',
        'stroke_phase_mapping': 'contact',
        'assessment_criteria': {
            'excellent': (0, 5),  # Minimal drift
            'good': (5, 10),  # Acceptable drift
            'needs_work': None  # > 10cm (unstable)
        }
    },
    
    'first_step_reaction_time': {
        'name': 'First Step Reaction Time',
        'description': 'Time from opponent contact to first step initiation',
        'expected_range': (0.2, 0.4),  # seconds
        'optimal_value': 0.3,
        'rationale': 'Quick first step enables better court coverage and positioning',
        'importance': 'MEDIUM',
        'stroke_phase_mapping': 'preparation',
        'assessment_criteria': {
            'excellent': (0.2, 0.3),  # Very quick
            'good': (0.3, 0.4),  # Good reaction
            'needs_work': None  # > 0.4s (slow reaction)
        }
    },
    
    'footwork_efficiency': {
        'name': 'Footwork Efficiency',
        'description': 'Ratio of steps taken to distance covered (lower = more efficient)',
        'expected_range': (1.5, 2.5),  # steps per meter
        'optimal_value': 2.0,
        'rationale': 'Efficient footwork conserves energy and improves positioning accuracy',
        'importance': 'MEDIUM',
        'stroke_phase_mapping': 'preparation',
        'assessment_criteria': {
            'excellent': (1.5, 2.0),  # Very efficient
            'good': (2.0, 2.5),  # Adequate efficiency
            'needs_work': None  # > 2.5 (too many small steps)
        }
    },
    
    'weight_transfer_completeness': {
        'name': 'Weight Transfer Completeness',
        'description': 'Percentage of body weight successfully transferred forward during shot',
        'expected_range': (60, 90),  # percentage
        'optimal_value': 75,
        'rationale': 'Complete weight transfer maximizes power and control',
        'importance': 'HIGH',
        'stroke_phase_mapping': 'contact',
        'assessment_criteria': {
            'excellent': (75, 90),  # Full transfer
            'good': (60, 75),  # Partial transfer
            'needs_work': None  # < 60% (incomplete transfer)
        }
    }
}


def get_movement_metric_spec(metric_name: str) -> dict:
    """
    Get specification for a movement/footwork metric.
    
    Movement metrics are stroke-agnostic and evaluate positioning, balance,
    and footwork quality. They complement stroke mechanics by assessing
    the foundational movement patterns that enable good stroke execution.
    
    INTEGRATION WITH EXISTING SYSTEMS:
    - Movement metrics participate in reliability analysis (same as stroke metrics)
    - Movement issues are eligible for adaptive prioritization (CRITICAL/PRIORITY/MONITOR)
    - Low-reliability movement metrics are suppressible
    - Movement drills map via existing drill recommendation engine
    
    BACKWARD COMPATIBILITY:
    - Returns None if metric not found (caller handles gracefully)
    - System works perfectly without movement metrics
    - Existing stroke analysis remains unchanged
    
    Args:
        metric_name: Name of movement metric (e.g., 'split_step_timing')
        
    Returns:
        Dictionary with metric specification, or None if not found
        
    Example:
        >>> spec = get_movement_metric_spec('split_step_timing')
        >>> print(spec['expected_range'])
        (-0.1, 0.1)  # seconds
        
        >>> spec = get_movement_metric_spec('unknown_metric')
        >>> print(spec)
        None
    """
    # Normalize metric name
    metric_key = metric_name.lower().strip().replace(' ', '_')
    
    # Return spec if found
    return MOVEMENT_METRICS.get(metric_key)


def assess_movement_quality(
    metric_name: str,
    measured_value: float
) -> dict:
    """
    Assess the quality of a movement/footwork metric.
    
    Uses movement-specific thresholds to classify performance as:
    - 'excellent': Top-tier movement quality
    - 'good': Adequate movement quality
    - 'needs_work': Below acceptable threshold
    
    Returns assessment with human-readable feedback.
    
    INTEGRATION:
    - Assessment results feed into adaptive prioritization
    - 'needs_work' classifications become coaching priorities
    - 'excellent' classifications may suppress redundant coaching
    
    Args:
        metric_name: Name of movement metric
        measured_value: Player's measured value
        
    Returns:
        Dictionary with assessment results:
        - classification: 'excellent' / 'good' / 'needs_work' / 'unknown'
        - deviation: Distance from optimal
        - feedback: Human-readable coaching feedback
        
    Example:
        >>> result = assess_movement_quality('split_step_timing', 0.15)
        >>> print(result['classification'])
        'needs_work'
        >>> print(result['feedback'])
        'Split-step timing is late by 150ms. Work on anticipation.'
    """
    spec = get_movement_metric_spec(metric_name)
    
    if not spec:
        return {
            'classification': 'unknown',
            'deviation': None,
            'feedback': f"Metric '{metric_name}' not recognized"
        }
    
    # Get assessment criteria
    criteria = spec['assessment_criteria']
    optimal = spec['optimal_value']
    
    # Calculate deviation from optimal
    deviation = measured_value - optimal
    
    # Classify performance
    if criteria['excellent'] and criteria['excellent'][0] <= measured_value <= criteria['excellent'][1]:
        classification = 'excellent'
        feedback = f"{spec['name']} is excellent. Maintain this quality."
    elif criteria['good'] and criteria['good'][0] <= measured_value <= criteria['good'][1]:
        classification = 'good'
        feedback = f"{spec['name']} is good but can improve. {spec['rationale']}"
    else:
        classification = 'needs_work'
        # Generate specific feedback based on deviation direction
        if 'timing' in metric_name.lower() or 'time' in metric_name.lower():
            if deviation > 0:
                feedback = f"{spec['name']} is too slow by {abs(deviation):.2f}s. {spec['rationale']}"
            else:
                feedback = f"{spec['name']} is early by {abs(deviation):.2f}s. {spec['rationale']}"
        elif 'symmetry' in metric_name.lower():
            side = 'right' if measured_value > 1.0 else 'left'
            asymmetry = abs((measured_value - 1.0) * 100)
            feedback = f"{spec['name']} shows {asymmetry:.0f}% imbalance favoring {side} side. {spec['rationale']}"
        else:
            feedback = f"{spec['name']} needs improvement (current: {measured_value:.2f}, optimal: {optimal:.2f}). {spec['rationale']}"
    
    return {
        'classification': classification,
        'deviation': deviation,
        'feedback': feedback,
        'importance': spec['importance'],
        'stroke_phase': spec['stroke_phase_mapping']
    }


def is_movement_metric(metric_name: str) -> bool:
    """
    Check if a metric belongs to the movement/footwork family.
    
    This allows existing systems (reliability, prioritization, drills) to
    distinguish between stroke mechanics and movement metrics.
    
    Args:
        metric_name: Name of metric to check
        
    Returns:
        True if movement metric, False otherwise
        
    Example:
        >>> is_movement_metric('split_step_timing')
        True
        >>> is_movement_metric('hip_rotation')
        False
    """
    metric_key = metric_name.lower().strip().replace(' ', '_')
    return metric_key in MOVEMENT_METRICS


def compute_center_of_mass(landmarks_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute approximate center of mass from hip landmarks.
    
    Uses mid-hip position as COM proxy. This is a simplification but
    sufficient for movement analysis (balance, lateral motion, etc.).
    
    Args:
        landmarks_df: DataFrame with pose landmarks (must have hip columns)
        
    Returns:
        DataFrame with COM coordinates: com_x, com_y, com_z
        Returns empty DataFrame if hip landmarks missing
        
    Example:
        >>> com = compute_center_of_mass(landmarks_df)
        >>> lateral_drift = com['com_x'].max() - com['com_x'].min()
    """
    try:
        # Check for required landmarks
        if 'left_hip_x' not in landmarks_df.columns or 'right_hip_x' not in landmarks_df.columns:
            return pd.DataFrame()
        
        # Compute mid-hip position as COM proxy
        com_df = pd.DataFrame()
        com_df['com_x'] = (landmarks_df['left_hip_x'] + landmarks_df['right_hip_x']) / 2
        com_df['com_y'] = (landmarks_df['left_hip_y'] + landmarks_df['right_hip_y']) / 2
        
        if 'left_hip_z' in landmarks_df.columns and 'right_hip_z' in landmarks_df.columns:
            com_df['com_z'] = (landmarks_df['left_hip_z'] + landmarks_df['right_hip_z']) / 2
        else:
            com_df['com_z'] = 0.0
        
        return com_df
    
    except Exception as e:
        print(f"[WARNING] Failed to compute COM: {e}")
        return pd.DataFrame()


def extract_split_step_timing(
    landmarks_df: pd.DataFrame,
    contact_frame: int,
    fps: float = 24.0,
    search_window_frames: int = 30
) -> dict:
    """
    Extract split-step timing from pose time series.
    
    APPROACH:
    - Split-step is a "dip and plant" movement before stroke
    - Detected via: COM vertical motion + knee flexion increase
    - Optimal timing: 0-150ms before opponent contact (we use player contact as proxy)
    
    HEURISTIC:
    1. Search window: [contact_frame - search_window, contact_frame]
    2. Detect COM vertical dip (local minimum in com_y)
    3. Confirm with knee flexion increase
    4. Compute timing relative to contact
    
    CONFIDENCE:
    - High (0.8-1.0): Clear dip detected, knee flexion confirms
    - Medium (0.5-0.8): Dip detected, weak knee signal
    - Low (0-0.5): No clear dip, or too noisy
    
    Args:
        landmarks_df: DataFrame with pose landmarks
        contact_frame: Frame index of stroke contact
        fps: Frames per second
        search_window_frames: Frames to search before contact
        
    Returns:
        Dictionary with:
        - split_step_timing_seconds: Time before contact (negative = early, positive = late)
        - split_step_quality: 'on-time' / 'early' / 'late' / 'not_detected'
        - confidence: 0.0-1.0
        - split_step_frame: Frame where split-step detected (or None)
    """
    result = {
        'split_step_timing_seconds': None,
        'split_step_quality': 'not_detected',
        'confidence': 0.0,
        'split_step_frame': None
    }
    
    try:
        # Compute COM
        com_df = compute_center_of_mass(landmarks_df)
        if com_df.empty:
            return result
        
        # Define search window
        start_frame = max(0, contact_frame - search_window_frames)
        end_frame = contact_frame
        
        if end_frame - start_frame < 5:  # Need minimum window
            return result
        
        # Extract COM vertical position in window
        com_y_window = com_df['com_y'].iloc[start_frame:end_frame].values
        
        if len(com_y_window) < 5:
            return result
        
        # Smooth to reduce noise
        from scipy.ndimage import gaussian_filter1d
        com_y_smooth = gaussian_filter1d(com_y_window, sigma=2)
        
        # Find local minima (dip candidates)
        from scipy.signal import find_peaks
        peaks, properties = find_peaks(-com_y_smooth, prominence=0.01)  # Inverted to find minima
        
        if len(peaks) == 0:
            result['confidence'] = 0.1  # No dip detected
            return result
        
        # Take the last (closest to contact) dip as split-step
        split_step_idx = peaks[-1]
        split_step_frame = start_frame + split_step_idx
        
        # Compute timing relative to contact
        frames_before_contact = contact_frame - split_step_frame
        timing_seconds = frames_before_contact / fps
        
        # Check knee flexion for confirmation (if available)
        confidence = 0.6  # Base confidence
        
        if 'left_knee_angle' in landmarks_df.columns and 'right_knee_angle' in landmarks_df.columns:
            knee_angles = (landmarks_df['left_knee_angle'] + landmarks_df['right_knee_angle']) / 2
            knee_at_split = knee_angles.iloc[split_step_frame] if split_step_frame < len(knee_angles) else None
            knee_at_contact = knee_angles.iloc[contact_frame] if contact_frame < len(knee_angles) else None
            
            if knee_at_split is not None and knee_at_contact is not None:
                knee_flexion_increase = knee_at_contact - knee_at_split
                if knee_flexion_increase > 5:  # Degrees
                    confidence = 0.85  # High confidence with knee confirmation
        
        # Determine quality
        if -0.15 <= timing_seconds <= 0.05:  # -150ms to +50ms
            quality = 'on-time'
            confidence = min(1.0, confidence + 0.1)
        elif timing_seconds < -0.15:
            quality = 'early'
        else:
            quality = 'late'
        
        result['split_step_timing_seconds'] = -timing_seconds  # Negative = before contact
        result['split_step_quality'] = quality
        result['confidence'] = confidence
        result['split_step_frame'] = split_step_frame
        
    except Exception as e:
        print(f"[WARNING] Split-step extraction failed: {e}")
        result['confidence'] = 0.0
    
    return result


def extract_recovery_time(
    landmarks_df: pd.DataFrame,
    contact_frame: int,
    fps: float = 24.0,
    max_search_frames: int = 60
) -> dict:
    """
    Extract recovery time from pose time series.
    
    APPROACH:
    - Recovery = time from contact to return-to-ready position
    - Detected via: stance width stabilizes + COM lateral velocity drops
    
    HEURISTIC:
    1. Search window: [contact_frame, contact_frame + max_search]
    2. Compute stance width (ankle distance) over time
    3. Compute COM lateral velocity
    4. Ready position: stance width stable + low lateral velocity
    
    CONFIDENCE:
    - High (0.8-1.0): Clear stabilization detected
    - Medium (0.5-0.8): Stabilization detected, some noise
    - Low (0-0.5): No clear stabilization or max search reached
    
    Args:
        landmarks_df: DataFrame with pose landmarks
        contact_frame: Frame index of stroke contact
        fps: Frames per second
        max_search_frames: Maximum frames to search after contact
        
    Returns:
        Dictionary with:
        - recovery_time_seconds: Time from contact to ready
        - confidence: 0.0-1.0
        - recovery_frame: Frame where ready position detected (or None)
    """
    result = {
        'recovery_time_seconds': None,
        'confidence': 0.0,
        'recovery_frame': None
    }
    
    try:
        # Compute COM
        com_df = compute_center_of_mass(landmarks_df)
        if com_df.empty:
            return result
        
        # Define search window
        start_frame = contact_frame
        end_frame = min(len(landmarks_df), contact_frame + max_search_frames)
        
        if end_frame - start_frame < 10:  # Need minimum window
            return result
        
        # Compute COM lateral velocity (change in com_x)
        com_x = com_df['com_x'].values
        com_velocity = np.abs(np.diff(com_x, prepend=com_x[0]))
        
        # Smooth velocity
        from scipy.ndimage import gaussian_filter1d
        com_velocity_smooth = gaussian_filter1d(com_velocity, sigma=2)
        
        # Find when velocity drops below threshold
        velocity_threshold = 0.005  # Normalized units (adjust based on frame size)
        
        search_velocity = com_velocity_smooth[start_frame:end_frame]
        
        # Find first frame where velocity stays below threshold for 3+ frames
        stable_count = 0
        recovery_idx = None
        
        for i in range(len(search_velocity)):
            if search_velocity[i] < velocity_threshold:
                stable_count += 1
                if stable_count >= 3:  # 3 consecutive frames below threshold
                    recovery_idx = i
                    break
            else:
                stable_count = 0
        
        if recovery_idx is None:
            # No recovery detected in search window
            result['confidence'] = 0.2
            result['recovery_time_seconds'] = max_search_frames / fps  # Max time
            return result
        
        recovery_frame = start_frame + recovery_idx
        recovery_time = recovery_idx / fps
        
        # Confidence based on velocity profile smoothness
        velocity_variance = np.var(search_velocity[:recovery_idx+1])
        confidence = 0.7 if velocity_variance < 0.0001 else 0.5
        
        result['recovery_time_seconds'] = recovery_time
        result['confidence'] = confidence
        result['recovery_frame'] = recovery_frame
        
    except Exception as e:
        print(f"[WARNING] Recovery time extraction failed: {e}")
        result['confidence'] = 0.0
    
    return result


def extract_balance_drift(
    landmarks_df: pd.DataFrame,
    contact_frame: int,
    window_frames: int = 10
) -> dict:
    """
    Extract balance drift from pose time series.
    
    APPROACH:
    - Balance drift = lateral COM movement during stroke execution
    - Measured in contact window: [contact_frame - window, contact_frame + window]
    
    HEURISTIC:
    1. Extract COM lateral position (com_x) in contact window
    2. Compute max lateral drift: max(com_x) - min(com_x)
    3. Normalize by frame width if available
    4. Compute stability score: 100 - (drift * scale_factor)
    
    CONFIDENCE:
    - High (0.8-1.0): Smooth COM trajectory, clear measurement
    - Medium (0.5-0.8): Some noise in trajectory
    - Low (0-0.5): Very noisy or insufficient data
    
    Args:
        landmarks_df: DataFrame with pose landmarks
        contact_frame: Frame index of stroke contact
        window_frames: Frames before/after contact to analyze
        
    Returns:
        Dictionary with:
        - balance_drift_cm_or_normalized: Lateral drift magnitude
        - stability_score: 0-100 (100 = perfect stability)
        - confidence: 0.0-1.0
    """
    result = {
        'balance_drift_cm_or_normalized': None,
        'stability_score': None,
        'confidence': 0.0
    }
    
    try:
        # Compute COM
        com_df = compute_center_of_mass(landmarks_df)
        if com_df.empty:
            return result
        
        # Define analysis window
        start_frame = max(0, contact_frame - window_frames)
        end_frame = min(len(landmarks_df), contact_frame + window_frames)
        
        if end_frame - start_frame < 5:  # Need minimum window
            return result
        
        # Extract COM lateral position in window
        com_x_window = com_df['com_x'].iloc[start_frame:end_frame].values
        
        if len(com_x_window) < 5:
            return result
        
        # Compute lateral drift
        drift = np.max(com_x_window) - np.min(com_x_window)
        
        # Compute stability score (0-100, higher = more stable)
        # Assume drift is in normalized coordinates (0-1 range)
        # Typical good balance: drift < 0.05 (5% of frame width)
        stability_score = max(0, 100 - (drift * 2000))  # Scale factor
        stability_score = min(100, stability_score)
        
        # Confidence based on trajectory smoothness
        com_x_diff = np.diff(com_x_window)
        trajectory_variance = np.var(com_x_diff)
        
        if trajectory_variance < 0.0001:
            confidence = 0.85  # High confidence, smooth trajectory
        elif trajectory_variance < 0.001:
            confidence = 0.65  # Medium confidence
        else:
            confidence = 0.4  # Low confidence, noisy
        
        result['balance_drift_cm_or_normalized'] = drift
        result['stability_score'] = stability_score
        result['confidence'] = confidence
        
    except Exception as e:
        print(f"[WARNING] Balance drift extraction failed: {e}")
        result['confidence'] = 0.0
    
    return result


def extract_movement_metrics_from_video(
    landmarks_df: pd.DataFrame,
    contact_frame: int,
    fps: float = 24.0
) -> dict:
    """
    Extract all CV-based movement metrics from pose time series.
    
    This is the main integration function that calls individual extractors
    and packages results for downstream analysis.
    
    INTEGRATION:
    - Called during pipeline execution (optional)
    - Results feed into Movement Intelligence (Phase 2.2)
    - Used for fatigue detection (Phase 2.3)
    - Participate in reliability analysis
    
    GRACEFUL DEGRADATION:
    - If landmarks_df is empty/invalid, returns empty dict
    - If individual extractors fail, their metrics are None
    - Pipeline continues without CV movement metrics
    
    Args:
        landmarks_df: DataFrame with pose landmarks (MediaPipe output)
        contact_frame: Frame index of stroke contact
        fps: Video frames per second
        
    Returns:
        Dictionary with extracted movement metrics:
        - split_step_timing: dict from extract_split_step_timing()
        - recovery_time: dict from extract_recovery_time()
        - balance_drift: dict from extract_balance_drift()
        - overall_confidence: Average confidence across metrics
        
    Example:
        >>> metrics = extract_movement_metrics_from_video(landmarks_df, contact_frame=220, fps=24.0)
        >>> if metrics['split_step_timing']['confidence'] > 0.5:
        ...     print(f"Split-step: {metrics['split_step_timing']['split_step_quality']}")
    """
    result = {
        'split_step_timing': {},
        'recovery_time': {},
        'balance_drift': {},
        'overall_confidence': 0.0
    }
    
    try:
        # Check input validity
        if landmarks_df is None or landmarks_df.empty:
            print("[INFO] No landmarks data available for movement extraction")
            return result
        
        if contact_frame < 0 or contact_frame >= len(landmarks_df):
            print(f"[WARNING] Invalid contact frame {contact_frame} for landmarks length {len(landmarks_df)}")
            return result
        
        # Extract individual metrics
        result['split_step_timing'] = extract_split_step_timing(landmarks_df, contact_frame, fps)
        result['recovery_time'] = extract_recovery_time(landmarks_df, contact_frame, fps)
        result['balance_drift'] = extract_balance_drift(landmarks_df, contact_frame)
        
        # Compute overall confidence
        confidences = [
            result['split_step_timing'].get('confidence', 0.0),
            result['recovery_time'].get('confidence', 0.0),
            result['balance_drift'].get('confidence', 0.0)
        ]
        result['overall_confidence'] = np.mean([c for c in confidences if c > 0]) if any(c > 0 for c in confidences) else 0.0
        
        # Log extraction summary
        print(f"[CV MOVEMENT] Extracted metrics with overall confidence: {result['overall_confidence']:.2f}")
        if result['split_step_timing'].get('confidence', 0) > 0.5:
            print(f"  - Split-step: {result['split_step_timing']['split_step_quality']} "
                  f"({result['split_step_timing']['split_step_timing_seconds']:.3f}s)")
        if result['recovery_time'].get('confidence', 0) > 0.5:
            print(f"  - Recovery time: {result['recovery_time']['recovery_time_seconds']:.2f}s")
        if result['balance_drift'].get('confidence', 0) > 0.5:
            print(f"  - Balance stability: {result['balance_drift']['stability_score']:.0f}/100")
        
    except Exception as e:
        print(f"[WARNING] Movement metric extraction failed: {e}")
        result['overall_confidence'] = 0.0
    
    return result

