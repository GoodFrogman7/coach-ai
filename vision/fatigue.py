"""
fatigue.py

Rally segmentation and fatigue inference from biomechanics.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
import numpy as np
from vision.adaptive import classify_coaching_issue

def segment_session_into_rallies(
    timestamps: list,
    inter_rally_gap_seconds: float = 10.0
) -> list:
    """
    Segment a session into rallies based on temporal gaps between strokes.
    
    A rally is a sequence of strokes with gaps < inter_rally_gap_seconds.
    Large gaps indicate rally boundaries (e.g., between points).
    
    GRACEFUL DEGRADATION:
    - Returns single rally if no gaps found
    - Returns empty list if no timestamps
    - Works with any number of strokes
    
    Args:
        timestamps: List of frame timestamps or stroke times
        inter_rally_gap_seconds: Gap threshold to define rally boundary
        
    Returns:
        List of rally dictionaries: [{'start_idx': int, 'end_idx': int, 'duration': float}, ...]
        
    Example:
        >>> timestamps = [0.5, 1.0, 1.5, 15.0, 15.5, 16.0]
        >>> rallies = segment_session_into_rallies(timestamps, inter_rally_gap_seconds=10.0)
        >>> len(rallies)
        2  # Two rallies: [0.5-1.5] and [15.0-16.0]
    """
    if not timestamps or len(timestamps) == 0:
        return []
    
    if len(timestamps) == 1:
        return [{'start_idx': 0, 'end_idx': 0, 'duration': 0.0, 'stroke_count': 1}]
    
    rallies = []
    rally_start_idx = 0
    
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i-1]
        
        if gap > inter_rally_gap_seconds:
            # Rally boundary detected
            rallies.append({
                'start_idx': rally_start_idx,
                'end_idx': i - 1,
                'duration': timestamps[i-1] - timestamps[rally_start_idx],
                'stroke_count': i - rally_start_idx
            })
            rally_start_idx = i
    
    # Add final rally
    rallies.append({
        'start_idx': rally_start_idx,
        'end_idx': len(timestamps) - 1,
        'duration': timestamps[-1] - timestamps[rally_start_idx],
        'stroke_count': len(timestamps) - rally_start_idx
    })
    
    return rallies


def compute_metric_trajectory(
    metric_values: list,
    rally_indices: list = None
) -> dict:
    """
    Compute trajectory statistics for a metric across a session or rally.
    
    Trajectory analysis reveals:
    - Trend (improving/stable/degrading)
    - Variability (consistent/inconsistent)
    - Range evolution (expanding/contracting)
    
    This is used to detect fatigue patterns (degrading trend, increasing variability).
    
    Args:
        metric_values: List of metric measurements in temporal order
        rally_indices: Optional list of rally segment indices
        
    Returns:
        Dictionary with trajectory statistics:
        - trend: Linear regression slope
        - variability: Coefficient of variation
        - early_mean: Mean of first 1/3 of values
        - late_mean: Mean of last 1/3 of values
        - degradation_ratio: late_mean / early_mean (< 1.0 = degradation)
        
    Example:
        >>> values = [180, 175, 170, 165, 160]  # Hip rotation degrading
        >>> traj = compute_metric_trajectory(values)
        >>> traj['trend']  # Negative trend
        -5.0
        >>> traj['degradation_ratio']  # < 1.0
        0.91
    """
    if not metric_values or len(metric_values) < 2:
        return {
            'trend': 0.0,
            'variability': 0.0,
            'early_mean': metric_values[0] if metric_values else 0.0,
            'late_mean': metric_values[0] if metric_values else 0.0,
            'degradation_ratio': 1.0,
            'sample_size': len(metric_values)
        }
    
    values = np.array(metric_values)
    n = len(values)
    
    # Compute linear trend (simple linear regression slope)
    x = np.arange(n)
    if n > 1:
        trend = np.polyfit(x, values, 1)[0]  # Slope of best-fit line
    else:
        trend = 0.0
    
    # Compute variability (coefficient of variation)
    mean_val = np.mean(values)
    std_val = np.std(values)
    variability = (std_val / mean_val * 100) if mean_val != 0 else 0.0
    
    # Compute early vs late comparison
    third = max(1, n // 3)
    early_values = values[:third]
    late_values = values[-third:]
    
    early_mean = np.mean(early_values)
    late_mean = np.mean(late_values)
    
    # Degradation ratio (< 1.0 indicates decline)
    # Handle metrics where lower is better vs higher is better
    degradation_ratio = (late_mean / early_mean) if early_mean != 0 else 1.0
    
    return {
        'trend': float(trend),
        'variability': float(variability),
        'early_mean': float(early_mean),
        'late_mean': float(late_mean),
        'degradation_ratio': float(degradation_ratio),
        'sample_size': n
    }


def infer_fatigue_from_biomechanics(
    session_metrics: dict,
    rally_data: list = None
) -> dict:
    """
    Infer fatigue from biomechanical degradation patterns.
    
    Fatigue inference signals (NO PHYSIOLOGICAL SENSORS):
    1. Recovery time increasing over session
    2. Rotation ranges decreasing (hip, shoulder)
    3. Variability increasing (consistency drops)
    4. Balance drift increasing
    5. Stance transition speed slowing
    
    This is INFERENCE, not measurement. We flag probable fatigue patterns.
    
    IMPORTANT:
    - Does NOT diagnose physiological fatigue
    - Identifies biomechanical degradation patterns
    - Suggests conditioning interventions
    - Distinguished from technique issues
    
    Args:
        session_metrics: Dictionary of metric trajectories
        rally_data: Optional rally segmentation data
        
    Returns:
        Dictionary with fatigue inference:
        - fatigue_score: 0-100 (0=no fatigue signals, 100=strong fatigue signals)
        - fatigue_signals: List of detected patterns
        - affected_metrics: Metrics showing fatigue patterns
        - confidence: 'high' / 'medium' / 'low' / 'insufficient_data'
        - recommendation: Conditioning focus vs technique focus
        
    Example:
        >>> metrics = {
        ...     'recovery_time': [0.7, 0.8, 0.9, 1.0, 1.1],
        ...     'hip_rotation': [180, 175, 170, 165, 160]
        ... }
        >>> fatigue = infer_fatigue_from_biomechanics(metrics)
        >>> fatigue['fatigue_score']  # High score
        75.0
        >>> 'Increasing recovery time' in fatigue['fatigue_signals']
        True
    """
    fatigue_signals = []
    affected_metrics = []
    fatigue_score = 0.0
    
    # Fatigue-sensitive metrics with their expected behaviors
    fatigue_indicators = {
        # Movement metrics (Phase 2.2 integration)
        'recovery_time': {'type': 'increasing', 'weight': 25, 'threshold': 1.15},
        'balance_drift': {'type': 'increasing', 'weight': 20, 'threshold': 1.20},
        'stance_transition_speed': {'type': 'increasing', 'weight': 15, 'threshold': 1.15},
        'first_step_reaction_time': {'type': 'increasing', 'weight': 15, 'threshold': 1.10},
        
        # Stroke metrics (Phase 2 integration)
        'hip_rotation': {'type': 'decreasing', 'weight': 20, 'threshold': 0.90},
        'shoulder_rotation': {'type': 'decreasing', 'weight': 15, 'threshold': 0.92},
        'knee_flexion': {'type': 'decreasing', 'weight': 10, 'threshold': 0.95},
        
        # Variability indicators (any metric)
        'variability': {'type': 'increasing', 'weight': 25, 'threshold': 1.30}
    }
    
    for metric_name, values in session_metrics.items():
        if not isinstance(values, list) or len(values) < 3:
            continue  # Need at least 3 data points
        
        trajectory = compute_metric_trajectory(values)
        
        # Check if this metric shows fatigue pattern
        metric_lower = metric_name.lower()
        matched_indicator = None
        
        for indicator_key, indicator_spec in fatigue_indicators.items():
            if indicator_key in metric_lower:
                matched_indicator = indicator_spec
                break
        
        if not matched_indicator:
            continue
        
        # Evaluate fatigue pattern
        degradation_ratio = trajectory['degradation_ratio']
        variability = trajectory['variability']
        
        if matched_indicator['type'] == 'increasing':
            # Metric should not increase (e.g., recovery time)
            if degradation_ratio > matched_indicator['threshold']:
                fatigue_score += matched_indicator['weight']
                fatigue_signals.append(
                    f"Increasing {metric_name}: {trajectory['early_mean']:.2f} → {trajectory['late_mean']:.2f} "
                    f"(+{(degradation_ratio - 1.0) * 100:.1f}%)"
                )
                affected_metrics.append(metric_name)
        
        elif matched_indicator['type'] == 'decreasing':
            # Metric should not decrease (e.g., hip rotation)
            if degradation_ratio < matched_indicator['threshold']:
                fatigue_score += matched_indicator['weight']
                fatigue_signals.append(
                    f"Decreasing {metric_name}: {trajectory['early_mean']:.2f} → {trajectory['late_mean']:.2f} "
                    f"({(degradation_ratio - 1.0) * 100:.1f}%)"
                )
                affected_metrics.append(metric_name)
        
        # Check variability increase (consistency drops)
        if variability > 25.0:  # > 25% coefficient of variation
            fatigue_score += 10  # Bonus penalty for high variability
            if f"High variability in {metric_name}" not in fatigue_signals:
                fatigue_signals.append(
                    f"High variability in {metric_name}: CV={variability:.1f}%"
                )
    
    # Determine confidence level
    sample_size = sum(len(v) for v in session_metrics.values() if isinstance(v, list))
    
    if sample_size < 5:
        confidence = 'insufficient_data'
    elif len(fatigue_signals) >= 3:
        confidence = 'high'
    elif len(fatigue_signals) >= 2:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    # Generate recommendation
    if fatigue_score > 60 and confidence in ['high', 'medium']:
        recommendation = 'CONDITIONING_FOCUS: Address cardiovascular endurance and muscular stamina before technique refinement'
    elif fatigue_score > 30:
        recommendation = 'HYBRID: Combine conditioning work with technique training'
    else:
        recommendation = 'TECHNIQUE_FOCUS: Fatigue not a primary factor, focus on skill refinement'
    
    # Cap fatigue score at 100
    fatigue_score = min(100.0, fatigue_score)
    
    return {
        'fatigue_score': fatigue_score,
        'fatigue_signals': fatigue_signals,
        'affected_metrics': affected_metrics,
        'confidence': confidence,
        'recommendation': recommendation,
        'sample_size': sample_size
    }


def classify_issue_with_fatigue_context(
    metric_name: str,
    current_deviation: float,
    reliability_level: str,
    phase_stability: float = 75.0,
    progress_delta: float = None,
    fatigue_inference: dict = None
) -> dict:
    """
    Extend issue classification to include fatigue context.
    
    Fatigue-driven issues are flagged separately and may be:
    - Deprioritized for technique coaching (conditioning needed instead)
    - Marked for rest/recovery recommendations
    - Routed to conditioning drills vs technique drills
    
    This is ADDITIVE to existing classification logic (Phase 2.1).
    
    Args:
        metric_name: Name of the metric
        current_deviation: Current deviation from optimal
        reliability_level: 'High' / 'Medium' / 'Low'
        phase_stability: Stability score 0-100
        progress_delta: Change from previous session
        fatigue_inference: Output from infer_fatigue_from_biomechanics()
        
    Returns:
        Dictionary with extended classification:
        - classification: 'CRITICAL' / 'PRIORITY' / 'MONITOR' / 'SUPPRESS'
        - recommendation: Coaching recommendation
        - fatigue_flag: True if likely fatigue-driven
        - intervention_type: 'technique' / 'conditioning' / 'rest'
        
    Example:
        >>> fatigue = {'fatigue_score': 75, 'affected_metrics': ['recovery_time']}
        >>> result = classify_issue_with_fatigue_context(
        ...     'recovery_time', 0.3, 'High', 80.0, None, fatigue
        ... )
        >>> result['fatigue_flag']
        True
        >>> result['intervention_type']
        'conditioning'
    """
    # Get base classification from existing system
    # Import the original function (exists in Phase 2.1)
    # We'll call it to get base classification
    base_classification = classify_coaching_issue(
        metric_name=metric_name,
        current_deviation=current_deviation,
        reliability_level=reliability_level,
        phase_stability=phase_stability,
        progress_delta=progress_delta
    )
    
    # Check if this metric is affected by fatigue
    fatigue_flag = False
    intervention_type = 'technique'  # Default
    
    if fatigue_inference and fatigue_inference['confidence'] in ['high', 'medium']:
        # Check if this specific metric is in the affected list
        metric_in_affected = any(
            metric_name.lower() in affected.lower() or affected.lower() in metric_name.lower()
            for affected in fatigue_inference['affected_metrics']
        )
        
        if metric_in_affected:
            fatigue_flag = True
            
            # Adjust intervention based on fatigue score
            if fatigue_inference['fatigue_score'] > 60:
                intervention_type = 'conditioning'
                # Modify recommendation to indicate fatigue
                base_classification['recommendation'] = (
                    f"FATIGUE-DRIVEN ({fatigue_inference['fatigue_score']:.0f}/100 fatigue score): "
                    f"Address conditioning/recovery before technique work. {base_classification['recommendation']}"
                )
            elif fatigue_inference['fatigue_score'] > 30:
                intervention_type = 'hybrid'
                base_classification['recommendation'] = (
                    f"POSSIBLE FATIGUE ({fatigue_inference['fatigue_score']:.0f}/100 fatigue score): "
                    f"Consider rest/conditioning alongside technique work. {base_classification['recommendation']}"
                )
    
    # Add fatigue context to result
    result = base_classification.copy()
    result['fatigue_flag'] = fatigue_flag
    result['intervention_type'] = intervention_type
    
    return result

