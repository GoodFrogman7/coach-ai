"""
reliability.py

Signal-quality, trust calibration, and measurement-reliability analysis.

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
from vision.movement import compute_center_of_mass

def compute_signal_quality_score(landmarks_df: pd.DataFrame) -> dict:
    """
    Compute session-level signal quality score from pose time series.
    
    Analyzes tracking artifacts that reduce measurement trust:
    1. Landmark visibility consistency - Are key landmarks always visible?
    2. Frame-to-frame jitter - Excessive noise in position?
    3. Missing data ratio - What % of frames have missing landmarks?
    4. Sudden COM jumps - Tracking loss / reacquisition?
    
    QUALITY INDICATORS:
    - High (0.8-1.0): Clean tracking, consistent visibility, low jitter
    - Medium (0.5-0.8): Some noise/occlusion, still usable
    - Low (0-0.5): Significant tracking issues, low trust
    
    Args:
        landmarks_df: DataFrame with pose landmarks (MediaPipe output)
        
    Returns:
        Dictionary with signal quality assessment:
        - signal_quality_score: 0.0-1.0 (normalized overall quality)
        - visibility_score: 0.0-1.0 (landmark visibility consistency)
        - jitter_score: 0.0-1.0 (1 = low jitter, 0 = high jitter)
        - missing_data_ratio: 0.0-1.0 (fraction of missing data)
        - tracking_stability_score: 0.0-1.0 (COM jump analysis)
        - quality_level: 'high' / 'medium' / 'low'
        - trust_reasons: List of human-readable quality issues
        
    Example:
        >>> quality = compute_signal_quality_score(landmarks_df)
        >>> if quality['signal_quality_score'] < 0.5:
        ...     print("Low signal quality:", quality['trust_reasons'])
    """
    result = {
        'signal_quality_score': 1.0,  # Default: high quality
        'visibility_score': 1.0,
        'jitter_score': 1.0,
        'missing_data_ratio': 0.0,
        'tracking_stability_score': 1.0,
        'quality_level': 'high',
        'trust_reasons': []
    }
    
    try:
        if landmarks_df is None or landmarks_df.empty:
            result['signal_quality_score'] = 0.0
            result['quality_level'] = 'low'
            result['trust_reasons'].append("No pose landmarks available")
            return result
        
        # 1. Landmark Visibility Consistency
        # Check if key landmarks (hips, knees) have consistent visibility
        key_landmarks = ['left_hip_x', 'right_hip_x', 'left_knee_angle', 'right_knee_angle']
        available_landmarks = [lm for lm in key_landmarks if lm in landmarks_df.columns]
        
        if not available_landmarks:
            result['visibility_score'] = 0.0
            result['trust_reasons'].append("Key landmarks missing from tracking data")
        else:
            # Count non-null values for each landmark
            visibility_ratios = []
            for landmark in available_landmarks:
                non_null_ratio = landmarks_df[landmark].notna().sum() / len(landmarks_df)
                visibility_ratios.append(non_null_ratio)
            
            result['visibility_score'] = np.mean(visibility_ratios)
            result['missing_data_ratio'] = 1.0 - result['visibility_score']
            
            if result['visibility_score'] < 0.7:
                result['trust_reasons'].append(
                    f"Low landmark visibility ({result['visibility_score']*100:.0f}% frames tracked)"
                )
        
        # 2. Frame-to-Frame Jitter
        # Compute position variance in hip landmarks (excessive jitter = tracking noise)
        if 'left_hip_x' in landmarks_df.columns and 'right_hip_x' in landmarks_df.columns:
            com_x = (landmarks_df['left_hip_x'] + landmarks_df['right_hip_x']) / 2
            com_x_clean = com_x.dropna()
            
            if len(com_x_clean) > 5:
                # Compute frame-to-frame differences
                frame_diffs = np.abs(np.diff(com_x_clean.values))
                median_diff = np.median(frame_diffs)
                
                # Jitter = number of diffs > 3x median (outliers)
                jitter_outliers = np.sum(frame_diffs > 3 * median_diff)
                jitter_ratio = jitter_outliers / len(frame_diffs)
                
                result['jitter_score'] = 1.0 - min(1.0, jitter_ratio * 5)  # Scale penalty
                
                if result['jitter_score'] < 0.7:
                    result['trust_reasons'].append(
                        f"Tracking jitter detected ({jitter_ratio*100:.1f}% outlier frames)"
                    )
        
        # 3. Sudden COM Jumps (tracking loss/reacquisition)
        com_df = compute_center_of_mass(landmarks_df)
        if not com_df.empty and len(com_df) > 10:
            com_x = com_df['com_x'].values
            com_y = com_df['com_y'].values
            
            # Compute frame-to-frame distances
            distances = np.sqrt(np.diff(com_x)**2 + np.diff(com_y)**2)
            median_distance = np.median(distances)
            
            # Sudden jumps = distances > 5x median
            sudden_jumps = np.sum(distances > 5 * median_distance)
            jump_ratio = sudden_jumps / len(distances)
            
            result['tracking_stability_score'] = 1.0 - min(1.0, jump_ratio * 10)  # Scale penalty
            
            if result['tracking_stability_score'] < 0.7:
                result['trust_reasons'].append(
                    f"Tracking instability detected ({sudden_jumps} sudden position jumps)"
                )
        
        # 4. Compute Overall Signal Quality Score (weighted average)
        weights = {
            'visibility': 0.40,  # Most important
            'jitter': 0.30,
            'tracking_stability': 0.30
        }
        
        result['signal_quality_score'] = (
            result['visibility_score'] * weights['visibility'] +
            result['jitter_score'] * weights['jitter'] +
            result['tracking_stability_score'] * weights['tracking_stability']
        )
        
        # 5. Determine Quality Level
        if result['signal_quality_score'] >= 0.8:
            result['quality_level'] = 'high'
        elif result['signal_quality_score'] >= 0.5:
            result['quality_level'] = 'medium'
            if not result['trust_reasons']:
                result['trust_reasons'].append("Moderate tracking quality detected")
        else:
            result['quality_level'] = 'low'
            if not result['trust_reasons']:
                result['trust_reasons'].append("Poor tracking quality detected")
        
    except Exception as e:
        print(f"[WARNING] Signal quality computation failed: {e}")
        result['signal_quality_score'] = 0.5  # Default to medium on error
        result['quality_level'] = 'medium'
        result['trust_reasons'].append("Signal quality assessment inconclusive")
    
    return result


def modulate_confidence_with_signal_quality(
    metric_confidence: float,
    signal_quality: dict,
    metric_name: str = None
) -> dict:
    """
    Modulate metric confidence based on signal quality.
    
    Combines biomechanical confidence (from CV extraction) with signal quality
    (from tracking analysis) to produce a calibrated trust score.
    
    FORMULA:
    - trust_score = metric_confidence × signal_quality_score × modulation_factor
    - modulation_factor adjusts based on quality level and metric type
    
    GRACEFUL DEGRADATION:
    - No metric is fully discarded (minimum trust > 0)
    - Low signal quality reduces trust but doesn't eliminate it
    - High-confidence metrics are less affected by moderate quality issues
    
    Args:
        metric_confidence: Original confidence from CV extraction (0-1)
        signal_quality: Output from compute_signal_quality_score()
        metric_name: Optional metric name for specific adjustments
        
    Returns:
        Dictionary with modulated confidence:
        - trust_score: Calibrated confidence (0-1)
        - original_confidence: Input metric confidence
        - signal_quality_score: Input signal quality
        - modulation_factor: Applied adjustment factor
        - trust_level: 'high' / 'medium' / 'low'
        - trust_reason: Human-readable explanation (if confidence reduced)
        
    Example:
        >>> quality = compute_signal_quality_score(landmarks_df)
        >>> modulated = modulate_confidence_with_signal_quality(0.85, quality)
        >>> print(f"Trust score: {modulated['trust_score']:.2f}")
    """
    result = {
        'trust_score': metric_confidence,  # Default: no change
        'original_confidence': metric_confidence,
        'signal_quality_score': signal_quality['signal_quality_score'],
        'modulation_factor': 1.0,
        'trust_level': 'high',
        'trust_reason': None
    }
    
    try:
        sq_score = signal_quality['signal_quality_score']
        quality_level = signal_quality['quality_level']
        
        # Determine modulation factor based on quality level
        if quality_level == 'high':
            # High signal quality: minimal modulation
            modulation_factor = 1.0
            trust_reason = None
        
        elif quality_level == 'medium':
            # Medium signal quality: moderate modulation
            # Scale based on actual score (0.5-0.8 range)
            modulation_factor = 0.7 + (sq_score - 0.5) * 0.6  # 0.7 to 0.88
            
            # Generate reason from signal quality issues
            if signal_quality['trust_reasons']:
                trust_reason = signal_quality['trust_reasons'][0]  # Primary issue
            else:
                trust_reason = "Moderate tracking quality"
        
        elif quality_level == 'low':
            # Low signal quality: significant modulation but not zero
            # Scale based on actual score (0-0.5 range)
            modulation_factor = 0.4 + sq_score * 0.6  # 0.4 to 0.7
            
            # Generate reason from signal quality issues
            if signal_quality['trust_reasons']:
                # Combine top issues
                reasons = signal_quality['trust_reasons'][:2]
                trust_reason = "; ".join(reasons)
            else:
                trust_reason = "Low tracking quality"
        
        else:
            # Unknown quality level: default moderate modulation
            modulation_factor = 0.8
            trust_reason = "Signal quality unknown"
        
        # Apply modulation
        trust_score = metric_confidence * modulation_factor
        
        # Ensure minimum trust (graceful degradation)
        trust_score = max(0.1, trust_score)  # Never go below 0.1
        
        # Determine trust level
        if trust_score >= 0.7:
            trust_level = 'high'
        elif trust_score >= 0.4:
            trust_level = 'medium'
        else:
            trust_level = 'low'
        
        result.update({
            'trust_score': trust_score,
            'modulation_factor': modulation_factor,
            'trust_level': trust_level,
            'trust_reason': trust_reason
        })
        
    except Exception as e:
        print(f"[WARNING] Confidence modulation failed: {e}")
        # On error, return original confidence
        result['trust_score'] = metric_confidence
        result['trust_reason'] = "Trust calibration failed"
    
    return result


def apply_trust_calibration_to_cv_metrics(
    cv_metrics: dict,
    signal_quality: dict
) -> dict:
    """
    Apply trust calibration to all CV-extracted movement metrics.
    
    This is the main integration function that:
    1. Takes CV-extracted metrics with biomechanical confidence
    2. Applies signal quality modulation
    3. Returns calibrated trust scores + reasons
    
    INTEGRATION:
    - Call after extract_movement_metrics_from_video()
    - Trust scores replace confidences for downstream analysis
    - Original confidences preserved for reference
    
    Args:
        cv_metrics: Output from extract_movement_metrics_from_video()
        signal_quality: Output from compute_signal_quality_score()
        
    Returns:
        Dictionary with trust-calibrated metrics:
        - All original cv_metrics fields preserved
        - Each metric gets additional 'trust_calibration' field
        - Overall trust summary added
        
    Example:
        >>> cv_metrics = extract_movement_metrics_from_video(landmarks_df, 220, 24.0)
        >>> signal_quality = compute_signal_quality_score(landmarks_df)
        >>> calibrated = apply_trust_calibration_to_cv_metrics(cv_metrics, signal_quality)
        >>> print(f"Calibrated confidence: {calibrated['split_step_timing']['trust_calibration']['trust_score']:.2f}")
    """
    calibrated = cv_metrics.copy()
    
    try:
        # Calibrate each metric type
        metric_types = ['split_step_timing', 'recovery_time', 'balance_drift']
        
        for metric_type in metric_types:
            if metric_type in calibrated and 'confidence' in calibrated[metric_type]:
                original_conf = calibrated[metric_type]['confidence']
                
                # Apply trust calibration
                trust_result = modulate_confidence_with_signal_quality(
                    original_conf,
                    signal_quality,
                    metric_name=metric_type
                )
                
                # Add trust calibration to metric
                calibrated[metric_type]['trust_calibration'] = trust_result
                
                # Update effective confidence to trust score
                calibrated[metric_type]['effective_confidence'] = trust_result['trust_score']
        
        # Compute overall calibrated confidence
        calibrated_confidences = []
        for metric_type in metric_types:
            if metric_type in calibrated and 'effective_confidence' in calibrated[metric_type]:
                calibrated_confidences.append(calibrated[metric_type]['effective_confidence'])
        
        if calibrated_confidences:
            calibrated['overall_calibrated_confidence'] = np.mean(calibrated_confidences)
        else:
            calibrated['overall_calibrated_confidence'] = 0.0
        
        # Add overall trust summary
        calibrated['trust_summary'] = {
            'signal_quality_level': signal_quality['quality_level'],
            'signal_quality_score': signal_quality['signal_quality_score'],
            'calibration_applied': True,
            'trust_issues': signal_quality['trust_reasons'] if signal_quality['trust_reasons'] else None
        }
        
    except Exception as e:
        print(f"[WARNING] Trust calibration application failed: {e}")
        calibrated['trust_summary'] = {
            'signal_quality_level': 'unknown',
            'calibration_applied': False,
            'trust_issues': ["Calibration failed"]
        }
    
    return calibrated


def compute_confidence_statistics(features_df: pd.DataFrame, phase_data: dict = None) -> dict:
    """
    Compute confidence statistics (mean, std) for key biomechanical metrics.
    
    This helps assess measurement reliability and identify noisy/unstable metrics.
    Lower standard deviation indicates more stable and reliable measurements.
    
    Args:
        features_df: DataFrame with biomechanical features per frame
        phase_data: Optional phase segmentation data for phase-specific analysis
        
    Returns:
        Dictionary containing confidence statistics for each metric
    """
    key_metrics = [
        'left_shoulder_angle',
        'right_shoulder_angle',
        'left_elbow_angle',
        'right_elbow_angle',
        'left_knee_angle',
        'right_knee_angle',
        'hip_rotation',
        'spine_lean',
        'stance_width_normalized'
    ]
    
    confidence_stats = {}
    
    for metric in key_metrics:
        if metric in features_df.columns:
            values = features_df[metric].dropna()
            
            if len(values) > 0:
                confidence_stats[metric] = {
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'range': float(np.max(values) - np.min(values)),
                    'cv': float(np.std(values) / np.mean(values)) if np.mean(values) != 0 else 0.0  # Coefficient of variation
                }
    
    return confidence_stats


def assess_measurement_reliability(confidence_stats: dict) -> dict:
    """
    Assess measurement reliability based on confidence statistics.
    
    Classifies each metric as High/Medium/Low reliability based on 
    coefficient of variation (CV = std/mean).
    
    Args:
        confidence_stats: Dictionary from compute_confidence_statistics()
        
    Returns:
        Dictionary mapping metric names to reliability assessments
    """
    reliability = {}
    
    for metric, stats in confidence_stats.items():
        cv = stats['cv']
        std = stats['std']
        
        # For angles, also consider absolute std dev
        # Low CV and low std = High reliability
        # High CV or high std = Lower reliability
        
        if 'angle' in metric:
            # For angles: std < 10° is excellent, 10-20° is good, >20° is fair
            if std < 10.0:
                reliability[metric] = {
                    'level': 'High',
                    'description': 'Very stable measurement',
                    'cv': cv,
                    'std': std
                }
            elif std < 20.0:
                reliability[metric] = {
                    'level': 'Medium',
                    'description': 'Moderate variation',
                    'cv': cv,
                    'std': std
                }
            else:
                reliability[metric] = {
                    'level': 'Low',
                    'description': 'High variation - measurement may be noisy',
                    'cv': cv,
                    'std': std
                }
        else:
            # For other metrics (rotation, lean, width): use CV
            if cv < 0.15:  # CV < 15%
                reliability[metric] = {
                    'level': 'High',
                    'description': 'Very stable measurement',
                    'cv': cv,
                    'std': std
                }
            elif cv < 0.30:  # CV < 30%
                reliability[metric] = {
                    'level': 'Medium',
                    'description': 'Moderate variation',
                    'cv': cv,
                    'std': std
                }
            else:
                reliability[metric] = {
                    'level': 'Low',
                    'description': 'High variation - measurement may be noisy',
                    'cv': cv,
                    'std': std
                }
    
    return reliability


def compute_intra_phase_stability(features_df: pd.DataFrame, phase_data: dict) -> dict:
    """
    Compute stability metrics within each movement phase.
    
    Measures how consistent biomechanical metrics are within each phase.
    Lower variance indicates better technique repeatability and measurement stability.
    
    Args:
        features_df: DataFrame with biomechanical features
        phase_data: Phase segmentation data with start/end frames
        
    Returns:
        Dictionary with stability metrics per phase
    """
    if not phase_data:
        return {}
    
    key_metrics = [
        'left_shoulder_angle',
        'right_shoulder_angle',
        'left_elbow_angle',
        'right_elbow_angle',
        'hip_rotation',
        'spine_lean'
    ]
    
    stability = {}
    
    for phase_name, (start_frame, end_frame) in phase_data.items():
        phase_df = features_df.iloc[start_frame:end_frame+1]
        
        phase_stability = {}
        variance_scores = []
        
        for metric in key_metrics:
            if metric in phase_df.columns:
                values = phase_df[metric].dropna()
                
                if len(values) > 1:
                    std = float(np.std(values))
                    mean = float(np.mean(values))
                    
                    # Normalize variance (coefficient of variation)
                    cv = std / abs(mean) if mean != 0 else 0.0
                    
                    phase_stability[metric] = {
                        'std': std,
                        'cv': cv
                    }
                    
                    # Lower CV = better stability (inverse for scoring)
                    # Map CV to 0-100 scale (lower CV = higher score)
                    if cv < 0.1:
                        stability_score = 100.0
                    elif cv < 0.2:
                        stability_score = 90.0
                    elif cv < 0.3:
                        stability_score = 75.0
                    elif cv < 0.5:
                        stability_score = 60.0
                    else:
                        stability_score = 50.0
                    
                    variance_scores.append(stability_score)
        
        # Compute overall phase stability score
        if variance_scores:
            stability[phase_name] = {
                'metrics': phase_stability,
                'overall_score': float(np.mean(variance_scores))
            }
    
    return stability


def interpret_reliability_level(level: str) -> str:
    """
    Provide human-readable interpretation of reliability levels.
    
    Args:
        level: Reliability level (High/Medium/Low)
        
    Returns:
        Human-readable explanation
    """
    interpretations = {
        'High': '✓ Reliable - measurements are consistent and trustworthy',
        'Medium': '~ Moderate - some variation present but acceptable',
        'Low': '✗ Caution - high variation may affect accuracy'
    }
    return interpretations.get(level, 'Unknown reliability')

