"""
similarity.py

Technique similarity scoring (per-metric, per-phase) and coaching cues.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from vision.config_session import get_metrics_list, get_phase_weights
from vision.cue_templates import get_cue

def extract_phase_feature_vector(phase_metrics: dict, metric_keys: list = None) -> np.ndarray:
    """
    Extract normalized feature vector from phase biomechanical metrics.
    
    Args:
        phase_metrics: Dictionary of metrics for a single phase
        metric_keys: List of metric keys to include (defaults to key biomechanics)
        
    Returns:
        NumPy array of feature values (NaN replaced with 0)
    """
    if metric_keys is None:
        # Key biomechanical features for technique similarity
        metric_keys = [
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
    
    features = []
    for key in metric_keys:
        value = phase_metrics.get(key, np.nan)
        # Replace NaN with 0 for ML computation
        features.append(0.0 if np.isnan(value) else float(value))
    
    return np.array(features)


def compute_ml_phase_similarity(user_phase_metrics: dict, ref_phase_metrics: dict, config: dict = None) -> dict:
    """
    Compute per-phase technique-similarity scores against the reference.

    For each phase, every biomechanical metric is compared to the reference
    using a per-metric coaching tolerance: a deviation of one tolerance scores
    50%, two tolerances scores 0%, and a perfect match scores 100%. The phase
    score is the mean of the available per-metric similarities. Using a fixed
    per-metric tolerance makes metrics with different natural magnitudes (e.g. a
    ~150 deg elbow angle vs a ~1.0 normalized stance width) contribute
    comparably, which the previous scale-free approach failed to do.

    NOTE: This replaces an earlier implementation that fit a StandardScaler on a
    single sample. Standardizing one row forces every feature to zero, so both
    vectors collapsed and the cosine similarity always landed on the neutral
    ~50 default regardless of the input -- the score carried no signal. This
    model is consistent with compute_similarity_score(), which scores the
    impact frame the same way; here it is resolved per movement phase.

    Args:
        user_phase_metrics: User's phase-specific metrics
        ref_phase_metrics: Reference phase-specific metrics
        config: Optional configuration dictionary

    Returns:
        Dictionary: {phase_name: similarity_score (0-100) or None if no
        comparable metrics were available for that phase}
    """
    ml_similarities = {}

    # Get metrics list from config or use defaults
    metric_keys = get_metrics_list(config)

    # Per-metric coaching tolerances (degrees, or normalized units for stance).
    # Kept consistent with the tolerances in compute_similarity_score().
    metric_tolerances = {
        'left_shoulder_angle': 35.0,
        'right_shoulder_angle': 35.0,
        'left_elbow_angle': 30.0,
        'right_elbow_angle': 30.0,
        'left_knee_angle': 25.0,
        'right_knee_angle': 25.0,
        'hip_rotation': 20.0,
        'spine_lean': 15.0,
        'stance_width_normalized': 2.0,
    }
    default_tolerance = 30.0

    phase_names = ['preparation', 'load', 'contact', 'follow_through']

    for phase_name in phase_names:
        if phase_name not in user_phase_metrics or phase_name not in ref_phase_metrics:
            continue

        try:
            user_pm = user_phase_metrics[phase_name]
            ref_pm = ref_phase_metrics[phase_name]

            per_metric_sims = []
            for key in metric_keys:
                user_val = user_pm.get(key, np.nan)
                ref_val = ref_pm.get(key, np.nan)

                # Skip metrics missing from either side rather than treating a
                # missing value as 0 (which would fabricate a large deviation).
                if np.isnan(user_val) or np.isnan(ref_val):
                    continue

                tolerance = metric_tolerances.get(key, default_tolerance)
                deviation = abs(float(user_val) - float(ref_val))
                # 0 deviation -> 100, one tolerance -> 50, two tolerances -> 0
                similarity = max(0.0, 100.0 * (1.0 - deviation / (2.0 * tolerance)))
                per_metric_sims.append(similarity)

            if not per_metric_sims:
                # No comparable metrics for this phase -> no score (not a fake 50).
                ml_similarities[phase_name] = None
                continue

            ml_similarities[phase_name] = round(float(np.mean(per_metric_sims)), 1)

        except Exception as e:
            print(f"[WARNING] Phase similarity computation failed for {phase_name}: {e}")
            ml_similarities[phase_name] = None

    return ml_similarities


def compute_ml_overall_similarity(ml_phase_similarities: dict, 
                                  phase_weights: dict = None) -> float:
    """
    Compute weighted overall ML similarity score across all phases.
    
    Uses same biomechanical weighting as phase-weighted scoring for consistency.
    
    Args:
        ml_phase_similarities: Dictionary of phase similarity scores
        phase_weights: Optional custom weights (defaults to biomechanical importance)
        
    Returns:
        Overall similarity score (0-100)
    """
    if phase_weights is None:
        # Use same weights as phase_weighted_score for consistency
        phase_weights = {
            'preparation': 0.15,
            'load': 0.25,
            'contact': 0.35,
            'follow_through': 0.25
        }
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for phase_name, weight in phase_weights.items():
        if phase_name in ml_phase_similarities:
            score = ml_phase_similarities[phase_name]
            if score is not None:
                weighted_sum += score * weight
                total_weight += weight
    
    if total_weight > 0:
        return round(weighted_sum / total_weight, 1)
    else:
        return 50.0  # Default neutral score


def interpret_ml_similarity(score: float) -> str:
    """
    Interpret ML similarity score in human-readable terms.
    
    Args:
        score: ML similarity score (0-100)
        
    Returns:
        Human-readable interpretation
    """
    if score >= 85:
        return "Excellent match - your movement pattern closely resembles the professional technique"
    elif score >= 70:
        return "Good similarity - technique is on the right track with room for refinement"
    elif score >= 55:
        return "Moderate similarity - several aspects match but key differences remain"
    else:
        return "Significant differences - technique diverges from professional pattern"


def compute_similarity_score(user_metrics: dict, ref_metrics: dict, metric_weights: dict = None) -> float:
    """
    Compute similarity score (0-100) between user and reference metrics.
    
    Args:
        user_metrics: User's metrics dictionary
        ref_metrics: Reference metrics dictionary
        metric_weights: Optional weights for each metric (defaults to equal)
        
    Returns:
        Similarity score from 0 (very different) to 100 (identical)
    """
    if metric_weights is None:
        metric_weights = {
            'left_elbow_angle': 1.0,
            'right_elbow_angle': 1.0,
            'left_knee_angle': 1.0,
            'right_knee_angle': 1.0,
            'hip_rotation': 1.5,  # More important
            'spine_lean': 1.0,
            'stance_width_normalized': 1.2,
            'left_shoulder_angle': 0.8,
            'right_shoulder_angle': 0.8,
        }
    
    # Define acceptable deviation ranges (in degrees or normalized units)
    tolerance_ranges = {
        'left_elbow_angle': 30.0,
        'right_elbow_angle': 30.0,
        'left_knee_angle': 25.0,
        'right_knee_angle': 25.0,
        'hip_rotation': 20.0,
        'spine_lean': 15.0,
        'stance_width_normalized': 2.0,
        'left_shoulder_angle': 35.0,
        'right_shoulder_angle': 35.0,
    }
    
    similarities = []
    weights = []
    
    for metric, tolerance in tolerance_ranges.items():
        if metric in user_metrics and metric in ref_metrics:
            user_val = user_metrics[metric]
            ref_val = ref_metrics[metric]
            
            if not np.isnan(user_val) and not np.isnan(ref_val):
                # Calculate deviation
                deviation = abs(user_val - ref_val)
                
                # Convert to similarity score (0-100)
                # 0 deviation = 100, tolerance deviation = 50, 2*tolerance = 0
                similarity = max(0, 100 * (1 - deviation / (2 * tolerance)))
                
                similarities.append(similarity)
                weights.append(metric_weights.get(metric, 1.0))
    
    if not similarities:
        return 50.0  # Default middle score if no metrics available
    
    # Weighted average
    weighted_score = np.average(similarities, weights=weights)
    
    return round(weighted_score, 1)


def compute_phase_similarity_scores(user_phase_metrics: dict, ref_phase_metrics: dict) -> dict:
    """
    Compute similarity scores for each movement phase.
    
    Args:
        user_phase_metrics: User's phase-specific metrics
        ref_phase_metrics: Reference phase-specific metrics
        
    Returns:
        Dictionary: {phase_name: similarity_score}
    """
    phase_scores = {}
    
    for phase_name in ['preparation', 'load', 'contact', 'follow_through']:
        if phase_name in user_phase_metrics and phase_name in ref_phase_metrics:
            score = compute_similarity_score(
                user_phase_metrics[phase_name],
                ref_phase_metrics[phase_name]
            )
            phase_scores[phase_name] = score
    
    return phase_scores


def normalize_phase_timeline(features_df: pd.DataFrame, phases: dict) -> dict:
    """
    Normalize each movement phase to a 0-100% timeline.
    
    Args:
        features_df: Features DataFrame with frame column
        phases: Dictionary of phase boundaries {phase_name: (start_frame, end_frame)}
        
    Returns:
        Dictionary: {phase_name: DataFrame with 'phase_progress' column (0-100)}
    """
    normalized_phases = {}
    
    for phase_name, (start_frame, end_frame) in phases.items():
        # Extract phase data
        phase_data = features_df[
            (features_df['frame'] >= start_frame) & 
            (features_df['frame'] <= end_frame)
        ].copy()
        
        if len(phase_data) > 0:
            # Normalize to 0-100% timeline
            phase_duration = end_frame - start_frame
            if phase_duration > 0:
                phase_data['phase_progress'] = (
                    (phase_data['frame'] - start_frame) / phase_duration * 100
                )
            else:
                phase_data['phase_progress'] = 50.0  # Single frame
            
            normalized_phases[phase_name] = phase_data
    
    return normalized_phases


def compute_phase_consistency(normalized_phases: dict, metrics: list = None) -> dict:
    """
    Compute per-metric consistency (standard deviation) within each phase.
    Lower std dev = more consistent movement.
    
    Args:
        normalized_phases: Dictionary of phase DataFrames with normalized timelines
        metrics: List of metric names to analyze (defaults to key biomechanics)
        
    Returns:
        Dictionary: {phase_name: {metric: std_dev}}
    """
    if metrics is None:
        metrics = [
            'left_elbow_angle',
            'right_elbow_angle',
            'left_knee_angle',
            'right_knee_angle',
            'hip_rotation',
            'spine_lean',
            'stance_width_normalized'
        ]
    
    consistency_scores = {}
    
    for phase_name, phase_data in normalized_phases.items():
        phase_consistency = {}
        
        for metric in metrics:
            if metric in phase_data.columns:
                values = phase_data[metric].dropna()
                if len(values) > 1:
                    # Standard deviation as consistency measure
                    phase_consistency[metric] = float(values.std())
                else:
                    phase_consistency[metric] = 0.0
            else:
                phase_consistency[metric] = np.nan
        
        consistency_scores[phase_name] = phase_consistency
    
    return consistency_scores


def compute_phase_weighted_score(phase_scores: dict, config: dict = None,
                                 phase_weights: dict = None) -> float:
    """
    Compute phase-weighted overall score where contact and follow-through 
    have higher impact on final technique quality.
    
    Phase weights based on biomechanical importance (configurable):
    - Preparation: 15% (setup)
    - Load: 25% (energy storage)
    - Contact: 35% (ball impact - most critical)
    - Follow-through: 25% (power transfer and control)
    
    Args:
        phase_scores: Dictionary {phase_name: similarity_score}
        config: Optional configuration dictionary
        phase_weights: Explicit phase weights (e.g. stroke-specific). When
            provided, these take precedence over config-derived weights.

    Returns:
        Weighted average score (0-100)
    """
    # Explicit weights (e.g. stroke-aware) win; otherwise fall back to config.
    weights = phase_weights if phase_weights else get_phase_weights(config)
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for phase_name, weight in weights.items():
        if phase_name in phase_scores and not np.isnan(phase_scores[phase_name]):
            weighted_sum += phase_scores[phase_name] * weight
            total_weight += weight
    
    if total_weight > 0:
        return round(weighted_sum / total_weight, 1)
    else:
        return 50.0  # Default middle score


def interpret_consistency(std_dev: float, metric_type: str = 'angle') -> tuple:
    """
    Interpret consistency score (std dev) into quality rating.
    
    Args:
        std_dev: Standard deviation value
        metric_type: 'angle' or 'normalized' for different thresholds
        
    Returns:
        Tuple of (rating_text, quality_indicator)
    """
    if metric_type == 'angle':
        # Thresholds for angular metrics (degrees)
        if std_dev < 3.0:
            return "Excellent", "✓"
        elif std_dev < 6.0:
            return "Good", "~"
        elif std_dev < 10.0:
            return "Fair", "○"
        else:
            return "Inconsistent", "✗"
    else:
        # Thresholds for normalized metrics
        if std_dev < 0.1:
            return "Excellent", "✓"
        elif std_dev < 0.2:
            return "Good", "~"
        elif std_dev < 0.4:
            return "Fair", "○"
        else:
            return "Inconsistent", "✗"


def get_impact_metrics(features_df: pd.DataFrame, impact_frame: int, window: int = 3) -> dict:
    """
    Get average metrics around the impact frame.
    
    Args:
        features_df: Features DataFrame
        impact_frame: Detected impact frame number
        window: Number of frames before/after to average
        
    Returns:
        Dictionary of averaged metrics
    """
    # Get frames around impact
    mask = (features_df['frame'] >= impact_frame - window) & \
           (features_df['frame'] <= impact_frame + window)
    impact_data = features_df[mask]
    
    if impact_data.empty:
        impact_data = features_df
    
    metrics = {
        'left_shoulder_angle': impact_data['left_shoulder_angle'].mean(),
        'right_shoulder_angle': impact_data['right_shoulder_angle'].mean(),
        'left_elbow_angle': impact_data['left_elbow_angle'].mean(),
        'right_elbow_angle': impact_data['right_elbow_angle'].mean(),
        'left_knee_angle': impact_data['left_knee_angle'].mean(),
        'right_knee_angle': impact_data['right_knee_angle'].mean(),
        'hip_rotation': impact_data['hip_rotation'].mean(),
        'spine_lean': impact_data['spine_lean'].mean(),
        'stance_width_normalized': impact_data['stance_width_normalized'].mean(),
    }
    
    return metrics


def rank_cues_by_deviation(user_metrics: dict, ref_metrics: dict, 
                           user_phase_metrics: dict = None, 
                           ref_phase_metrics: dict = None,
                           stroke: str = 'backhand') -> list:
    """
    Rank potential coaching cues by metric deviation magnitude.
    
    Args:
        user_metrics: User's impact metrics
        ref_metrics: Reference impact metrics
        user_phase_metrics: Optional phase-specific user metrics
        ref_phase_metrics: Optional phase-specific reference metrics
        stroke: Stroke whose cue wording to use (see vision.cue_templates)
        
    Returns:
        List of tuples: (priority_score, cue_text, metric_name, deviation, phase)
    """
    cue_candidates = []
    cue = lambda key: get_cue(stroke, key)  # noqa: E731
    
    # Analyze impact metrics
    metrics_config = {
        'left_elbow_angle': {
            'weight': 2.0,
            'threshold': 15,
            'high': cue('left_elbow_angle.high'),
            'low': cue('left_elbow_angle.low')
        },
        'right_elbow_angle': {
            'weight': 2.0,
            'threshold': 15,
            'high': cue('right_elbow_angle.high'),
            'low': cue('right_elbow_angle.low')
        },
        'hip_rotation': {
            'weight': 2.5,
            'threshold': 5,
            'low_abs': cue('hip_rotation.low_abs'),
            'high_abs': cue('hip_rotation.high_abs')
        },
        'spine_lean': {
            'weight': 1.5,
            'threshold': 8,
            'high': cue('spine_lean.high'),
            'low': cue('spine_lean.low')
        },
        'stance_width_normalized': {
            'weight': 2.2,
            'threshold': 0.3,
            'low': cue('stance_width_normalized.low'),
            'high': cue('stance_width_normalized.high')
        }
    }
    
    # Knee bend (combined metric)
    if 'left_knee_angle' in user_metrics and 'right_knee_angle' in user_metrics:
        avg_user_knee = (user_metrics['left_knee_angle'] + user_metrics['right_knee_angle']) / 2
        avg_ref_knee = (ref_metrics['left_knee_angle'] + ref_metrics['right_knee_angle']) / 2
        knee_diff = avg_user_knee - avg_ref_knee
        
        if abs(knee_diff) > 15:
            deviation_score = abs(knee_diff) * 2.0  # weight
            if knee_diff > 0:
                cue_candidates.append((
                    deviation_score,
                    cue('knee_angle_avg.high'),
                    'knee_angle_avg',
                    knee_diff,
                    'contact'
                ))
            else:
                cue_candidates.append((
                    deviation_score,
                    cue('knee_angle_avg.low'),
                    'knee_angle_avg',
                    knee_diff,
                    'contact'
                ))
    
    # Process individual metrics
    for metric, config in metrics_config.items():
        if metric in user_metrics and metric in ref_metrics:
            user_val = user_metrics[metric]
            ref_val = ref_metrics[metric]
            diff = user_val - ref_val
            
            # Check if deviation exceeds threshold
            if 'low_abs' in config:  # Special handling for abs value metrics
                abs_diff = abs(user_val) - abs(ref_val)
                if abs_diff < -config['threshold']:
                    deviation_score = abs(abs_diff) * config['weight']
                    cue_candidates.append((
                        deviation_score,
                        config['low_abs'],
                        metric,
                        abs_diff,
                        'contact'
                    ))
                elif abs_diff > config['threshold'] * 2:
                    deviation_score = abs(abs_diff) * config['weight']
                    cue_candidates.append((
                        deviation_score,
                        config['high_abs'],
                        metric,
                        abs_diff,
                        'contact'
                    ))
            else:
                if abs(diff) > config['threshold']:
                    deviation_score = abs(diff) * config['weight']
                    if diff > 0 and 'high' in config:
                        cue_candidates.append((
                            deviation_score,
                            config['high'],
                            metric,
                            diff,
                            'contact'
                        ))
                    elif diff < 0 and 'low' in config:
                        cue_candidates.append((
                            deviation_score,
                            config['low'],
                            metric,
                            diff,
                            'contact'
                        ))
    
    # Add phase-specific cues with their priority
    if user_phase_metrics and ref_phase_metrics:
        phase_cues = get_phase_cues_with_priority(user_phase_metrics, ref_phase_metrics, stroke=stroke)
        cue_candidates.extend(phase_cues)
    
    # Sort by priority score (descending)
    cue_candidates.sort(key=lambda x: x[0], reverse=True)
    
    return cue_candidates


def get_phase_cues_with_priority(user_phases: dict, ref_phases: dict,
                                 stroke: str = 'backhand') -> list:
    """
    Get phase-specific cues with priority scores.
    
    Returns:
        List of tuples: (priority_score, cue_text, metric_name, deviation, phase)
    """
    cues = []
    cue = lambda key: get_cue(stroke, key)  # noqa: E731
    
    # Preparation phase
    if 'preparation' in user_phases and 'preparation' in ref_phases:
        user_prep = user_phases['preparation']
        ref_prep = ref_phases['preparation']
        
        # Shoulder rotation in prep
        shoulder_diff = abs(user_prep.get('left_shoulder_angle', 0) - ref_prep.get('left_shoulder_angle', 0))
        if shoulder_diff > 25:
            cues.append((
                shoulder_diff * 1.5,
                cue('preparation.shoulder'),
                'left_shoulder_angle',
                shoulder_diff,
                'preparation'
            ))
        
        # Stance width in prep
        stance_diff = user_prep.get('stance_width_normalized', 0) - ref_prep.get('stance_width_normalized', 0)
        if stance_diff < -0.5:
            cues.append((
                abs(stance_diff) * 25,  # High weight for stance
                cue('preparation.stance'),
                'stance_width_normalized',
                stance_diff,
                'preparation'
            ))
    
    # Load phase
    if 'load' in user_phases and 'load' in ref_phases:
        user_load = user_phases['load']
        ref_load = ref_phases['load']
        
        # Hip rotation in load
        hip_diff = abs(user_load.get('hip_rotation', 0)) - abs(ref_load.get('hip_rotation', 0))
        if hip_diff < -8:
            cues.append((
                abs(hip_diff) * 3.0,  # Very high weight
                cue('load.hip'),
                'hip_rotation',
                hip_diff,
                'load'
            ))
        
        # Knee bend in load
        user_knee_avg = (user_load.get('left_knee_angle', 180) + user_load.get('right_knee_angle', 180)) / 2
        ref_knee_avg = (ref_load.get('left_knee_angle', 180) + ref_load.get('right_knee_angle', 180)) / 2
        if user_knee_avg - ref_knee_avg > 20:
            cues.append((
                abs(user_knee_avg - ref_knee_avg) * 1.8,
                cue('load.knee'),
                'knee_angle_avg',
                user_knee_avg - ref_knee_avg,
                'load'
            ))
    
    # Follow-through phase
    if 'follow_through' in user_phases and 'follow_through' in ref_phases:
        user_follow = user_phases['follow_through']
        ref_follow = ref_phases['follow_through']
        
        # Elbow extension in follow-through
        user_elbow_ext = user_follow.get('left_elbow_angle', 0)
        ref_elbow_ext = ref_follow.get('left_elbow_angle', 0)
        if user_elbow_ext < ref_elbow_ext - 20:
            cues.append((
                abs(user_elbow_ext - ref_elbow_ext) * 1.2,
                cue('follow_through.elbow'),
                'left_elbow_angle',
                user_elbow_ext - ref_elbow_ext,
                'follow_through'
            ))
        
        # Balance in follow-through
        spine_diff = user_follow.get('spine_lean', 0) - ref_follow.get('spine_lean', 0)
        if abs(spine_diff) > 10:
            cues.append((
                abs(spine_diff) * 1.3,
                cue('follow_through.spine'),
                'spine_lean',
                spine_diff,
                'follow_through'
            ))
    
    return cues


def generate_coaching_cues(user_metrics: dict, ref_metrics: dict, 
                          user_phase_metrics: dict = None, 
                          ref_phase_metrics: dict = None,
                          limit_primary: int = 2,
                          stroke: str = 'backhand') -> tuple:
    """
    Generate coaching cues based on metric differences, ranked by priority.
    
    Args:
        user_metrics: User's impact metrics
        ref_metrics: Reference impact metrics
        user_phase_metrics: Optional phase-specific user metrics
        ref_phase_metrics: Optional phase-specific reference metrics
        limit_primary: Number of top-priority cues for primary focus
        
    Returns:
        Tuple of (primary_cues, all_ranked_cues)
    """
    # Get all cues ranked by deviation magnitude
    ranked_cues = rank_cues_by_deviation(
        user_metrics, ref_metrics, 
        user_phase_metrics, ref_phase_metrics,
        stroke=stroke,
    )
    
    # Extract just the cue text
    all_cues = [cue[1] for cue in ranked_cues]
    
    # Top priority cues for "Today's Focus"
    primary_cues = all_cues[:limit_primary]
    
    # Ensure we have at least minimum cues
    if len(all_cues) < 3:
        fallback_cues = [get_cue(stroke, 'fallback.1'), get_cue(stroke, 'fallback.2'),
                         get_cue(stroke, 'fallback.3')]
        for fallback in fallback_cues:
            if len(all_cues) >= 5:
                break
            if fallback not in all_cues:
                all_cues.append(fallback)
    
    return primary_cues, all_cues[:5], ranked_cues  # Return top 5 total cues


def generate_drills(user_metrics: dict, ref_metrics: dict, stroke: str = 'backhand') -> list:
    """
    Generate drill suggestions based on identified weaknesses.
    
    Args:
        user_metrics: User's impact metrics
        ref_metrics: Reference impact metrics
        stroke: Stroke whose drill wording to use (see vision.cue_templates)
        
    Returns:
        List of drill descriptions
    """
    drills = []
    cue = lambda key: get_cue(stroke, key)  # noqa: E731
    
    # Knee bend drill
    avg_user_knee = (user_metrics['left_knee_angle'] + user_metrics['right_knee_angle']) / 2
    avg_ref_knee = (ref_metrics['left_knee_angle'] + ref_metrics['right_knee_angle']) / 2
    
    if avg_user_knee - avg_ref_knee > 10:
        drills.append(cue('drill.knee'))
    
    # Hip rotation drill
    hip_diff = abs(user_metrics['hip_rotation']) - abs(ref_metrics['hip_rotation'])
    if hip_diff < -3:
        drills.append(cue('drill.hip'))
    
    # Balance/stance drill
    stance_diff = user_metrics['stance_width_normalized'] - ref_metrics['stance_width_normalized']
    if abs(stance_diff) > 0.2:
        drills.append(cue('drill.stance'))
    
    # General two-handed backhand drills
    if len(drills) < 2:
        drills.append(cue('drill.general_1'))
    
    if len(drills) < 2:
        drills.append(cue('drill.general_2'))
    
    return drills[:2]

