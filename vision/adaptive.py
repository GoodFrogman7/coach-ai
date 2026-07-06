"""
adaptive.py

Adaptive coaching: issue prioritization and classification.

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

def compute_issue_priority_score(
    metric_name: str,
    deviation: float,
    phase: str,
    reliability_level: str = 'Medium',
    phase_stability_score: float = 75.0,
    progress_delta: float = 0.0
) -> dict:
    """
    Compute a priority score for a coaching issue based on multiple factors.
    
    Priority factors:
    1. Severity: How far from reference (deviation magnitude)
    2. Reliability: How trustworthy is the measurement
    3. Consistency: How stable within the phase
    4. Progress: Is it improving or getting worse
    
    Args:
        metric_name: Name of the biomechanical metric
        deviation: Deviation from reference
        phase: Movement phase where issue occurs
        reliability_level: Measurement reliability (High/Medium/Low)
        phase_stability_score: Intra-phase stability (0-100)
        progress_delta: Change from previous session (negative = improving)
        
    Returns:
        Dictionary with priority score and component breakdowns
    """
    priority_score = 0.0
    components = {}
    
    # 1. Severity Score (0-40 points) - based on deviation magnitude
    abs_deviation = abs(deviation)
    
    if 'angle' in metric_name.lower() or 'rotation' in metric_name.lower():
        # For angles: large deviations are more severe
        if abs_deviation >= 80:
            severity = 40.0
        elif abs_deviation >= 50:
            severity = 35.0
        elif abs_deviation >= 30:
            severity = 30.0
        elif abs_deviation >= 20:
            severity = 20.0
        elif abs_deviation >= 10:
            severity = 10.0
        else:
            severity = 5.0
    else:
        # For normalized metrics
        if abs_deviation >= 4.0:
            severity = 40.0
        elif abs_deviation >= 3.0:
            severity = 30.0
        elif abs_deviation >= 2.0:
            severity = 20.0
        elif abs_deviation >= 1.0:
            severity = 10.0
        else:
            severity = 5.0
    
    components['severity'] = severity
    priority_score += severity
    
    # 2. Reliability Weight (0-25 points) - higher reliability = higher priority
    reliability_weights = {
        'High': 25.0,
        'Medium': 15.0,
        'Low': 5.0
    }
    reliability_points = reliability_weights.get(reliability_level, 15.0)
    components['reliability'] = reliability_points
    priority_score += reliability_points
    
    # 3. Phase Importance (0-20 points) - contact and load are critical
    phase_weights = {
        'contact': 20.0,
        'load': 15.0,
        'follow_through': 12.0,
        'preparation': 8.0
    }
    phase_points = phase_weights.get(phase.lower(), 10.0)
    components['phase_importance'] = phase_points
    priority_score += phase_points
    
    # 4. Consistency Penalty (0-15 points) - low stability reduces priority
    # Higher stability = higher priority (issue is consistent, not random noise)
    consistency_points = (phase_stability_score / 100.0) * 15.0
    components['consistency'] = consistency_points
    priority_score += consistency_points
    
    # 5. Progress Modifier (-10 to +10 points)
    # Getting worse = higher priority
    # Improving = lower priority
    if progress_delta > 5.0:  # Getting worse
        progress_mod = min(10.0, progress_delta)
    elif progress_delta < -5.0:  # Improving
        progress_mod = max(-10.0, progress_delta)
    else:
        progress_mod = 0.0
    
    components['progress_modifier'] = progress_mod
    priority_score += progress_mod
    
    return {
        'total_score': priority_score,
        'components': components,
        'severity': severity,
        'reliability': reliability_points,
        'phase_importance': phase_points,
        'consistency': consistency_points,
        'progress_modifier': progress_mod
    }


def classify_coaching_issue(
    metric_name: str,
    current_deviation: float,
    reliability_level: str,
    progress_delta: float = None,
    phase_stability: float = 75.0
) -> dict:
    """
    Classify a coaching issue for adaptive recommendations.
    
    Classifications:
    - CRITICAL: High severity + high reliability + persistent
    - PRIORITY: Moderate severity + reliable measurement
    - MONITOR: Improving or low reliability but still present
    - SUPPRESS: Low reliability or actively improving
    
    Args:
        metric_name: Name of metric
        current_deviation: Current deviation from reference
        reliability_level: Measurement reliability
        progress_delta: Change from previous session (if available)
        phase_stability: Stability score within phase
        
    Returns:
        Classification dictionary
    """
    abs_dev = abs(current_deviation)
    
    # Determine severity level
    is_severe = abs_dev >= 50 if 'angle' in metric_name.lower() else abs_dev >= 3.0
    is_moderate = abs_dev >= 20 if 'angle' in metric_name.lower() else abs_dev >= 1.5
    
    # Check reliability
    is_reliable = reliability_level in ['High', 'Medium']
    
    # Check progress
    is_improving = progress_delta is not None and progress_delta < -5.0
    is_worsening = progress_delta is not None and progress_delta > 5.0
    
    # Check consistency
    is_consistent = phase_stability >= 70.0
    
    # Classification logic
    if is_severe and reliability_level == 'High' and is_consistent:
        if is_worsening:
            classification = 'CRITICAL'
            recommendation = 'Address immediately - severe issue getting worse'
        else:
            classification = 'CRITICAL'
            recommendation = 'Address immediately - severe and consistent issue'
    elif is_severe and is_reliable:
        classification = 'PRIORITY'
        recommendation = 'Focus on this - significant deviation from pro technique'
    elif is_moderate and is_reliable and not is_improving:
        classification = 'PRIORITY'
        recommendation = 'Important area for improvement'
    elif is_improving and is_reliable:
        classification = 'MONITOR'
        recommendation = 'Continue current approach - showing improvement'
    elif reliability_level == 'Low' and not is_severe:
        classification = 'SUPPRESS'
        recommendation = 'Low measurement confidence - may not be actionable'
    elif is_moderate and reliability_level == 'Low':
        classification = 'MONITOR'
        recommendation = 'Verify measurement quality before focusing on this'
    else:
        classification = 'MONITOR'
        recommendation = 'Track progress - minor issue or improving'
    
    return {
        'classification': classification,
        'recommendation': recommendation,
        'is_severe': is_severe,
        'is_reliable': is_reliable,
        'is_improving': is_improving,
        'is_worsening': is_worsening,
        'is_consistent': is_consistent
    }


def generate_adaptive_coaching_focus(
    ranked_cues: list,
    user_reliability: dict = None,
    user_phase_stability: dict = None,
    progress_deltas: dict = None
) -> dict:
    """
    Generate adaptive coaching recommendations based on priority scores.
    
    Uses severity, reliability, consistency, and progress to intelligently
    prioritize coaching cues and suppress low-value recommendations.
    
    Args:
        ranked_cues: List of ranked coaching cues (metric, deviation, phase, etc.)
        user_reliability: Reliability assessment for each metric
        user_phase_stability: Stability scores per phase
        progress_deltas: Progress tracking from previous session
        
    Returns:
        Dictionary with adaptive recommendations
    """
    adaptive_cues = []
    
    for cue_data in ranked_cues:
        # Extract cue information
        cue_text = cue_data[0]
        phase_name = cue_data[1]
        metric_name = cue_data[2]
        deviation = cue_data[3]
        phase = cue_data[4]
        
        # Get reliability level
        reliability_level = 'Medium'  # default
        if user_reliability and metric_name in user_reliability:
            reliability_level = user_reliability[metric_name]['level']
        
        # Get phase stability
        phase_stability = 75.0  # default
        if user_phase_stability and phase in user_phase_stability:
            phase_stability = user_phase_stability[phase]['overall_score']
        
        # Get progress delta for this metric
        progress_delta = 0.0
        if progress_deltas and 'phase_scores' in progress_deltas:
            # Check if this phase has progress data
            if phase in progress_deltas['phase_scores']:
                progress_delta = progress_deltas['phase_scores'][phase]['delta']
        
        # Compute priority score
        priority_data = compute_issue_priority_score(
            metric_name=metric_name,
            deviation=deviation,
            phase=phase,
            reliability_level=reliability_level,
            phase_stability_score=phase_stability,
            progress_delta=progress_delta
        )
        
        # Classify issue
        classification_data = classify_coaching_issue(
            metric_name=metric_name,
            current_deviation=deviation,
            reliability_level=reliability_level,
            progress_delta=progress_delta,
            phase_stability=phase_stability
        )
        
        adaptive_cues.append({
            'cue_text': cue_text,
            'metric': metric_name,
            'phase': phase,
            'deviation': deviation,
            'priority_score': priority_data['total_score'],
            'priority_components': priority_data['components'],
            'classification': classification_data['classification'],
            'recommendation': classification_data['recommendation'],
            'reliability': reliability_level,
            'phase_stability': phase_stability,
            'progress_delta': progress_delta
        })
    
    # Sort by priority score (highest first)
    adaptive_cues.sort(key=lambda x: x['priority_score'], reverse=True)
    
    # Separate by classification
    critical_issues = [c for c in adaptive_cues if c['classification'] == 'CRITICAL']
    priority_issues = [c for c in adaptive_cues if c['classification'] == 'PRIORITY']
    monitor_issues = [c for c in adaptive_cues if c['classification'] == 'MONITOR']
    suppressed_issues = [c for c in adaptive_cues if c['classification'] == 'SUPPRESS']
    
    return {
        'all_adaptive_cues': adaptive_cues,
        'critical': critical_issues,
        'priority': priority_issues,
        'monitor': monitor_issues,
        'suppressed': suppressed_issues,
        'top_3': adaptive_cues[:3] if len(adaptive_cues) >= 3 else adaptive_cues
    }

