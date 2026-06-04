"""
compare.py
Full pipeline for comparing user video against reference video.
Generates overlay videos, feature CSVs, and coaching report.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

# Optional: PyYAML for configuration support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from vision.extract_pose import extract_pose_landmarks, save_landmarks
from vision.overlay_pose import create_overlay_video
from vision.features import (
    compute_features_from_landmarks,
    compute_wrist_speed,
    save_features,
    segment_stroke_phases,
    compute_phase_metrics
)


# ============================================================================
# Stroke Abstraction Layer (Phase 2: Multi-Stroke Intelligence Foundation)
# ============================================================================

"""
The Stroke Abstraction Layer enables Coach AI to analyze multiple tennis strokes
(backhand, forehand, serve, volley, overhead) by providing stroke-specific
biomechanical context.

WHY THIS EXISTS:
- Different strokes have different optimal biomechanical ranges
- E.g., forehand hip rotation is typically larger than backhand
- E.g., serve elbow extension is intentionally different than groundstrokes
- Universal thresholds would misclassify stroke-specific technique

HOW IT WORKS:
- Defines expected ranges per metric per stroke
- Provides fallback to backhand defaults (100% backward compatibility)
- Integrates only at threshold interpretation (no changes to core logic)

FUTURE VISION:
This foundational layer enables:
- Multi-stroke video analysis
- Stroke-specific drill recommendations
- Cross-stroke technique comparison
- Full tennis game intelligence
"""

# Stroke profile definitions
# Each profile specifies expected biomechanical ranges and intent
STROKE_PROFILES = {
    'backhand': {
        'name': 'Two-Handed Backhand',
        'description': 'Baseline two-handed backhand stroke',
        'biomechanical_intent': {
            'hip_rotation': {
                'expected_range': (150, 220),  # degrees
                'rationale': 'Hip coiling provides power generation'
            },
            'elbow_angle': {
                'expected_range': (90, 140),  # degrees
                'rationale': 'Compact arm structure for control'
            },
            'knee_flexion': {
                'expected_range': (150, 170),  # degrees
                'rationale': 'Athletic stance with slight bend'
            },
            'spine_lean': {
                'expected_range': (-10, 15),  # degrees (negative = backward)
                'rationale': 'Upright to slightly forward posture'
            }
        },
        'phase_emphasis': {
            'preparation': 0.15,
            'load': 0.25,
            'contact': 0.35,  # Most critical
            'follow_through': 0.25
        }
    },
    
    'forehand': {
        'name': 'Forehand',
        'description': 'Baseline forehand stroke',
        'biomechanical_intent': {
            'hip_rotation': {
                'expected_range': (180, 270),  # Larger than backhand
                'rationale': 'Greater hip rotation for power on dominant side'
            },
            'elbow_angle': {
                'expected_range': (100, 160),  # More extension
                'rationale': 'Longer lever arm for forehand mechanics'
            },
            'knee_flexion': {
                'expected_range': (150, 175),
                'rationale': 'Similar stance to backhand'
            },
            'spine_lean': {
                'expected_range': (-5, 20),  # More forward lean
                'rationale': 'Aggressive forward posture for forehand'
            }
        },
        'phase_emphasis': {
            'preparation': 0.15,
            'load': 0.30,  # More load emphasis
            'contact': 0.35,
            'follow_through': 0.20
        }
    },
    
    'serve': {
        'name': 'Serve',
        'description': 'First or second serve',
        'biomechanical_intent': {
            'hip_rotation': {
                'expected_range': (200, 300),  # Maximum rotation
                'rationale': 'Full body rotation for serve power'
            },
            'elbow_angle': {
                'expected_range': (140, 180),  # Near full extension
                'rationale': 'Extended reach for contact point height'
            },
            'knee_flexion': {
                'expected_range': (120, 160),  # Deeper bend
                'rationale': 'Leg drive from trophy position'
            },
            'spine_lean': {
                'expected_range': (-20, 10),  # Backward arch
                'rationale': 'Spinal extension in trophy position'
            }
        },
        'phase_emphasis': {
            'preparation': 0.20,  # Trophy position critical
            'load': 0.20,
            'contact': 0.40,  # Most critical for serve
            'follow_through': 0.20
        }
    },
    
    'volley': {
        'name': 'Volley',
        'description': 'Net volley (forehand or backhand)',
        'biomechanical_intent': {
            'hip_rotation': {
                'expected_range': (30, 90),  # Minimal rotation
                'rationale': 'Compact motion for quick reaction at net'
            },
            'elbow_angle': {
                'expected_range': (90, 130),  # Compact
                'rationale': 'Short, punching motion'
            },
            'knee_flexion': {
                'expected_range': (140, 170),
                'rationale': 'Ready position with flexion'
            },
            'spine_lean': {
                'expected_range': (0, 20),  # Forward lean
                'rationale': 'Aggressive forward posture at net'
            }
        },
        'phase_emphasis': {
            'preparation': 0.30,  # Split-step crucial
            'load': 0.10,  # Minimal loading
            'contact': 0.45,  # Contact timing critical
            'follow_through': 0.15  # Short follow-through
        }
    },
    
    'overhead': {
        'name': 'Overhead Smash',
        'description': 'Overhead smash or high volley',
        'biomechanical_intent': {
            'hip_rotation': {
                'expected_range': (150, 250),  # Similar to serve
                'rationale': 'Serve-like motion for power'
            },
            'elbow_angle': {
                'expected_range': (130, 180),  # Extended
                'rationale': 'High contact point extension'
            },
            'knee_flexion': {
                'expected_range': (140, 175),
                'rationale': 'Balanced stance for overhead reach'
            },
            'spine_lean': {
                'expected_range': (-15, 5),  # Backward arch
                'rationale': 'Backward lean for upward contact'
            }
        },
        'phase_emphasis': {
            'preparation': 0.25,
            'load': 0.20,
            'contact': 0.40,
            'follow_through': 0.15
        }
    }
}


def get_stroke_aware_threshold(
    metric_name: str,
    stroke_type: str = 'backhand',
    threshold_type: str = 'expected_range'
) -> tuple:
    """
    Get stroke-specific biomechanical thresholds for intelligent metric evaluation.
    
    This function enables multi-stroke intelligence by providing stroke-specific
    context for biomechanical metrics. Different strokes have different optimal
    ranges (e.g., forehand has larger hip rotation than backhand).
    
    BACKWARD COMPATIBILITY:
    - Default stroke_type is 'backhand' (preserves all existing behavior)
    - Falls back to backhand if stroke not found
    - Returns None if metric not in profile (caller handles fallback)
    
    INTEGRATION POINTS (future):
    - Similarity scoring: adjust deviation thresholds per stroke
    - Coaching cues: stroke-specific recommendations
    - Drill selection: map drills to stroke requirements
    
    Args:
        metric_name: Name of biomechanical metric (e.g., 'hip_rotation')
        stroke_type: Type of stroke ('backhand', 'forehand', 'serve', 'volley', 'overhead')
        threshold_type: Type of threshold ('expected_range', 'rationale')
        
    Returns:
        Threshold value (type depends on threshold_type), or None if not found
        
    Example:
        >>> get_stroke_aware_threshold('hip_rotation', 'forehand')
        (180, 270)  # Forehand expects larger rotation than backhand
        
        >>> get_stroke_aware_threshold('hip_rotation', 'backhand')
        (150, 220)  # Backhand default (existing behavior)
        
        >>> get_stroke_aware_threshold('hip_rotation', 'unknown_stroke')
        (150, 220)  # Falls back to backhand
    """
    # Normalize stroke type
    stroke_type = stroke_type.lower().strip()
    
    # Fallback to backhand if stroke not recognized (backward compatibility)
    if stroke_type not in STROKE_PROFILES:
        stroke_type = 'backhand'
    
    # Get stroke profile
    profile = STROKE_PROFILES[stroke_type]
    
    # Normalize metric name for lookup
    metric_key = metric_name.lower().replace('_angle', '').replace('_rotation', '')
    
    # Map common metric names to profile keys
    metric_mapping = {
        'hip': 'hip_rotation',
        'hip_rotation': 'hip_rotation',
        'elbow': 'elbow_angle',
        'elbow_angle': 'elbow_angle',
        'left_elbow': 'elbow_angle',
        'right_elbow': 'elbow_angle',
        'knee': 'knee_flexion',
        'knee_angle': 'knee_flexion',
        'knee_flexion': 'knee_flexion',
        'left_knee': 'knee_flexion',
        'right_knee': 'knee_flexion',
        'spine': 'spine_lean',
        'spine_lean': 'spine_lean'
    }
    
    profile_key = metric_mapping.get(metric_key)
    
    if not profile_key:
        return None
    
    # Get biomechanical intent for this metric
    if profile_key not in profile['biomechanical_intent']:
        return None
    
    metric_spec = profile['biomechanical_intent'][profile_key]
    
    # Return requested threshold type
    if threshold_type == 'expected_range':
        return metric_spec.get('expected_range')
    elif threshold_type == 'rationale':
        return metric_spec.get('rationale')
    else:
        return None


def get_stroke_phase_weights(stroke_type: str = 'backhand') -> dict:
    """
    Get stroke-specific phase importance weights.
    
    Different strokes emphasize different phases:
    - Groundstrokes: Contact is most critical
    - Serve: Contact + Preparation (trophy position)
    - Volley: Preparation (split-step) + Contact
    
    BACKWARD COMPATIBILITY:
    - Default is 'backhand' (preserves existing behavior)
    - Falls back to backhand if stroke not found
    
    Args:
        stroke_type: Type of stroke
        
    Returns:
        Dictionary of phase weights (sum = 1.0)
    """
    # Normalize stroke type
    stroke_type = stroke_type.lower().strip()
    
    # Fallback to backhand (backward compatibility)
    if stroke_type not in STROKE_PROFILES:
        stroke_type = 'backhand'
    
    return STROKE_PROFILES[stroke_type]['phase_emphasis']


# ============================================================================
# Movement & Footwork Intelligence (Phase 2.2)
# ============================================================================

"""
The Movement & Footwork Intelligence layer extends Coach AI with stroke-agnostic
movement analysis. While stroke mechanics focus on arm/body positioning during
the swing, movement intelligence evaluates:
- Court positioning
- Split-step timing
- Lateral push-off and recovery
- Balance and stability
- Transition speed

WHY THIS MATTERS FOR TENNIS:
- "Good feet, good shots" - Movement is foundational
- Poor footwork causes inconsistent stroke mechanics
- Recovery speed determines rally control
- Balance enables power generation
- Split-step timing affects reaction time

HOW IT COMPLEMENTS STROKE ABSTRACTION:
- Stroke Abstraction: WHAT happens during the swing
- Movement Intelligence: HOW you get into position to execute
- Together: Complete tennis technique analysis

INTEGRATION WITH EXISTING SYSTEMS:
- Movement metrics participate in reliability analysis
- Movement issues are eligible for CRITICAL/PRIORITY/MONITOR classification
- Footwork drills map to movement metrics via existing drill engine
- Low-reliability movement metrics are suppressible (same as stroke metrics)

BACKWARD COMPATIBILITY:
- Movement metrics are optional (system works without them)
- Existing stroke analysis remains unchanged
- If no movement data available, gracefully skips
"""

# Movement metric definitions
# These are stroke-agnostic and evaluate positioning/footwork quality
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


# ============================================================================
# Rally & Fatigue Intelligence (Phase 2.3)
# ============================================================================

"""
The Rally & Fatigue Intelligence layer adds temporal analysis to detect
performance degradation patterns over the course of a session or rally.

WHY THIS MATTERS FOR TENNIS:
- Fatigue affects technique: Tired players exhibit biomechanical degradation
- Rally patterns reveal strategic weaknesses vs fatigue effects
- Technical coaching for fatigue-driven issues is ineffective
- Recovery and conditioning need different interventions than technique work

KEY INSIGHTS:
- Fatigue signals: Increasing recovery time, decreasing rotation, rising variability
- Rally patterns: Metric evolution within point sequences
- Temporal degradation: Performance decline over session
- Fatigue vs Technique: Different root causes, different solutions

INTEGRATION WITH EXISTING SYSTEMS:
- Fatigue flags participate in adaptive prioritization (additive)
- Fatigue-driven issues may be suppressed or marked for conditioning work
- Rally context enriches coaching cue specificity
- Backward compatible: Works without rally data

INFERENCE APPROACH (NO PHYSIOLOGICAL SENSORS):
We infer fatigue purely from biomechanical degradation patterns:
1. Temporal trends (metrics worsening over time)
2. Increased variability (consistency drops)
3. Recovery time increases
4. Range of motion decreases
5. Balance instability increases

This is INFERENCE, not measurement. We flag probable fatigue-driven issues.
"""

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
    
    import numpy as np
    
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
    from inspect import signature
    
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


# ============================================================================
# CV-Based Movement Extraction (Phase 3.1)
# ============================================================================

"""
CV-Based Movement Extraction computes movement metrics directly from pose
time series data extracted by MediaPipe. This enables automatic measurement
of split-step timing, recovery time, and balance drift without manual input.

WHY THIS MATTERS:
- Automated movement analysis from video alone
- No manual annotation or sensors required
- Real-time feedback on footwork quality
- Objective measurement of movement patterns

APPROACH:
- Use existing pose landmarks (MediaPipe output)
- Compute center of mass (COM) from hip landmarks
- Detect movement events from kinematic signals
- Estimate timing and quality metrics

INTEGRATION:
- Metrics feed into Movement Intelligence (Phase 2.2)
- Participate in reliability analysis
- Used for fatigue detection (Phase 2.3)
- Enable automated coaching feedback

GRACEFUL DEGRADATION:
- All metrics are optional
- Missing/noisy data returns None with confidence=0
- Pipeline continues without movement metrics if extraction fails
"""

import numpy as np
import pandas as pd


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


# ============================================================================
# Measurement Trust & Calibration (Phase 3.2)
# ============================================================================

"""
Measurement Trust & Calibration adds a Signal Quality & Trust Layer to evaluate
the reliability of CV-derived movement metrics. This improves coaching confidence
by distinguishing between biomechanical issues and measurement artifacts.

WHY THIS MATTERS:
- Real-world video has variable quality (lighting, occlusion, motion blur)
- Tracking errors can look like biomechanical issues
- Low-quality measurements reduce coaching trust
- Calibrated confidence prevents false positives

KEY DISTINCTION:
- SIGNAL QUALITY: How good is the tracking/measurement?
- BIOMECHANICAL CONFIDENCE: How reliable is the extracted metric?
- TRUST SCORE: Combined assessment (signal × biomechanical)

APPROACH:
- Analyze pose time series for tracking artifacts
- Compute session-level signal quality score (0-1)
- Modulate metric confidence based on signal quality
- Generate human-readable trust reason codes

INTEGRATION:
- Plugs into existing reliability & prioritization logic
- No threshold retuning required
- Graceful degradation (no metrics fully discarded)
- Backward compatible
"""


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


# ============================================================================
# Session Management
# ============================================================================

def generate_session_id() -> str:
    """
    Generate a unique session ID based on current timestamp.
    
    Returns:
        Session ID in format: YYYY-MM-DD_HH-MM-SS
    """
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def create_session_directory(session_id: str, base_dir: str = "outputs") -> Path:
    """
    Create a session-specific output directory.
    
    Args:
        session_id: Unique session identifier
        base_dir: Base output directory (default: "outputs")
        
    Returns:
        Path object for the session directory
        
    Raises:
        OSError: If directory creation fails (caller should handle)
    """
    session_dir = Path(base_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_session_paths(session_id: str = None, base_dir: str = "outputs") -> dict:
    """
    Get output file paths for a session.
    
    Args:
        session_id: Optional session ID. If None, uses base_dir directly (legacy mode)
        base_dir: Base output directory
        
    Returns:
        Dictionary of output paths
    """
    if session_id:
        output_dir = Path(base_dir) / session_id
    else:
        output_dir = Path(base_dir)
    
    return {
        'output_dir': output_dir,
        'overlay_user': output_dir / "overlay_user.mp4",
        'overlay_ref': output_dir / "overlay_ref.mp4",
        'features_user': output_dir / "user_features.csv",
        'features_ref': output_dir / "ref_features.csv",
        'report': output_dir / "report.md"
    }


# TODO: Multi-user support - Add user_id parameter to session management
# TODO: Progress tracking - Store session history in a sessions.json file
# TODO: Real-time inference - Stream processing for live video analysis


# ============================================================================
# Configuration Management (Optional)
# ============================================================================

def load_config(config_path: str = None) -> dict:
    """
    Load configuration from YAML file (optional).
    
    If no config is provided, returns None and system uses hardcoded defaults.
    This ensures 100% backward compatibility with existing tennis behavior.
    
    Args:
        config_path: Path to YAML config file (optional)
        
    Returns:
        Configuration dictionary or None if no config/YAML unavailable
    """
    if config_path is None:
        return None
    
    if not YAML_AVAILABLE:
        print("[WARNING] PyYAML not installed. Install with: pip install pyyaml")
        print("[INFO] Using hardcoded defaults for tennis backhand analysis")
        return None
    
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            print(f"[WARNING] Config file not found: {config_path}")
            print("[INFO] Using hardcoded defaults for tennis backhand analysis")
            return None
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        print(f"[CONFIG] Loaded configuration from: {config_path}")
        if 'sport' in config and 'movement' in config:
            print(f"[CONFIG] Sport: {config['sport']}, Movement: {config['movement']}")
        
        return config
    
    except Exception as e:
        print(f"[WARNING] Failed to load config: {e}")
        print("[INFO] Using hardcoded defaults for tennis backhand analysis")
        return None


def get_phase_weights(config: dict = None) -> dict:
    """
    Get phase weights from config or use defaults.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Phase weights dictionary
    """
    # Default tennis backhand weights (existing hardcoded behavior)
    default_weights = {
        'preparation': 0.15,
        'load': 0.25,
        'contact': 0.35,
        'follow_through': 0.25
    }
    
    if config and 'phase_weights' in config:
        return config['phase_weights']
    
    return default_weights


def get_metrics_list(config: dict = None) -> list:
    """
    Get metrics list from config or use defaults.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        List of metric names
    """
    # Default tennis backhand metrics (existing hardcoded behavior)
    default_metrics = [
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
    
    if config and 'metrics' in config:
        return config['metrics']
    
    return default_metrics


def get_phase_names(config: dict = None) -> dict:
    """
    Get phase names from config or use defaults.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dictionary mapping phase keys to display names
    """
    # Default tennis backhand phases (existing hardcoded behavior)
    default_phases = {
        'preparation': 'Preparation',
        'load': 'Load',
        'contact': 'Contact',
        'follow_through': 'Follow-through'
    }
    
    if config and 'phases' in config:
        return {key: phase['name'] for key, phase in config['phases'].items()}
    
    return default_phases


# ============================================================================
# Progress Tracking Across Sessions
# ============================================================================

def find_previous_session(base_dir: str = "outputs", current_session_id: str = None) -> str:
    """
    Find the most recent previous session directory.
    
    Args:
        base_dir: Base output directory
        current_session_id: Current session ID to exclude
        
    Returns:
        Previous session ID (directory name) or None if not found
    """
    try:
        base_path = Path(base_dir)
        if not base_path.exists():
            return None
        
        # Get all session directories (format: YYYY-MM-DD_HH-MM-SS)
        session_dirs = []
        for item in base_path.iterdir():
            if item.is_dir() and item.name != current_session_id:
                # Check if it looks like a session directory (has timestamp format)
                if len(item.name) == 19 and item.name[10] == '_':
                    session_dirs.append(item.name)
        
        if not session_dirs:
            return None
        
        # Sort by timestamp (lexicographic = chronological for our format)
        session_dirs.sort(reverse=True)
        
        # Return most recent
        return session_dirs[0]
        
    except Exception as e:
        print(f"[WARNING] Error finding previous session: {e}")
        return None


def load_previous_metrics(session_id: str, base_dir: str = "outputs") -> dict:
    """
    Load key metrics from a previous session's report.
    
    Args:
        session_id: Previous session ID
        base_dir: Base output directory
        
    Returns:
        Dictionary with previous metrics or None if unavailable
    """
    try:
        report_path = Path(base_dir) / session_id / "report.md"
        
        if not report_path.exists():
            return None
        
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metrics = {}
        
        # Parse overall similarity score
        import re
        overall_match = re.search(r'\*\*Overall Technique Score:\s+(\d+\.?\d*)/100\*\*', content)
        if overall_match:
            metrics['overall_score'] = float(overall_match.group(1))
        
        # Parse phase-weighted score
        weighted_match = re.search(r'\*\*Overall Quality Score:\s+(\d+\.?\d*)/100\*\*', content)
        if weighted_match:
            metrics['phase_weighted_score'] = float(weighted_match.group(1))
        
        # Parse phase-specific scores
        phase_pattern = r'\*\*(\w+(?:\s+\w+)?)\*\*:\s+(\d+\.?\d*)/100'
        phase_matches = re.findall(phase_pattern, content)
        
        phase_scores = {}
        for phase_name, score in phase_matches:
            phase_key = phase_name.lower().replace(' ', '_').replace('-', '_')
            phase_scores[phase_key] = float(score)
        
        if phase_scores:
            metrics['phase_scores'] = phase_scores
        
        # Parse key metric differences (for detailed tracking)
        # Looking for patterns like "| Left Elbow Angle | 119.3° | 92.6° | +26.7° |"
        metric_pattern = r'\|\s+(\w+(?:\s+\w+)*)\s+\|\s+(\d+\.?\d*)°?\s+\|.*?\|\s+([+-]?\d+\.?\d*)°?\s+\|'
        metric_matches = re.findall(metric_pattern, content)
        
        key_metrics = {}
        for metric_name, user_val, diff in metric_matches[:7]:  # Take first 7 (main metrics table)
            metric_key = metric_name.lower().replace(' ', '_')
            key_metrics[metric_key] = {
                'value': float(user_val),
                'diff_from_pro': float(diff)
            }
        
        if key_metrics:
            metrics['key_metrics'] = key_metrics
        
        return metrics if metrics else None
        
    except Exception as e:
        print(f"[WARNING] Error loading previous metrics: {e}")
        return None


def compute_progress_deltas(current_metrics: dict, previous_metrics: dict) -> dict:
    """
    Compute changes between current and previous sessions.
    
    Args:
        current_metrics: Current session metrics
        previous_metrics: Previous session metrics
        
    Returns:
        Dictionary of deltas and classifications
    """
    deltas = {}
    
    # Overall score delta
    if 'overall_score' in current_metrics and 'overall_score' in previous_metrics:
        current = current_metrics['overall_score']
        previous = previous_metrics['overall_score']
        delta = current - previous
        
        deltas['overall_score'] = {
            'current': current,
            'previous': previous,
            'delta': delta,
            'status': classify_progress(delta, metric_type='score')
        }
    
    # Phase-weighted score delta
    if 'phase_weighted_score' in current_metrics and 'phase_weighted_score' in previous_metrics:
        current = current_metrics['phase_weighted_score']
        previous = previous_metrics['phase_weighted_score']
        delta = current - previous
        
        deltas['phase_weighted_score'] = {
            'current': current,
            'previous': previous,
            'delta': delta,
            'status': classify_progress(delta, metric_type='score')
        }
    
    # Phase-specific deltas
    if 'phase_scores' in current_metrics and 'phase_scores' in previous_metrics:
        current_phases = current_metrics['phase_scores']
        previous_phases = previous_metrics['phase_scores']
        
        phase_deltas = {}
        for phase_key in current_phases:
            if phase_key in previous_phases:
                current = current_phases[phase_key]
                previous = previous_phases[phase_key]
                delta = current - previous
                
                phase_deltas[phase_key] = {
                    'current': current,
                    'previous': previous,
                    'delta': delta,
                    'status': classify_progress(delta, metric_type='score')
                }
        
        if phase_deltas:
            deltas['phase_deltas'] = phase_deltas
    
    return deltas


def classify_progress(delta: float, metric_type: str = 'score') -> tuple:
    """
    Classify progress as Improved/Stable/Regressed.
    
    Args:
        delta: Change value (current - previous)
        metric_type: 'score' (higher is better) or 'error' (lower is better)
        
    Returns:
        Tuple of (status_text, icon)
    """
    if metric_type == 'score':
        # For scores, positive delta is improvement
        if delta >= 3.0:
            return "Improved", "↗"
        elif delta <= -3.0:
            return "Regressed", "↘"
        else:
            return "Stable", "→"
    else:
        # For errors/deviations, negative delta is improvement
        if delta <= -3.0:
            return "Improved", "↗"
        elif delta >= 3.0:
            return "Regressed", "↘"
        else:
            return "Stable", "→"


# ============================================================================
# ML-Based Similarity Analysis
# ============================================================================

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
    Compute ML-based similarity scores for each movement phase using cosine similarity.
    
    Cosine similarity measures the angle between feature vectors, capturing
    the overall pattern match independent of scale. Score ranges from -1 (opposite)
    to 1 (identical), normalized to 0-100 for reporting.
    
    Args:
        user_phase_metrics: User's phase-specific metrics
        ref_phase_metrics: Reference phase-specific metrics
        config: Optional configuration dictionary
        
    Returns:
        Dictionary: {phase_name: similarity_score (0-100)}
    """
    ml_similarities = {}
    
    # Get metrics list from config or use defaults
    metric_keys = get_metrics_list(config)
    
    phase_names = ['preparation', 'load', 'contact', 'follow_through']
    
    for phase_name in phase_names:
        if phase_name not in user_phase_metrics or phase_name not in ref_phase_metrics:
            continue
        
        try:
            # Extract feature vectors using config-specified metrics
            user_features = extract_phase_feature_vector(user_phase_metrics[phase_name], metric_keys=metric_keys)
            ref_features = extract_phase_feature_vector(ref_phase_metrics[phase_name], metric_keys=metric_keys)
            
            # Reshape for sklearn (expects 2D arrays)
            user_vec = user_features.reshape(1, -1)
            ref_vec = ref_features.reshape(1, -1)
            
            # Compute cosine similarity directly (no StandardScaler - it zeroes single-sample vectors)
            cos_sim = cosine_similarity(user_vec, ref_vec)[0, 0]
            
            # Convert from [-1, 1] to [0, 100]
            # -1 = 0%, 0 = 50%, 1 = 100%
            similarity_score = (cos_sim + 1) * 50.0
            
            ml_similarities[phase_name] = round(float(similarity_score), 1)
            
        except Exception as e:
            print(f"[WARNING] ML similarity computation failed for {phase_name}: {e}")
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


# ============================================================================
# System Reliability & Confidence Analysis
# ============================================================================

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


# ============================================================================
# Adaptive Coaching Decision Engine
# ============================================================================

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


# ============================================================================
# Intelligent Drill & Intervention Recommendations
# ============================================================================

def get_drill_knowledge_base() -> dict:
    """
    Static knowledge base mapping biomechanical issues to training drills.
    
    Each drill includes:
    - name: Drill name
    - description: What the drill does
    - target_metrics: Which metrics it addresses
    - target_phases: Which phases it helps with
    - intensity_levels: Different versions (light/moderate/intensive)
    - frequency: Recommended practice frequency
    
    Returns:
        Dictionary of drills organized by issue category
    """
    return {
        'hip_rotation': {
            'drills': [
                {
                    'name': 'Medicine Ball Rotational Throws',
                    'description': 'Stand sideways to wall, rotate hips explosively to throw medicine ball',
                    'target_metrics': ['hip_rotation'],
                    'target_phases': ['load', 'contact'],
                    'intensity': {
                        'light': '2 sets × 8 reps, 4-6 lbs ball',
                        'moderate': '3 sets × 10 reps, 6-8 lbs ball',
                        'intensive': '4 sets × 12 reps, 8-10 lbs ball, daily'
                    },
                    'rationale': 'Builds rotational power and hip coiling mechanics'
                },
                {
                    'name': 'Hip Rotation Shadow Swings',
                    'description': 'Practice stroke focusing solely on hip rotation, exaggerate the movement',
                    'target_metrics': ['hip_rotation'],
                    'target_phases': ['load', 'contact'],
                    'intensity': {
                        'light': '50 reps, slow tempo',
                        'moderate': '100 reps, match tempo',
                        'intensive': '200 reps daily, with resistance band'
                    },
                    'rationale': 'Isolates hip rotation to build muscle memory'
                }
            ]
        },
        'elbow_angles': {
            'drills': [
                {
                    'name': 'Wall Contact Drill',
                    'description': 'Stand close to wall, practice stroke keeping elbows compact and close to body',
                    'target_metrics': ['left_elbow_angle', 'right_elbow_angle'],
                    'target_phases': ['contact', 'load'],
                    'intensity': {
                        'light': '3 sets × 10 reps',
                        'moderate': '5 sets × 15 reps',
                        'intensive': '10 sets × 20 reps, add resistance bands'
                    },
                    'rationale': 'Enforces proper elbow position and compact arm structure'
                },
                {
                    'name': 'Elbow-to-Body Connection',
                    'description': 'Hold small towel between elbow and torso during shadow strokes',
                    'target_metrics': ['left_elbow_angle', 'right_elbow_angle'],
                    'target_phases': ['preparation', 'load', 'contact'],
                    'intensity': {
                        'light': '50 reps',
                        'moderate': '100 reps',
                        'intensive': '200 reps, progress to live balls'
                    },
                    'rationale': 'Creates kinesthetic awareness of proper elbow position'
                }
            ]
        },
        'knee_stability': {
            'drills': [
                {
                    'name': 'Split-Step to Stance Drill',
                    'description': 'Practice split-step followed by balanced backhand stance, hold for 3 seconds',
                    'target_metrics': ['left_knee_angle', 'right_knee_angle'],
                    'target_phases': ['preparation', 'load'],
                    'intensity': {
                        'light': '2 sets × 10 reps',
                        'moderate': '3 sets × 15 reps',
                        'intensive': '5 sets × 20 reps with weights'
                    },
                    'rationale': 'Builds lower body stability and balance'
                }
            ]
        },
        'stance_width': {
            'drills': [
                {
                    'name': 'Ladder Footwork Drill',
                    'description': 'Use agility ladder, practice split-stepping into consistent stance width',
                    'target_metrics': ['stance_width_normalized'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '3 minutes',
                        'moderate': '5 minutes',
                        'intensive': '10 minutes with shadow strokes'
                    },
                    'rationale': 'Develops consistent footwork and stance positioning'
                },
                {
                    'name': 'Cone Placement Training',
                    'description': 'Place cones at optimal foot positions, practice hitting from marked stance',
                    'target_metrics': ['stance_width_normalized'],
                    'target_phases': ['preparation', 'load'],
                    'intensity': {
                        'light': '20 balls',
                        'moderate': '50 balls',
                        'intensive': '100 balls across multiple sessions'
                    },
                    'rationale': 'Provides visual feedback for proper stance width'
                }
            ]
        },
        'spine_lean': {
            'drills': [
                {
                    'name': 'Mirror Posture Check',
                    'description': 'Practice stroke in front of mirror, focus on maintaining proper spine angle',
                    'target_metrics': ['spine_lean'],
                    'target_phases': ['preparation', 'load', 'contact'],
                    'intensity': {
                        'light': '5 minutes daily',
                        'moderate': '10 minutes daily',
                        'intensive': '15 minutes 2x daily with video recording'
                    },
                    'rationale': 'Visual feedback for posture correction'
                }
            ]
        },
        'shoulder_stability': {
            'drills': [
                {
                    'name': 'Resistance Band Shoulder Rotations',
                    'description': 'Use resistance bands to strengthen shoulder stability through stroke motion',
                    'target_metrics': ['left_shoulder_angle', 'right_shoulder_angle'],
                    'target_phases': ['preparation', 'load'],
                    'intensity': {
                        'light': '2 sets × 10 reps, light band',
                        'moderate': '3 sets × 15 reps, medium band',
                        'intensive': '4 sets × 20 reps, heavy band'
                    },
                    'rationale': 'Builds shoulder strength and stability'
                }
            ]
        },
        'general_technique': {
            'drills': [
                {
                    'name': 'Slow-Motion Shadow Strokes',
                    'description': 'Execute full stroke in slow motion, focus on feeling each phase',
                    'target_metrics': ['all'],
                    'target_phases': ['all'],
                    'intensity': {
                        'light': '25 reps',
                        'moderate': '50 reps',
                        'intensive': '100 reps with video analysis'
                    },
                    'rationale': 'Builds muscle memory and movement awareness'
                },
                {
                    'name': 'Video Review Sessions',
                    'description': 'Record yourself, compare side-by-side with pro reference',
                    'target_metrics': ['all'],
                    'target_phases': ['all'],
                    'intensity': {
                        'light': '1x per week',
                        'moderate': '2x per week',
                        'intensive': '3x per week with detailed notes'
                    },
                    'rationale': 'Provides objective feedback on progress'
                }
            ]
        },
        
        # ====================================================================
        # Movement & Footwork Drills (Phase 2.2)
        # ====================================================================
        
        'split_step_timing': {
            'drills': [
                {
                    'name': 'Partner Split-Step Drill',
                    'description': 'Partner drops ball, practice split-step at exact moment ball bounces',
                    'target_metrics': ['split_step_timing'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '2 sets × 10 reps',
                        'moderate': '4 sets × 15 reps',
                        'intensive': '6 sets × 20 reps with random timing'
                    },
                    'rationale': 'Develops anticipation and split-step timing coordination'
                },
                {
                    'name': 'Shadow Split-Step Training',
                    'description': 'Watch pro match video, split-step in sync with players',
                    'target_metrics': ['split_step_timing'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '5 minutes',
                        'moderate': '10 minutes',
                        'intensive': '15 minutes 2x daily'
                    },
                    'rationale': 'Builds rhythm and timing awareness'
                }
            ]
        },
        
        'lateral_push_off_symmetry': {
            'drills': [
                {
                    'name': 'Single-Leg Lateral Bounds',
                    'description': 'Practice explosive lateral jumps on each leg separately, compare distance',
                    'target_metrics': ['lateral_push_off_symmetry'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '2 sets × 8 reps per leg',
                        'moderate': '3 sets × 12 reps per leg',
                        'intensive': '4 sets × 15 reps per leg with measurements'
                    },
                    'rationale': 'Identifies and corrects lateral movement imbalances'
                },
                {
                    'name': 'Side-to-Side Shuffle Drill',
                    'description': 'Shuffle laterally between lines, focus on equal power from both legs',
                    'target_metrics': ['lateral_push_off_symmetry'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '3 sets × 30 seconds',
                        'moderate': '5 sets × 45 seconds',
                        'intensive': '8 sets × 60 seconds with acceleration focus'
                    },
                    'rationale': 'Develops balanced lateral movement power'
                }
            ]
        },
        
        'recovery_time': {
            'drills': [
                {
                    'name': 'Touch-and-Recover Drill',
                    'description': 'Hit from wide position, touch center line, recover to ready position',
                    'target_metrics': ['recovery_time'],
                    'target_phases': ['follow_through'],
                    'intensity': {
                        'light': '10 reps per side',
                        'moderate': '20 reps per side',
                        'intensive': '30 reps per side, timed'
                    },
                    'rationale': 'Builds recovery speed and court positioning habits'
                },
                {
                    'name': 'Recovery Sprint Intervals',
                    'description': 'Sprint to corner, hit imaginary shot, sprint back to center',
                    'target_metrics': ['recovery_time'],
                    'target_phases': ['follow_through'],
                    'intensity': {
                        'light': '6 reps',
                        'moderate': '12 reps',
                        'intensive': '20 reps with stopwatch tracking'
                    },
                    'rationale': 'Conditions fast recovery and endurance'
                }
            ]
        },
        
        'stance_transition_speed': {
            'drills': [
                {
                    'name': 'Quick-Setup Shadow Drill',
                    'description': 'From ready position, transition to stroke stance as fast as possible',
                    'target_metrics': ['stance_transition_speed'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '3 sets × 10 reps',
                        'moderate': '5 sets × 15 reps',
                        'intensive': '8 sets × 20 reps, timed'
                    },
                    'rationale': 'Develops explosive stance setup speed'
                },
                {
                    'name': 'Cone-Touch Transition Drill',
                    'description': 'Touch cone at ready position, explode to stroke stance at second cone',
                    'target_metrics': ['stance_transition_speed'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '2 sets × 8 reps per side',
                        'moderate': '4 sets × 12 reps per side',
                        'intensive': '6 sets × 15 reps per side with timing'
                    },
                    'rationale': 'Builds explosive transition mechanics'
                }
            ]
        },
        
        'balance_drift': {
            'drills': [
                {
                    'name': 'Balance Board Strokes',
                    'description': 'Practice shadow strokes while standing on balance board',
                    'target_metrics': ['balance_drift'],
                    'target_phases': ['contact'],
                    'intensity': {
                        'light': '2 sets × 10 strokes',
                        'moderate': '4 sets × 15 strokes',
                        'intensive': '6 sets × 20 strokes with eyes closed'
                    },
                    'rationale': 'Develops core stability and balance control'
                },
                {
                    'name': 'Single-Leg Balance Holds',
                    'description': 'Hold stroke finish position on one leg, measure stability',
                    'target_metrics': ['balance_drift'],
                    'target_phases': ['contact', 'follow_through'],
                    'intensity': {
                        'light': '3 sets × 15 seconds per leg',
                        'moderate': '4 sets × 30 seconds per leg',
                        'intensive': '5 sets × 45 seconds per leg with perturbations'
                    },
                    'rationale': 'Builds proprioception and stability'
                }
            ]
        },
        
        'first_step_reaction_time': {
            'drills': [
                {
                    'name': 'Light Reaction Drill',
                    'description': 'Partner points direction with hand signal, react with first step',
                    'target_metrics': ['first_step_reaction_time'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '2 sets × 10 reps',
                        'moderate': '4 sets × 15 reps',
                        'intensive': '6 sets × 20 reps with varied timing'
                    },
                    'rationale': 'Develops visual processing and reaction speed'
                },
                {
                    'name': 'Ball Drop Reaction Drill',
                    'description': 'Partner drops ball from shoulder height, catch before second bounce',
                    'target_metrics': ['first_step_reaction_time'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '2 sets × 8 reps',
                        'moderate': '3 sets × 12 reps',
                        'intensive': '5 sets × 15 reps from various distances'
                    },
                    'rationale': 'Trains explosive first-step mechanics'
                }
            ]
        },
        
        'footwork_efficiency': {
            'drills': [
                {
                    'name': 'Minimalist Footwork Pattern',
                    'description': 'Move to ball using minimum steps possible, focus on stride length',
                    'target_metrics': ['footwork_efficiency'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '15 balls',
                        'moderate': '30 balls',
                        'intensive': '50 balls with step counting'
                    },
                    'rationale': 'Develops economical movement patterns'
                },
                {
                    'name': 'Ladder Agility Training',
                    'description': 'Agility ladder drills focusing on long strides and efficient steps',
                    'target_metrics': ['footwork_efficiency'],
                    'target_phases': ['preparation'],
                    'intensity': {
                        'light': '4 minutes',
                        'moderate': '8 minutes',
                        'intensive': '12 minutes with varied patterns'
                    },
                    'rationale': 'Builds efficient foot placement patterns'
                }
            ]
        },
        
        'weight_transfer_completeness': {
            'drills': [
                {
                    'name': 'Weight Transfer Shadow Drill',
                    'description': 'Practice stroke emphasizing complete weight shift from back to front foot',
                    'target_metrics': ['weight_transfer_completeness'],
                    'target_phases': ['contact'],
                    'intensity': {
                        'light': '3 sets × 10 reps',
                        'moderate': '5 sets × 15 reps',
                        'intensive': '8 sets × 20 reps with resistance band'
                    },
                    'rationale': 'Builds kinetic chain power generation'
                },
                {
                    'name': 'Medicine Ball Transfer Throws',
                    'description': 'Throw medicine ball forward while fully transferring weight',
                    'target_metrics': ['weight_transfer_completeness'],
                    'target_phases': ['contact'],
                    'intensity': {
                        'light': '2 sets × 8 throws, 4-6 lbs',
                        'moderate': '3 sets × 12 throws, 6-8 lbs',
                        'intensive': '4 sets × 15 throws, 8-10 lbs'
                    },
                    'rationale': 'Develops explosive weight transfer mechanics'
                }
            ]
        },
        
        'general_movement': {
            'drills': [
                {
                    'name': 'Court Coverage Circuit',
                    'description': 'Complete circuit: split-step, move to corner, recover, repeat all 4 corners',
                    'target_metrics': ['split_step_timing', 'recovery_time', 'footwork_efficiency'],
                    'target_phases': ['preparation', 'follow_through'],
                    'intensity': {
                        'light': '2 circuits',
                        'moderate': '4 circuits',
                        'intensive': '6 circuits timed'
                    },
                    'rationale': 'Integrates all movement skills in tennis-specific pattern'
                },
                {
                    'name': 'Footwork & Shot Combination',
                    'description': 'Feed random balls, focus on perfect footwork setup for each shot',
                    'target_metrics': ['stance_transition_speed', 'balance_drift', 'weight_transfer_completeness'],
                    'target_phases': ['preparation', 'contact'],
                    'intensity': {
                        'light': '20 balls',
                        'moderate': '50 balls',
                        'intensive': '100 balls with varied feeds'
                    },
                    'rationale': 'Applies movement skills in realistic match situations'
                }
            ]
        }
    }


def map_metric_to_drill_category(metric_name: str) -> str:
    """
    Map a biomechanical or movement metric to its corresponding drill category.
    
    Extended in Phase 2.2 to support movement & footwork metrics alongside
    stroke mechanics metrics. Movement metrics (split-step, recovery, balance)
    are now eligible for drill recommendations via the same system.
    
    Args:
        metric_name: Name of the metric
        
    Returns:
        Drill category key
    """
    metric_lower = metric_name.lower()
    
    # Check if this is a movement/footwork metric (Phase 2.2)
    if is_movement_metric(metric_name):
        # Direct mapping for movement metrics
        metric_key = metric_lower.replace(' ', '_')
        if metric_key in ['split_step_timing', 'lateral_push_off_symmetry', 
                         'recovery_time', 'stance_transition_speed', 'balance_drift',
                         'first_step_reaction_time', 'footwork_efficiency', 
                         'weight_transfer_completeness']:
            return metric_key
        else:
            return 'general_movement'
    
    # Stroke mechanics metrics (original logic)
    if 'hip' in metric_lower and 'rotation' in metric_lower:
        return 'hip_rotation'
    elif 'elbow' in metric_lower:
        return 'elbow_angles'
    elif 'knee' in metric_lower:
        return 'knee_stability'
    elif 'stance' in metric_lower or 'width' in metric_lower:
        return 'stance_width'
    elif 'spine' in metric_lower or 'lean' in metric_lower:
        return 'spine_lean'
    elif 'shoulder' in metric_lower:
        return 'shoulder_stability'
    else:
        return 'general_technique'


def generate_adaptive_drill_recommendations(
    adaptive_focus: dict,
    drill_kb: dict = None
) -> dict:
    """
    Generate intelligent drill recommendations based on adaptive coaching priorities.
    
    Adjusts drill intensity and frequency based on:
    - Issue classification (CRITICAL/PRIORITY/MONITOR/SUPPRESS)
    - Severity of deviation
    - Persistence across sessions
    
    Args:
        adaptive_focus: Output from generate_adaptive_coaching_focus()
        drill_kb: Drill knowledge base (optional, uses default if None)
        
    Returns:
        Dictionary with drill recommendations by priority level
    """
    if drill_kb is None:
        drill_kb = get_drill_knowledge_base()
    
    recommendations = {
        'critical_drills': [],
        'priority_drills': [],
        'maintenance_drills': [],
        'suppressed_count': 0
    }
    
    # Process critical issues - intensive drills
    for issue in adaptive_focus['critical']:
        category = map_metric_to_drill_category(issue['metric'])
        
        if category in drill_kb and drill_kb[category]['drills']:
            # Select first drill for this category (most relevant)
            drill = drill_kb[category]['drills'][0]
            
            recommendations['critical_drills'].append({
                'issue_metric': issue['metric'],
                'issue_phase': issue['phase'],
                'drill_name': drill['name'],
                'drill_description': drill['description'],
                'intensity_level': 'intensive',
                'prescription': drill['intensity']['intensive'],
                'rationale': drill['rationale'],
                'priority_score': issue['priority_score'],
                'urgency': 'HIGH',
                'reason': f"Critical issue: {abs(issue['deviation']):.1f}{'°' if 'normalized' not in issue['metric'] else ''} deviation, {issue['reliability']} reliability"
            })
    
    # Process priority issues - moderate drills
    for issue in adaptive_focus['priority'][:3]:  # Limit to top 3
        category = map_metric_to_drill_category(issue['metric'])
        
        if category in drill_kb and drill_kb[category]['drills']:
            # Try to select a different drill than critical ones
            available_drills = drill_kb[category]['drills']
            drill = available_drills[0] if len(available_drills) == 1 else available_drills[min(1, len(available_drills)-1)]
            
            recommendations['priority_drills'].append({
                'issue_metric': issue['metric'],
                'issue_phase': issue['phase'],
                'drill_name': drill['name'],
                'drill_description': drill['description'],
                'intensity_level': 'moderate',
                'prescription': drill['intensity']['moderate'],
                'rationale': drill['rationale'],
                'priority_score': issue['priority_score'],
                'urgency': 'MODERATE',
                'reason': f"Priority issue: {abs(issue['deviation']):.1f}{'°' if 'normalized' not in issue['metric'] else ''} deviation, needs focused work"
            })
    
    # Process monitor issues - light maintenance drills (only if improving)
    for issue in adaptive_focus['monitor'][:2]:  # Limit to top 2
        # Only recommend drills for improving issues, not low-reliability ones
        if issue['progress_delta'] < -5:  # Improving
            category = map_metric_to_drill_category(issue['metric'])
            
            if category in drill_kb and drill_kb[category]['drills']:
                drill = drill_kb[category]['drills'][0]
                
                recommendations['maintenance_drills'].append({
                    'issue_metric': issue['metric'],
                    'issue_phase': issue['phase'],
                    'drill_name': drill['name'],
                    'drill_description': drill['description'],
                    'intensity_level': 'light',
                    'prescription': drill['intensity']['light'],
                    'rationale': drill['rationale'],
                    'priority_score': issue['priority_score'],
                    'urgency': 'MAINTENANCE',
                    'reason': f"Currently improving - maintain progress with light practice"
                })
    
    # Count suppressed issues (no drills recommended)
    recommendations['suppressed_count'] = len(adaptive_focus['suppressed'])
    
    # Add general technique drills if no specific drills recommended
    if not recommendations['critical_drills'] and not recommendations['priority_drills']:
        general = drill_kb['general_technique']['drills'][0]
        recommendations['priority_drills'].append({
            'issue_metric': 'general',
            'issue_phase': 'all',
            'drill_name': general['name'],
            'drill_description': general['description'],
            'intensity_level': 'moderate',
            'prescription': general['intensity']['moderate'],
            'rationale': general['rationale'],
            'priority_score': 50.0,
            'urgency': 'MODERATE',
            'reason': 'General technique refinement'
        })
    
    return recommendations


# ============================================================================
# Drill Outcome Tracking (Learning Layer)
# ============================================================================

def track_drill_outcomes(
    previous_session_id: str,
    previous_session_metrics: dict,
    current_session_metrics: dict,
    drill_recommendations: dict,
    current_session_id: str,
    reliability_data: dict = None
) -> list:
    """
    Track drill outcomes by comparing metric improvements between sessions.
    
    This function learns which drills correlate with improvements by:
    1. Computing metric deltas (current - previous)
    2. Matching improvements to drills that targeted those metrics
    3. Storing outcomes for future intelligence
    
    IMPORTANT: This function has NO side effects on recommendations or reports.
    It only records outcomes for future learning.
    
    Args:
        previous_session_id: Previous session identifier
        previous_session_metrics: Metrics from previous session (phase-specific)
        current_session_metrics: Metrics from current session (phase-specific)
        drill_recommendations: Drills that were recommended in previous session
        current_session_id: Current session identifier
        reliability_data: Optional reliability assessment for current session
        
    Returns:
        List of outcome records (for storage)
    """
    outcomes = []
    
    # If no drill recommendations, nothing to track
    if not drill_recommendations:
        return outcomes
    
    # Collect all drills from all urgency levels
    all_drills = []
    all_drills.extend(drill_recommendations.get('critical_drills', []))
    all_drills.extend(drill_recommendations.get('priority_drills', []))
    all_drills.extend(drill_recommendations.get('maintenance_drills', []))
    
    # For each drill, check if the targeted metric improved
    for drill in all_drills:
        target_metric = drill['issue_metric']
        target_phase = drill['issue_phase']
        
        # Skip general drills (can't track specific improvements)
        if target_metric == 'general' or target_phase == 'all':
            continue
        
        # Get previous and current metric values
        # Note: These are phase-specific metrics
        prev_value = None
        curr_value = None
        
        # Try to get metric from phase-specific data
        if previous_session_metrics and target_phase in previous_session_metrics:
            prev_value = previous_session_metrics[target_phase].get(target_metric)
        
        if current_session_metrics and target_phase in current_session_metrics:
            curr_value = current_session_metrics[target_phase].get(target_metric)
        
        # If we have both values, compute delta
        if prev_value is not None and curr_value is not None:
            # For deviation metrics, improvement means getting closer to zero
            # Delta = current - previous (negative = improvement if tracking deviations)
            # But here we're tracking raw metric values, not deviations
            delta = curr_value - prev_value
            
            # Get reliability for this metric (current session)
            metric_reliability = 'Unknown'
            if reliability_data and target_metric in reliability_data:
                metric_reliability = reliability_data[target_metric].get('level', 'Unknown')
            
            # Store outcome record
            outcome = {
                'previous_session_id': previous_session_id,
                'current_session_id': current_session_id,
                'metric_name': target_metric,
                'phase': target_phase,
                'drill_name': drill['drill_name'],
                'intensity': drill['intensity_level'],
                'classification': drill['urgency'],
                'pre_value': float(prev_value),
                'post_value': float(curr_value),
                'delta': float(delta),
                'reliability': metric_reliability,
                'timestamp': datetime.now().isoformat()
            }
            
            outcomes.append(outcome)
    
    return outcomes


def save_drill_outcomes(outcomes: list, output_dir: str = "outputs") -> bool:
    """
    Append drill outcomes to persistent storage (append-only).
    
    Stores outcomes in a JSON file for future analysis. Uses append-only
    approach to preserve full history.
    
    Args:
        outcomes: List of outcome records
        output_dir: Base output directory
        
    Returns:
        True if successful, False otherwise
    """
    if not outcomes:
        return True  # Nothing to save
    
    try:
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Outcome file path
        outcome_file = Path(output_dir) / 'drill_outcomes.json'
        
        # Load existing outcomes (if file exists)
        existing_outcomes = []
        if outcome_file.exists():
            try:
                with open(outcome_file, 'r') as f:
                    existing_outcomes = json.load(f)
            except:
                # If file is corrupted, start fresh
                existing_outcomes = []
        
        # Append new outcomes
        existing_outcomes.extend(outcomes)
        
        # Save back to file
        with open(outcome_file, 'w') as f:
            json.dump(existing_outcomes, f, indent=2)
        
        return True
    
    except Exception as e:
        # Silently fail - don't break the pipeline
        print(f"  [INFO] Could not save drill outcomes: {e}")
        return False


def get_drill_effectiveness_summary(output_dir: str = "outputs") -> dict:
    """
    Compute average improvement per drill from historical outcomes (read-only).
    
    This helper function summarizes which drills have been most effective
    historically. Useful for future intelligence but not used in current session.
    
    Args:
        output_dir: Base output directory
        
    Returns:
        Dictionary with drill effectiveness statistics
    """
    outcome_file = Path(output_dir) / 'drill_outcomes.json'
    
    # If no outcomes file, return empty summary
    if not outcome_file.exists():
        return {}
    
    try:
        # Load outcomes
        with open(outcome_file, 'r') as f:
            outcomes = json.load(f)
        
        # Group by drill name
        drill_stats = {}
        
        for outcome in outcomes:
            drill_name = outcome['drill_name']
            delta = outcome['delta']
            reliability = outcome['reliability']
            
            if drill_name not in drill_stats:
                drill_stats[drill_name] = {
                    'count': 0,
                    'total_delta': 0.0,
                    'deltas': [],
                    'high_reliability_count': 0
                }
            
            drill_stats[drill_name]['count'] += 1
            drill_stats[drill_name]['total_delta'] += delta
            drill_stats[drill_name]['deltas'].append(delta)
            
            if reliability == 'High':
                drill_stats[drill_name]['high_reliability_count'] += 1
        
        # Compute averages
        summary = {}
        for drill_name, stats in drill_stats.items():
            if stats['count'] > 0:
                summary[drill_name] = {
                    'usage_count': stats['count'],
                    'avg_delta': stats['total_delta'] / stats['count'],
                    'high_reliability_fraction': stats['high_reliability_count'] / stats['count']
                }
        
        return summary
    
    except Exception as e:
        # Silently fail - this is optional intelligence
        return {}


def compute_drill_confidence_scores(output_dir: str = "outputs") -> dict:
    """
    Compute confidence scores for each drill based on historical outcomes (read-only).
    
    This function analyzes past drill effectiveness to generate confidence scores
    that indicate which drills have proven to be most effective. The confidence
    score integrates multiple factors:
    
    - Improvement magnitude: How much the drill improves metrics
    - Reliability: Fraction of outcomes with high-confidence measurements
    - Consistency: Low variance across outcomes (reliable effectiveness)
    - Sample size: More data = higher confidence
    
    IMPORTANT: This is a read-only analysis function. It does NOT affect
    drill recommendations or any pipeline behavior. It only observes and scores.
    
    Args:
        output_dir: Base output directory
        
    Returns:
        Dictionary with confidence scores per drill
        {
            'drill_name': {
                'usage_count': int,
                'avg_delta': float,
                'std_delta': float,
                'high_reliability_ratio': float,
                'consistency': float (0-1, higher = more consistent),
                'confidence_score': float (0-1, higher = more confident),
                'confidence_level': str ('High'/'Medium'/'Low')
            }
        }
    """
    outcome_file = Path(output_dir) / 'drill_outcomes.json'
    
    # If no outcomes file, return empty scores
    if not outcome_file.exists():
        return {}
    
    try:
        # Load all historical outcomes
        with open(outcome_file, 'r') as f:
            outcomes = json.load(f)
        
        if not outcomes:
            return {}
        
        # Group outcomes by drill name
        drill_groups = {}
        
        for outcome in outcomes:
            drill_name = outcome['drill_name']
            delta = outcome['delta']
            reliability = outcome['reliability']
            
            if drill_name not in drill_groups:
                drill_groups[drill_name] = {
                    'deltas': [],
                    'reliabilities': []
                }
            
            drill_groups[drill_name]['deltas'].append(delta)
            drill_groups[drill_name]['reliabilities'].append(reliability)
        
        # Compute confidence scores for each drill
        confidence_scores = {}
        
        for drill_name, data in drill_groups.items():
            deltas = np.array(data['deltas'])
            reliabilities = data['reliabilities']
            
            # 1. Usage count (sample size)
            usage_count = len(deltas)
            
            # 2. Average improvement (negative delta = improvement for most metrics)
            avg_delta = float(np.mean(deltas))
            
            # 3. Standard deviation (consistency measure)
            std_delta = float(np.std(deltas)) if len(deltas) > 1 else 0.0
            
            # 4. High reliability ratio (measurement confidence)
            high_reliability_count = sum(1 for r in reliabilities if r == 'High')
            high_reliability_ratio = high_reliability_count / usage_count if usage_count > 0 else 0.0
            
            # 5. Consistency score (inverse of coefficient of variation)
            # Low variance relative to mean = high consistency
            # Use abs(avg_delta) to avoid division issues with near-zero means
            if abs(avg_delta) > 0.1:
                cv = std_delta / abs(avg_delta)
                # Convert to 0-1 scale: lower CV = higher consistency
                # CV > 1.0 = inconsistent (score 0), CV = 0 = perfect (score 1)
                consistency = max(0.0, 1.0 - min(cv, 1.0))
            else:
                # If avg_delta near zero, use std alone
                # Lower std = higher consistency
                consistency = max(0.0, 1.0 - min(std_delta / 10.0, 1.0))
            
            # 6. Compute overall confidence score (0-1 scale)
            # Weights: improvement (40%), reliability (25%), consistency (25%), sample size (10%)
            
            # Improvement component (normalize delta to 0-1)
            # Assume deltas in range [-20, +20], with negative being good
            # Map: -20 → 1.0 (best), 0 → 0.5, +20 → 0.0 (worst)
            improvement_score = max(0.0, min(1.0, 0.5 - (avg_delta / 40.0)))
            
            # Reliability component (already 0-1)
            reliability_score = high_reliability_ratio
            
            # Consistency component (already 0-1)
            consistency_score = consistency
            
            # Sample size component (diminishing returns after 5 samples)
            # 1 sample = 0.2, 5+ samples = 1.0
            sample_score = min(1.0, usage_count / 5.0)
            
            # Weighted confidence score
            confidence_score = (
                0.40 * improvement_score +
                0.25 * reliability_score +
                0.25 * consistency_score +
                0.10 * sample_score
            )
            
            # Classify confidence level
            if confidence_score >= 0.75:
                confidence_level = 'High'
            elif confidence_score >= 0.50:
                confidence_level = 'Medium'
            else:
                confidence_level = 'Low'
            
            confidence_scores[drill_name] = {
                'usage_count': usage_count,
                'avg_delta': avg_delta,
                'std_delta': std_delta,
                'high_reliability_ratio': high_reliability_ratio,
                'consistency': consistency,
                'confidence_score': confidence_score,
                'confidence_level': confidence_level
            }
        
        return confidence_scores
    
    except Exception as e:
        # Silently fail - this is read-only intelligence
        return {}


def get_top_effective_drills(n: int = 5, output_dir: str = "outputs") -> list:
    """
    Get top N most effective drills based on confidence scores (read-only).
    
    This helper ranks drills by their confidence scores and returns the most
    effective ones. Useful for understanding which drills have the best
    track record historically.
    
    IMPORTANT: This is read-only. It does NOT influence current recommendations.
    
    Args:
        n: Number of top drills to return (default 5)
        output_dir: Base output directory
        
    Returns:
        List of (drill_name, confidence_data) tuples, sorted by confidence score
    """
    # Get confidence scores for all drills
    confidence_scores = compute_drill_confidence_scores(output_dir)
    
    if not confidence_scores:
        return []
    
    # Sort by confidence score (highest first)
    sorted_drills = sorted(
        confidence_scores.items(),
        key=lambda x: x[1]['confidence_score'],
        reverse=True
    )
    
    # Return top N
    return sorted_drills[:n]


########################################
# MATCH READINESS INTELLIGENCE
# (Synthesis layer - combines technique, movement, fatigue, trust)
########################################

def compute_match_readiness(
    technique_score: float,
    movement_metrics: dict = None,
    fatigue_analysis: dict = None,
    signal_quality: dict = None
) -> dict:
    """
    Compute match readiness score by synthesizing existing intelligence layers.
    
    IMPORTANT: Match readiness is NOT a performance prediction or injury risk assessment.
    It is a training and competition guidance signal that reflects the current state of:
    - Technique quality (stroke biomechanics)
    - Movement quality (footwork, balance, recovery)
    - Fatigue level (biomechanical degradation signals)
    - Signal trust (measurement reliability)
    
    The readiness score helps coaches and athletes decide:
    - Is the athlete ready for competition?
    - Should training intensity be adjusted?
    - Are there red flags that need attention before competing?
    
    This is a synthesis layer that combines existing intelligence without introducing
    new measurements or analysis. It provides a single, explainable metric for decision-making.
    
    Args:
        technique_score: Overall technique similarity score (0-100)
        movement_metrics: Dict of movement quality assessments (optional)
        fatigue_analysis: Dict with fatigue score and signals (optional)
        signal_quality: Dict with signal quality score (optional)
    
    Returns:
        dict: {
            'readiness_score': float (0-100),
            'readiness_level': str (Poor/Fair/Good/Excellent),
            'confidence': float (0-1),
            'contributors': dict (component scores with weights),
            'explanation': str (human-readable summary),
            'flags': list (warning signals)
        }
    """
    # Component weights (sum to 1.0)
    # These can be adjusted based on sport/context
    base_weights = {
        'technique': 0.40,
        'movement': 0.30,
        'fatigue': 0.20,
        'trust': 0.10
    }
    
    # Components dictionary
    components = {}
    actual_weights = {}
    flags = []
    
    # 1. Technique quality (always available)
    components['technique'] = technique_score / 100.0  # Normalize to 0-1
    actual_weights['technique'] = base_weights['technique']
    
    # 2. Movement quality (optional)
    if movement_metrics and movement_metrics.get('split_step_timing'):
        # Extract movement quality signals
        split_step = movement_metrics.get('split_step_timing', {})
        recovery = movement_metrics.get('recovery_time', {})
        balance = movement_metrics.get('balance_drift', {})
        
        movement_scores = []
        
        # Split-step quality
        if split_step.get('split_step_quality') == 'on-time':
            movement_scores.append(1.0)
        elif split_step.get('split_step_quality') == 'early':
            movement_scores.append(0.8)
        else:
            movement_scores.append(0.5)
            flags.append("Split-step timing needs improvement")
        
        # Recovery time (lower is better, assume < 1.5s is good)
        recovery_time = recovery.get('recovery_time_seconds', 2.0)
        recovery_score = max(0, 1.0 - (recovery_time - 1.0) / 1.5)
        movement_scores.append(recovery_score)
        
        if recovery_time > 2.0:
            flags.append("Slow recovery time detected")
        
        # Balance stability
        balance_score = balance.get('stability_score', 50) / 100.0
        movement_scores.append(balance_score)
        
        if balance_score < 0.6:
            flags.append("Balance instability detected")
        
        # Average movement quality
        components['movement'] = np.mean(movement_scores)
        actual_weights['movement'] = base_weights['movement']
    else:
        # Reweight if movement data missing
        actual_weights['technique'] += base_weights['movement'] * 0.7
        actual_weights['fatigue'] = base_weights['fatigue'] + base_weights['movement'] * 0.3
    
    # 3. Fatigue level (optional, inverted - low fatigue = good readiness)
    if fatigue_analysis and 'fatigue_score' in fatigue_analysis:
        fatigue_score = fatigue_analysis['fatigue_score']  # 0-100, higher = more fatigue
        components['fatigue'] = 1.0 - (fatigue_score / 100.0)  # Invert: low fatigue = high readiness
        actual_weights['fatigue'] = base_weights['fatigue']
        
        if fatigue_score > 60:
            flags.append("Moderate to high fatigue detected")
        
        # Check for specific fatigue signals
        affected = fatigue_analysis.get('affected_metrics', [])
        if len(affected) >= 3:
            flags.append(f"{len(affected)} metrics show fatigue patterns")
    else:
        # Reweight if fatigue data missing
        # Distribute fatigue weight to existing components only
        if 'movement' in components:
            actual_weights['movement'] += base_weights['fatigue'] * 0.5
            actual_weights['technique'] += base_weights['fatigue'] * 0.5
        else:
            # No movement data, give all to technique
            actual_weights['technique'] += base_weights['fatigue']
    
    # 4. Signal trust (optional)
    if signal_quality and 'quality_score' in signal_quality:
        trust_score = signal_quality['quality_score']
        components['trust'] = trust_score
        actual_weights['trust'] = base_weights['trust']
        
        if trust_score < 0.6:
            flags.append("Measurement quality below optimal")
    else:
        # Distribute trust weight to other components
        for key in actual_weights:
            actual_weights[key] += base_weights['trust'] / len(actual_weights)
    
    # Normalize weights to sum to 1.0 (in case of rounding errors)
    weight_sum = sum(actual_weights.values())
    actual_weights = {k: v / weight_sum for k, v in actual_weights.items()}
    
    # Compute weighted readiness score
    readiness_raw = sum(
        components.get(key, 0) * actual_weights[key]
        for key in actual_weights
    )
    
    readiness_score = readiness_raw * 100  # Scale to 0-100
    
    # Determine readiness level
    if readiness_score >= 85:
        readiness_level = "Excellent"
    elif readiness_score >= 70:
        readiness_level = "Good"
    elif readiness_score >= 55:
        readiness_level = "Fair"
    else:
        readiness_level = "Poor"
    
    # Compute confidence based on data availability
    data_availability = len(components) / 4.0  # 4 possible components
    confidence = data_availability * 0.7 + 0.3  # Minimum 0.3, max 1.0
    
    # If trust is low, reduce confidence
    if 'trust' in components and components['trust'] < 0.7:
        confidence *= components['trust']
    
    # Generate human-readable explanation
    explanation_parts = []
    
    # Lead with readiness level
    explanation_parts.append(f"{readiness_level} readiness")
    
    # Identify top contributor (only from actual components)
    valid_contributors = {k: components.get(k, 0) * actual_weights[k] 
                          for k in actual_weights if k in components}
    
    if valid_contributors:
        top_contributor = max(valid_contributors.items(), key=lambda x: x[1])[0]
        
        contributor_names = {
            'technique': 'technique quality',
            'movement': 'movement quality',
            'fatigue': 'low fatigue',
            'trust': 'signal reliability'
        }
        
        explanation_parts.append(f"driven by strong {contributor_names[top_contributor]}")
        
        # Note any concerns (only from actual components)
        concerns = []
        for key, score in components.items():
            if score < 0.6 and key != 'trust':  # Trust is metadata, not a performance factor
                concerns.append(contributor_names.get(key, key))
        
        if concerns:
            explanation_parts.append(f"with concerns in {', '.join(concerns)}")
    
    explanation = ", ".join(explanation_parts) + "."
    
    # Build contributors dict (only include actual components)
    contributors_output = {}
    for key in components.keys():
        if key in actual_weights:
            contributors_output[key] = {
                'raw_score': round(components[key] * 100, 1),
                'weight': round(actual_weights[key], 2),
                'weighted_contribution': round(components[key] * actual_weights[key] * 100, 1)
            }
    
    return {
        'readiness_score': round(readiness_score, 1),
        'readiness_level': readiness_level,
        'confidence': round(confidence, 2),
        'contributors': contributors_output,
        'explanation': explanation,
        'flags': flags
    }


########################################
# TRAINING LOAD & SESSION PLANNING
# (Synthesis layer - converts readiness into training guidance)
########################################

def compute_training_load_recommendation(
    match_readiness: dict = None,
    fatigue_analysis: dict = None,
    signal_quality: dict = None,
    adaptive_coaching: dict = None
) -> dict:
    """
    Compute training load recommendation based on match readiness and fatigue intelligence.
    
    IMPORTANT: This is training guidance, NOT medical advice or workout prescription.
    It provides general recommendations for session planning based on observable
    biomechanical state. Always consult with qualified coaches and medical professionals.
    
    The training load recommendation helps answer:
    - What type of session should I do today?
    - What intensity is appropriate?
    - What should I focus on or avoid?
    
    This is a synthesis layer that converts readiness signals into actionable guidance
    without introducing new measurements or modifying existing analysis.
    
    Args:
        match_readiness: Output from compute_match_readiness (optional)
        fatigue_analysis: Dict with fatigue score and signals (optional)
        signal_quality: Dict with signal quality score (optional)
        adaptive_coaching: Dict with priority issues (optional)
    
    Returns:
        dict: {
            'session_type': str (Recovery/Technique/Movement/Conditioning/Full/Match-sim),
            'intensity': str (Low/Moderate/High),
            'focus_areas': list[str],
            'avoid_areas': list[str],
            'rationale': str (human-readable explanation),
            'confidence': float (0-1),
            'warnings': list[str]
        }
    """
    # Default values
    session_type = "Technique"
    intensity = "Moderate"
    focus_areas = []
    avoid_areas = []
    warnings = []
    confidence = 0.5
    
    # Extract key signals
    readiness_score = 70.0  # Default moderate readiness
    readiness_level = "Good"
    fatigue_score = 30.0  # Default low fatigue
    trust_score = 0.8  # Default good trust
    
    if match_readiness:
        readiness_score = match_readiness.get('readiness_score', 70.0)
        readiness_level = match_readiness.get('readiness_level', 'Good')
        confidence = match_readiness.get('confidence', 0.5)
    
    if fatigue_analysis:
        fatigue_score = fatigue_analysis.get('fatigue_score', 30.0)
    
    if signal_quality:
        trust_score = signal_quality.get('quality_score', 0.8)
    
    # Decision logic based on readiness and fatigue
    
    # Case 1: Low signal trust → Recommend re-recording
    if trust_score < 0.6:
        session_type = "Technique"
        intensity = "Low"
        focus_areas.append("Video quality improvement")
        warnings.append("Low measurement quality detected - consider re-recording with better lighting/angles")
        rationale = "Limited training guidance due to low measurement quality. Focus on basic technique with low intensity until better video data is available."
    
    # Case 2: High fatigue → Recovery or light technique
    elif fatigue_score > 60:
        session_type = "Recovery"
        intensity = "Low"
        focus_areas.append("Active recovery")
        focus_areas.append("Mobility work")
        avoid_areas.append("High-intensity rallies")
        avoid_areas.append("Explosive movements")
        
        if fatigue_score > 75:
            warnings.append("Very high fatigue detected - prioritize rest and recovery")
        
        rationale = f"High fatigue detected ({fatigue_score:.0f}/100). Prioritize recovery to prevent overtraining. Light technique drills acceptable, but avoid high-intensity work."
    
    # Case 3: Low readiness (poor technique/movement)
    elif readiness_score < 55:
        session_type = "Technique"
        intensity = "Low"
        focus_areas.append("Fundamental technique refinement")
        focus_areas.append("Slow-motion practice")
        avoid_areas.append("Match simulation")
        avoid_areas.append("High-speed rallies")
        
        rationale = f"Low readiness ({readiness_score:.1f}/100). Focus on technique fundamentals at low intensity to build solid foundation before increasing load."
    
    # Case 4: Fair readiness → Technique + Movement
    elif readiness_score < 70:
        session_type = "Technique"
        intensity = "Moderate"
        focus_areas.append("Technical corrections")
        focus_areas.append("Movement patterns")
        focus_areas.append("Consistency drills")
        
        if fatigue_score > 40:
            avoid_areas.append("Extended rallies")
            warnings.append("Moderate fatigue present - monitor closely and reduce volume if needed")
        
        rationale = f"Fair readiness ({readiness_score:.1f}/100). Moderate intensity technical and movement work appropriate. Build consistency before increasing intensity."
    
    # Case 5: Good readiness → Conditioning or Full training
    elif readiness_score < 85:
        if fatigue_score < 30:
            session_type = "Full"
            intensity = "High"
            focus_areas.append("Technical refinement under pressure")
            focus_areas.append("Conditioning drills")
            focus_areas.append("Point play")
        else:
            session_type = "Conditioning"
            intensity = "Moderate"
            focus_areas.append("Technique maintenance")
            focus_areas.append("Movement conditioning")
            avoid_areas.append("Max-intensity rallies")
        
        rationale = f"Good readiness ({readiness_score:.1f}/100). Ready for substantial training load. Can include conditioning and point play."
    
    # Case 6: Excellent readiness → Match simulation
    else:
        session_type = "Match-sim"
        intensity = "High"
        focus_areas.append("Match simulation")
        focus_areas.append("Competition scenarios")
        focus_areas.append("Mental toughness")
        focus_areas.append("Strategy execution")
        
        rationale = f"Excellent readiness ({readiness_score:.1f}/100). Peak form. Ready for match simulation and high-intensity competition preparation."
    
    # Add specific focus areas from adaptive coaching if available
    if adaptive_coaching and 'priorities' in adaptive_coaching:
        priorities = adaptive_coaching['priorities']
        critical_issues = [p for p in priorities if p.get('classification') == 'CRITICAL']
        
        if critical_issues and session_type not in ['Recovery', 'Match-sim']:
            for issue in critical_issues[:2]:  # Top 2 critical issues
                metric = issue.get('metric', '').replace('_', ' ').title()
                focus_areas.append(f"Address critical issue: {metric}")
    
    # Confidence adjustment based on data availability
    if not match_readiness:
        confidence *= 0.7
    if not fatigue_analysis:
        confidence *= 0.9
    if not signal_quality:
        confidence *= 0.95
    
    return {
        'session_type': session_type,
        'intensity': intensity,
        'focus_areas': focus_areas,
        'avoid_areas': avoid_areas,
        'rationale': rationale,
        'confidence': round(confidence, 2),
        'warnings': warnings
    }


########################################
# PLAYER BASELINE & PERSONALIZATION
# (Aggregates historical session data for relative interpretation)
########################################

def load_historical_sessions(output_dir: str = "outputs", max_sessions: int = 10) -> list:
    """
    Load historical session data from the outputs directory.
    
    This function scans session directories and extracts key metrics
    for baseline computation. It loads data from session subdirectories
    (e.g., outputs/2025-12-29_13-12-31/) and returns a list of session
    summaries.
    
    Args:
        output_dir: Base output directory (default: "outputs")
        max_sessions: Maximum number of recent sessions to load (default: 10)
    
    Returns:
        list: List of session dicts, sorted by timestamp (newest first)
              Each dict contains: {
                  'session_id': str,
                  'timestamp': str,
                  'technique_score': float,
                  'readiness_score': float (if available),
                  'phase_scores': dict (if available),
                  'metrics': dict (extracted metrics)
              }
    """
    output_path = Path(output_dir)
    
    if not output_path.exists():
        return []
    
    sessions = []
    
    # Find all session directories (timestamp format: YYYY-MM-DD_HH-MM-SS)
    session_dirs = []
    for item in output_path.iterdir():
        if item.is_dir() and len(item.name) == 19:  # Expected format length
            try:
                # Validate it's a timestamp format
                datetime.strptime(item.name, '%Y-%m-%d_%H-%M-%S')
                session_dirs.append(item)
            except ValueError:
                continue  # Skip non-session directories
    
    # Sort by timestamp (newest first)
    session_dirs.sort(reverse=True)
    
    # Load up to max_sessions
    for session_dir in session_dirs[:max_sessions]:
        try:
            session_id = session_dir.name
            
            # Try to load metrics from user_features.csv
            features_file = session_dir / "user_features.csv"
            metrics = {}
            
            if features_file.exists():
                # Read basic features
                features_df = pd.read_csv(features_file)
                
                # Extract key metrics (if available)
                if 'elbow_angle' in features_df.columns:
                    metrics['elbow_angle'] = features_df['elbow_angle'].mean()
                if 'knee_angle' in features_df.columns:
                    metrics['knee_angle'] = features_df['knee_angle'].mean()
                if 'hip_rotation' in features_df.columns:
                    metrics['hip_rotation'] = features_df['hip_rotation'].mean()
            
            # Try to extract scores from report.md if it exists
            report_file = session_dir / "report.md"
            technique_score = None
            readiness_score = None
            
            if report_file.exists():
                report_text = report_file.read_text(encoding='utf-8')
                
                # Extract technique score (look for "Overall Similarity: X.X%")
                import re
                similarity_match = re.search(r'Overall Similarity:\s*\*\*(\d+\.?\d*)%\*\*', report_text)
                if similarity_match:
                    technique_score = float(similarity_match.group(1))
                
                # Extract readiness score (look for "Score**: X.X/100")
                readiness_match = re.search(r'\*\*Score\*\*:\s*(\d+\.?\d*)/100', report_text)
                if readiness_match:
                    readiness_score = float(readiness_match.group(1))
            
            session_data = {
                'session_id': session_id,
                'timestamp': session_id,
                'technique_score': technique_score,
                'readiness_score': readiness_score,
                'metrics': metrics
            }
            
            sessions.append(session_data)
        
        except Exception as e:
            # Skip sessions that can't be loaded
            continue
    
    return sessions


def compute_player_baseline(
    historical_sessions: list,
    min_sessions: int = 3
) -> dict:
    """
    Compute player baseline from historical session data.
    
    This function aggregates historical metrics to establish personal
    reference values. These baselines enable relative interpretation:
    "Your recovery time is 15% faster than your baseline."
    
    IMPORTANT: Baselines represent typical performance for this athlete,
    NOT absolute standards or goals. They enable tracking relative changes
    over time.
    
    Args:
        historical_sessions: List of session dicts from load_historical_sessions
        min_sessions: Minimum sessions required to compute baseline (default: 3)
    
    Returns:
        dict: {
            'has_baseline': bool,
            'session_count': int,
            'baseline_technique_score': float,
            'baseline_readiness_score': float,
            'baseline_metrics': dict,
            'computed_at': str (timestamp)
        }
        
        Returns empty baseline if insufficient data.
    """
    if len(historical_sessions) < min_sessions:
        return {
            'has_baseline': False,
            'session_count': len(historical_sessions),
            'reason': f'Insufficient data (need {min_sessions} sessions, have {len(historical_sessions)})'
        }
    
    # Aggregate technique scores
    technique_scores = [s['technique_score'] for s in historical_sessions if s.get('technique_score') is not None]
    baseline_technique = np.mean(technique_scores) if technique_scores else None
    
    # Aggregate readiness scores
    readiness_scores = [s['readiness_score'] for s in historical_sessions if s.get('readiness_score') is not None]
    baseline_readiness = np.mean(readiness_scores) if readiness_scores else None
    
    # Aggregate metrics
    baseline_metrics = {}
    
    # Find common metrics across sessions
    all_metric_names = set()
    for session in historical_sessions:
        all_metric_names.update(session.get('metrics', {}).keys())
    
    for metric_name in all_metric_names:
        values = [
            s['metrics'][metric_name] 
            for s in historical_sessions 
            if metric_name in s.get('metrics', {})
        ]
        if values:
            baseline_metrics[metric_name] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'sample_size': len(values)
            }
    
    return {
        'has_baseline': True,
        'session_count': len(historical_sessions),
        'baseline_technique_score': round(baseline_technique, 1) if baseline_technique else None,
        'baseline_readiness_score': round(baseline_readiness, 1) if baseline_readiness else None,
        'baseline_metrics': baseline_metrics,
        'computed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def compare_to_baseline(
    current_value: float,
    baseline_value: float,
    metric_name: str = "metric"
) -> dict:
    """
    Compare current session value to player baseline.
    
    Generates relative interpretation for better context:
    - "15% above baseline" (improvement for positive metrics)
    - "10% below baseline" (decline for positive metrics)
    
    Args:
        current_value: Current session value
        baseline_value: Player baseline value
        metric_name: Name of metric for context
    
    Returns:
        dict: {
            'delta_absolute': float,
            'delta_percent': float,
            'delta_direction': str ('above' | 'below' | 'stable'),
            'interpretation': str (human-readable)
        }
    """
    if baseline_value == 0:
        return {
            'delta_absolute': 0,
            'delta_percent': 0,
            'delta_direction': 'stable',
            'interpretation': f'{metric_name} baseline is zero (cannot compute relative change)'
        }
    
    delta_absolute = current_value - baseline_value
    delta_percent = (delta_absolute / baseline_value) * 100
    
    # Determine direction
    if abs(delta_percent) < 5:
        delta_direction = 'stable'
        interpretation = f'{metric_name} is stable (within 5% of baseline)'
    elif delta_absolute > 0:
        delta_direction = 'above'
        interpretation = f'{metric_name} is {abs(delta_percent):.1f}% above baseline'
    else:
        delta_direction = 'below'
        interpretation = f'{metric_name} is {abs(delta_percent):.1f}% below baseline'
    
    return {
        'delta_absolute': round(delta_absolute, 2),
        'delta_percent': round(delta_percent, 1),
        'delta_direction': delta_direction,
        'interpretation': interpretation
    }


########################################
# PROGRESS NARRATIVES & COACH SUMMARIES
# (Interpretive layer - summarizes trends in coach-style language)
########################################

def detect_trend(values: list, min_sessions: int = 3, threshold_percent: float = 5.0) -> dict:
    """
    Detect trend in a time series of values.
    
    Uses conservative thresholds to classify trends as improving, stable, or declining.
    This is interpretive analysis, not statistical prediction.
    
    Args:
        values: List of values in chronological order (oldest first)
        min_sessions: Minimum values needed for trend detection (default: 3)
        threshold_percent: Threshold for classifying as improving/declining (default: 5%)
    
    Returns:
        dict: {
            'has_trend': bool,
            'trend': str ('improving' | 'stable' | 'declining'),
            'confidence': str ('low' | 'medium' | 'high'),
            'recent_avg': float,
            'earlier_avg': float,
            'percent_change': float
        }
    """
    if len(values) < min_sessions:
        return {
            'has_trend': False,
            'reason': f'Insufficient data (need {min_sessions} sessions, have {len(values)})'
        }
    
    # Assume values are already in chronological order (oldest first)
    # Split into earlier half and recent half
    split_point = len(values) // 2
    earlier_values = values[:split_point]
    recent_values = values[split_point:]
    
    earlier_avg = np.mean(earlier_values)
    recent_avg = np.mean(recent_values)
    
    # Compute percent change
    if earlier_avg == 0:
        percent_change = 0
    else:
        percent_change = ((recent_avg - earlier_avg) / earlier_avg) * 100
    
    # Classify trend
    if abs(percent_change) < threshold_percent:
        trend = 'stable'
    elif percent_change > 0:
        trend = 'improving'
    else:
        trend = 'declining'
    
    # Confidence based on consistency and sample size
    # High confidence: many samples and consistent direction
    # Low confidence: few samples or high variance
    std_dev = np.std(values)
    cv = (std_dev / np.mean(values)) if np.mean(values) != 0 else 0
    
    if len(values) >= 5 and cv < 0.15:
        confidence = 'high'
    elif len(values) >= 4 or cv < 0.25:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    return {
        'has_trend': True,
        'trend': trend,
        'confidence': confidence,
        'recent_avg': round(recent_avg, 1),
        'earlier_avg': round(earlier_avg, 1),
        'percent_change': round(percent_change, 1)
    }


def generate_progress_narrative(
    historical_sessions: list,
    num_sessions: int = 5,
    min_sessions: int = 3
) -> dict:
    """
    Generate human-readable progress narrative from historical sessions.
    
    This function creates coach-style summaries of multi-session trends:
    - Highlights positive trends first
    - Flags concerns gently
    - Avoids absolutes or predictions
    - Uses encouraging, supportive language
    
    IMPORTANT: This is interpretive analysis, NOT predictive modeling or
    performance guarantees. It summarizes observed patterns in recent data.
    
    Args:
        historical_sessions: List of session dicts from load_historical_sessions
        num_sessions: Number of recent sessions to analyze (default: 5)
        min_sessions: Minimum sessions needed for narrative (default: 3)
    
    Returns:
        dict: {
            'has_narrative': bool,
            'session_count': int,
            'trends': dict (technique, readiness trends),
            'narrative_summary': str (human-readable summary),
            'coach_take': str (short coaching insight)
        }
    """
    if len(historical_sessions) < min_sessions:
        return {
            'has_narrative': False,
            'session_count': len(historical_sessions),
            'reason': f'Insufficient history (need {min_sessions} sessions, have {len(historical_sessions)})'
        }
    
    # Limit to recent N sessions
    recent_sessions = historical_sessions[:num_sessions]
    
    # Extract technique scores (reverse for chronological order)
    technique_scores = [
        s['technique_score'] 
        for s in reversed(recent_sessions) 
        if s.get('technique_score') is not None
    ]
    
    # Extract readiness scores
    readiness_scores = [
        s['readiness_score'] 
        for s in reversed(recent_sessions) 
        if s.get('readiness_score') is not None
    ]
    
    # Detect trends
    trends = {}
    
    if len(technique_scores) >= min_sessions:
        trends['technique'] = detect_trend(technique_scores, min_sessions=min_sessions)
    
    if len(readiness_scores) >= min_sessions:
        trends['readiness'] = detect_trend(readiness_scores, min_sessions=min_sessions)
    
    # Generate narrative summary
    narrative_parts = []
    positive_trends = []
    concerns = []
    
    # Analyze technique trend
    if 'technique' in trends and trends['technique'].get('has_trend'):
        tech_trend = trends['technique']
        if tech_trend['trend'] == 'improving':
            positive_trends.append(f"technique is improving (+{tech_trend['percent_change']:.1f}%)")
        elif tech_trend['trend'] == 'declining':
            concerns.append(f"technique has dipped (-{abs(tech_trend['percent_change']):.1f}%)")
        else:
            narrative_parts.append(f"Technique is holding steady around {tech_trend['recent_avg']:.1f}%")
    
    # Analyze readiness trend
    if 'readiness' in trends and trends['readiness'].get('has_trend'):
        ready_trend = trends['readiness']
        if ready_trend['trend'] == 'improving':
            positive_trends.append(f"readiness is climbing (+{ready_trend['percent_change']:.1f}%)")
        elif ready_trend['trend'] == 'declining':
            concerns.append(f"readiness has dropped (-{abs(ready_trend['percent_change']):.1f}%)")
        else:
            narrative_parts.append(f"Readiness is consistent around {ready_trend['recent_avg']:.1f}/100")
    
    # Build narrative (positives first, then stable, then concerns)
    if positive_trends:
        narrative_parts.insert(0, f"Great progress! Your {' and '.join(positive_trends)}.")
    
    if concerns:
        narrative_parts.append(f"Worth noting: {' and '.join(concerns)}. This could be normal variation or may need attention.")
    
    if not narrative_parts:
        narrative_parts.append("Your performance has been consistent across recent sessions.")
    
    narrative_summary = " ".join(narrative_parts)
    
    # Generate coach's take
    coach_take = _generate_coach_take(trends, len(recent_sessions))
    
    return {
        'has_narrative': True,
        'session_count': len(recent_sessions),
        'trends': trends,
        'narrative_summary': narrative_summary,
        'coach_take': coach_take
    }


def _generate_coach_take(trends: dict, session_count: int) -> str:
    """
    Generate a short coaching insight based on trends.
    
    This is interpretive guidance, not prescriptive instruction.
    Uses encouraging, supportive language.
    
    Args:
        trends: Dict of detected trends
        session_count: Number of sessions analyzed
    
    Returns:
        str: Short coaching insight (1-2 sentences)
    """
    technique_trend = trends.get('technique', {}).get('trend')
    readiness_trend = trends.get('readiness', {}).get('trend')
    
    # Determine overall pattern
    improving_count = sum(1 for t in [technique_trend, readiness_trend] if t == 'improving')
    declining_count = sum(1 for t in [technique_trend, readiness_trend] if t == 'declining')
    
    # Generate appropriate take
    if improving_count >= 2:
        return "You're building momentum across the board. Keep up the consistent work and trust the process."
    elif improving_count == 1 and declining_count == 0:
        return "You're making progress in key areas. Stay focused on fundamentals and the results will follow."
    elif declining_count >= 2:
        return "Recent sessions show some dips. Consider reviewing fundamentals, checking for fatigue, or adjusting training load."
    elif declining_count == 1:
        return "One area has dipped slightly. This is normal - use it as feedback to refine your approach."
    else:
        return f"Solid consistency over {session_count} sessions. Consistency is the foundation of improvement."


# ============================================================================
# Input/Output Configuration
# ============================================================================

# Input video paths (static)
USER_VIDEO = "data/user/input.mp4"
REF_VIDEO = "data/reference/djokovic_backhand.mp4"

# Legacy output paths (kept for backward compatibility)
OUTPUT_USER_OVERLAY = "outputs/overlay_user.mp4"
OUTPUT_REF_OVERLAY = "outputs/overlay_ref.mp4"
OUTPUT_USER_FEATURES = "outputs/user_features.csv"
OUTPUT_REF_FEATURES = "outputs/ref_features.csv"
OUTPUT_REPORT = "outputs/report.md"


def get_video_fps(video_path: str) -> float:
    """Get FPS from video file."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps > 0 else 30.0


def detect_impact_frame(features_df: pd.DataFrame) -> int:
    """
    Detect approximate impact frame via max combined wrist speed.
    
    Args:
        features_df: Features DataFrame with wrist speed columns
        
    Returns:
        Frame number of detected impact
    """
    if 'combined_wrist_speed' not in features_df.columns:
        return len(features_df) // 2  # Default to middle if no speed data
    
    # Find frame with maximum wrist speed
    max_idx = features_df['combined_wrist_speed'].idxmax()
    if pd.isna(max_idx):
        return len(features_df) // 2
    
    return int(features_df.loc[max_idx, 'frame'])


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


def compute_phase_weighted_score(phase_scores: dict, config: dict = None) -> float:
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
        
    Returns:
        Weighted average score (0-100)
    """
    # Use config weights if provided, otherwise use defaults
    weights = get_phase_weights(config)
    
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
                           ref_phase_metrics: dict = None) -> list:
    """
    Rank potential coaching cues by metric deviation magnitude.
    
    Args:
        user_metrics: User's impact metrics
        ref_metrics: Reference impact metrics
        user_phase_metrics: Optional phase-specific user metrics
        ref_phase_metrics: Optional phase-specific reference metrics
        
    Returns:
        List of tuples: (priority_score, cue_text, metric_name, deviation, phase)
    """
    cue_candidates = []
    
    # Analyze impact metrics
    metrics_config = {
        'left_elbow_angle': {
            'weight': 2.0,
            'threshold': 15,
            'high': "**Bend your left elbow more** at contact. Your arm is too straight, reducing control and power transfer.",
            'low': "**Extend your left elbow slightly more** through contact. A bit more extension will add reach and power."
        },
        'right_elbow_angle': {
            'weight': 2.0,
            'threshold': 15,
            'high': "**Keep your right elbow closer to your body** for better stability. Think 'compact arms' through the stroke.",
            'low': "**Allow your right elbow to extend more** through the hitting zone for better racquet speed."
        },
        'hip_rotation': {
            'weight': 2.5,
            'threshold': 5,
            'low_abs': "**Rotate your hips more** into the shot. Your upper body is doing most of the work—engage those hips!",
            'high_abs': "**Control your hip rotation**. Over-rotation can throw off your timing and balance."
        },
        'spine_lean': {
            'weight': 1.5,
            'threshold': 8,
            'high': "**Stay more upright** through contact. You're leaning too much, which affects balance.",
            'low': "**Lean into the shot slightly more** for better weight transfer through the ball."
        },
        'stance_width_normalized': {
            'weight': 2.2,
            'threshold': 0.3,
            'low': "**Widen your stance** for a more stable base. You'll generate more power from your legs.",
            'high': "**Narrow your stance slightly**. Too wide limits your hip rotation and recovery speed."
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
                    "**Bend your knees more** throughout the stroke. Lower stance = more power from the ground up.",
                    'knee_angle_avg',
                    knee_diff,
                    'contact'
                ))
            else:
                cue_candidates.append((
                    deviation_score,
                    "**Don't over-crouch**. Your knees are bending too much, which can slow your recovery.",
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
        phase_cues = get_phase_cues_with_priority(user_phase_metrics, ref_phase_metrics)
        cue_candidates.extend(phase_cues)
    
    # Sort by priority score (descending)
    cue_candidates.sort(key=lambda x: x[0], reverse=True)
    
    return cue_candidates


def get_phase_cues_with_priority(user_phases: dict, ref_phases: dict) -> list:
    """
    Get phase-specific cues with priority scores.
    
    Returns:
        List of tuples: (priority_score, cue_text, metric_name, deviation, phase)
    """
    cues = []
    
    # Preparation phase
    if 'preparation' in user_phases and 'preparation' in ref_phases:
        user_prep = user_phases['preparation']
        ref_prep = ref_phases['preparation']
        
        # Shoulder rotation in prep
        shoulder_diff = abs(user_prep.get('left_shoulder_angle', 0) - ref_prep.get('left_shoulder_angle', 0))
        if shoulder_diff > 25:
            cues.append((
                shoulder_diff * 1.5,
                "**[Preparation]** Turn your shoulders earlier and more completely during the setup phase.",
                'left_shoulder_angle',
                shoulder_diff,
                'preparation'
            ))
        
        # Stance width in prep
        stance_diff = user_prep.get('stance_width_normalized', 0) - ref_prep.get('stance_width_normalized', 0)
        if stance_diff < -0.5:
            cues.append((
                abs(stance_diff) * 25,  # High weight for stance
                "**[Preparation]** Set up with a wider base from the start. Narrow stance limits power generation.",
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
                "**[Load]** Coil your hips more during the loading phase. This is where you store energy for the shot.",
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
                "**[Load]** Drop your center of gravity more in the loading phase. Bend those knees!",
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
                "**[Follow-through]** Extend your arms more through the finish. You're pulling back too early.",
                'left_elbow_angle',
                user_elbow_ext - ref_elbow_ext,
                'follow_through'
            ))
        
        # Balance in follow-through
        spine_diff = user_follow.get('spine_lean', 0) - ref_follow.get('spine_lean', 0)
        if abs(spine_diff) > 10:
            cues.append((
                abs(spine_diff) * 1.3,
                "**[Follow-through]** Maintain better balance through your finish position.",
                'spine_lean',
                spine_diff,
                'follow_through'
            ))
    
    return cues


def generate_coaching_cues(user_metrics: dict, ref_metrics: dict, 
                          user_phase_metrics: dict = None, 
                          ref_phase_metrics: dict = None,
                          limit_primary: int = 2) -> tuple:
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
        user_phase_metrics, ref_phase_metrics
    )
    
    # Extract just the cue text
    all_cues = [cue[1] for cue in ranked_cues]
    
    # Top priority cues for "Today's Focus"
    primary_cues = all_cues[:limit_primary]
    
    # Ensure we have at least minimum cues
    if len(all_cues) < 3:
        fallback_cues = [
            "**Keep your eye on the ball** through contact. Head still, watch the ball hit the strings.",
            "**Follow through completely** toward your target. Don't cut the swing short.",
            "**Relax your grip** slightly. A death-grip reduces racquet head speed."
        ]
        for fallback in fallback_cues:
            if len(all_cues) >= 5:
                break
            if fallback not in all_cues:
                all_cues.append(fallback)
    
    return primary_cues, all_cues[:5], ranked_cues  # Return top 5 total cues


def generate_drills(user_metrics: dict, ref_metrics: dict) -> list:
    """
    Generate drill suggestions based on identified weaknesses.
    
    Args:
        user_metrics: User's impact metrics
        ref_metrics: Reference impact metrics
        
    Returns:
        List of drill descriptions
    """
    drills = []
    
    # Knee bend drill
    avg_user_knee = (user_metrics['left_knee_angle'] + user_metrics['right_knee_angle']) / 2
    avg_ref_knee = (ref_metrics['left_knee_angle'] + ref_metrics['right_knee_angle']) / 2
    
    if avg_user_knee - avg_ref_knee > 10:
        drills.append(
            "**Wall Sits with Shadow Swings**: Stand against a wall in a squat position (knees at 90°). "
            "Hold for 30 seconds while performing slow-motion backhand swings. "
            "This builds leg strength and muscle memory for proper knee bend. Do 3 sets."
        )
    
    # Hip rotation drill
    hip_diff = abs(user_metrics['hip_rotation']) - abs(ref_metrics['hip_rotation'])
    if hip_diff < -3:
        drills.append(
            "**Medicine Ball Rotational Throws**: Stand sideways to a wall, holding a medicine ball (4-8 lbs). "
            "Rotate your hips and core explosively to throw the ball against the wall. "
            "Catch and repeat. Do 2 sets of 10 each side to build rotational power."
        )
    
    # Balance/stance drill
    stance_diff = user_metrics['stance_width_normalized'] - ref_metrics['stance_width_normalized']
    if abs(stance_diff) > 0.2:
        drills.append(
            "**Ladder Footwork Drill**: Use an agility ladder (or tape lines). "
            "Practice split-stepping into your backhand stance, focusing on consistent foot spacing. "
            "Hit shadow strokes at each stop. 5 minutes daily improves footwork consistency."
        )
    
    # General two-handed backhand drills
    if len(drills) < 2:
        drills.append(
            "**One-Arm Backhand Feeds**: Have a partner feed soft balls while you hit backhands with only your "
            "non-dominant hand on the racquet. This strengthens your lead arm and improves control. "
            "Do 20 balls, then switch back to two hands—you'll feel the difference immediately."
        )
    
    if len(drills) < 2:
        drills.append(
            "**Contact Point Drill**: Set up a ball on a cone or have a partner hold one at your ideal contact point. "
            "Practice bringing your racquet to that exact spot with proper form, pausing at contact. "
            "This builds muscle memory for consistent contact. 50 reps before each practice session."
        )
    
    return drills[:2]


def generate_report(
    user_metrics: dict, 
    ref_metrics: dict,
    user_impact_frame: int,
    ref_impact_frame: int,
    user_phases: dict = None,
    ref_phases: dict = None,
    user_phase_metrics: dict = None,
    ref_phase_metrics: dict = None,
    session_id: str = None,
    user_id: str = "default_user",
    user_consistency: dict = None,
    ref_consistency: dict = None,
    phase_weighted_score: float = None,
    progress_deltas: dict = None,
    previous_session_id: str = None,
    ml_similarities: dict = None,
    ml_overall: float = None,
    user_confidence_stats: dict = None,
    user_reliability: dict = None,
    user_phase_stability: dict = None,
    match_readiness: dict = None,
    training_load: dict = None,
    player_baseline: dict = None,
    baseline_comparisons: dict = None,
    progress_narrative: dict = None,
    ball_stats: dict = None,
    rally_data: dict = None
) -> str:
    """
    Generate the coaching report markdown with optional session metadata.
    
    Args:
        user_metrics: User's impact metrics
        ref_metrics: Reference impact metrics
        user_impact_frame: User's detected impact frame
        ref_impact_frame: Reference detected impact frame
        user_phases: User's phase boundaries (optional)
        ref_phases: Reference phase boundaries (optional)
        user_phase_metrics: User's phase-specific metrics (optional)
        ref_phase_metrics: Reference phase-specific metrics (optional)
        session_id: Session ID for metadata (optional)
        user_id: User identifier for metadata (default: "default_user")
        
    Returns:
        Markdown string for the report
    """
    # Generate cues with prioritization
    primary_cues, all_cues, ranked_cues = generate_coaching_cues(
        user_metrics, ref_metrics, 
        user_phase_metrics, ref_phase_metrics
    )
    drills = generate_drills(user_metrics, ref_metrics)
    
    # Compute similarity scores
    overall_score = compute_similarity_score(user_metrics, ref_metrics)
    
    phase_scores = {}
    if user_phase_metrics and ref_phase_metrics:
        phase_scores = compute_phase_similarity_scores(user_phase_metrics, ref_phase_metrics)
    
    # Start report with optional metadata header
    report = ""
    
    if session_id:
        # Add YAML-style metadata header
        generated_at = datetime.now().isoformat()
        ref_video_name = Path(REF_VIDEO).name
        
        report += f"""---
session_id: {session_id}
user_id: {user_id}
reference_video: {ref_video_name}
generated_at: {generated_at}
---

"""
    
    report += """# Two-Handed Backhand Analysis Report

"""
    
    # ========================================================================
    # EXECUTIVE SUMMARY - Quick overview of key findings
    # ========================================================================
    
    # Determine overall performance level
    if overall_score >= 80:
        performance_emoji = "🟢"
        performance_level = "Excellent"
    elif overall_score >= 70:
        performance_emoji = "🟡"
        performance_level = "Good"
    elif overall_score >= 60:
        performance_emoji = "🟡"
        performance_level = "Solid"
    else:
        performance_emoji = "🟠"
        performance_level = "Developing"
    
    report += f"""## 📊 Executive Summary

**Overall Performance: {performance_emoji} {performance_level} ({overall_score:.1f}/100)**

"""
    
    # Top weaknesses from ranked cues
    if len(ranked_cues) >= 2:
        report += f"""**🎯 Key Areas for Improvement:**
"""
        for i in range(min(3, len(ranked_cues))):
            metric_name = ranked_cues[i][2].replace('_', ' ').title()
            deviation = abs(ranked_cues[i][3])
            phase = ranked_cues[i][4].title()
            unit = '°' if 'normalized' not in ranked_cues[i][2] and 'width' not in ranked_cues[i][2] else ''
            report += f"- **{metric_name}** ({phase}): {deviation:.1f}{unit} deviation\n"
        report += "\n"
    
    # Phase performance summary
    if phase_scores:
        weakest_phase = min(phase_scores.items(), key=lambda x: x[1])
        strongest_phase = max(phase_scores.items(), key=lambda x: x[1])
        
        phase_display = {
            'preparation': 'Preparation',
            'load': 'Load',
            'contact': 'Contact',
            'follow_through': 'Follow-through'
        }
        
        report += f"""**📈 Phase Performance:**
- Strongest: {phase_display.get(strongest_phase[0], strongest_phase[0])} ({strongest_phase[1]:.1f}/100)
- Needs Work: {phase_display.get(weakest_phase[0], weakest_phase[0])} ({weakest_phase[1]:.1f}/100)

"""
    
    # Reliability confidence (if available)
    if user_reliability:
        high_count = sum(1 for r in user_reliability.values() if r['level'] == 'High')
        total_count = len(user_reliability)
        confidence_pct = (high_count / total_count * 100) if total_count > 0 else 0
        
        if confidence_pct >= 60:
            confidence_emoji = "✅"
            confidence_text = "High"
        elif confidence_pct >= 40:
            confidence_emoji = "⚠️"
            confidence_text = "Moderate"
        else:
            confidence_emoji = "⚠️"
            confidence_text = "Review"
        
        report += f"""**{confidence_emoji} Measurement Confidence: {confidence_text}**
- {high_count}/{total_count} metrics with high reliability
- Average phase stability: {np.mean([p['overall_score'] for p in user_phase_stability.values()]) if user_phase_stability else 0:.1f}/100

"""
    
    # Progress indicator (if available)
    if progress_deltas and 'overall_score' in progress_deltas:
        delta_val = progress_deltas['overall_score']['delta']
        if delta_val > 2:
            progress_emoji = "📈"
            progress_text = f"Improving (+{delta_val:.1f} points)"
        elif delta_val < -2:
            progress_emoji = "📉"
            progress_text = f"Attention needed ({delta_val:.1f} points)"
        else:
            progress_emoji = "➡️"
            progress_text = "Maintaining"
        
        report += f"""**{progress_emoji} Session Trend: {progress_text}**

"""
    
    report += """---

## Overview

Great work putting in the reps! I've analyzed your two-handed backhand against a professional reference (Djokovic). Below you'll find detailed analysis, specific coaching cues, and practice drills to take your game to the next level.

---

"""
    
    # Add similarity score section
    report += f"""## 🎯 Similarity Score

**Overall Technique Score: {overall_score}/100**

"""
    
    if phase_scores:
        report += "**Phase-by-Phase Scores:**\n\n"
        phase_labels = {
            'preparation': 'Preparation',
            'load': 'Load',
            'contact': 'Contact',
            'follow_through': 'Follow-through'
        }
        for phase_key, phase_label in phase_labels.items():
            if phase_key in phase_scores:
                score = phase_scores[phase_key]
                # Visual indicator
                if score >= 80:
                    indicator = "✓ Strong"
                elif score >= 60:
                    indicator = "~ Good"
                else:
                    indicator = "✗ Needs Work"
                report += f"- **{phase_label}**: {score}/100 {indicator}\n"
        report += "\n"
    
    # Interpretation guide
    if overall_score >= 80:
        interpretation = "Excellent! Your technique is very close to pro level in most areas."
    elif overall_score >= 60:
        interpretation = "Good foundation! Focus on the priority areas below to reach the next level."
    else:
        interpretation = "Significant room for improvement. Focus on the fundamentals highlighted below."
    
    report += f"*{interpretation}*\n\n---\n\n"
    
    # Today's Focus section
    report += """## 🎓 Today's Focus

**Your Top 2 Priorities:**

"""
    
    for i, cue in enumerate(primary_cues, 1):
        report += f"{i}. {cue}\n\n"
    
    if len(ranked_cues) >= 2:
        top_issue = ranked_cues[0]
        report += f"*Primary issue: {top_issue[2].replace('_', ' ').title()} "
        report += f"(deviation: {abs(top_issue[3]):.1f}{'°' if 'normalized' not in top_issue[2] else ''}) "
        report += f"in {top_issue[4]} phase*\n\n"
    
    report += "---\n\n"
    
    # Adaptive Coaching Focus section (if we have reliability/progress data)
    if user_reliability and ranked_cues:
        adaptive_focus = generate_adaptive_coaching_focus(
            ranked_cues=ranked_cues,
            user_reliability=user_reliability,
            user_phase_stability=user_phase_stability,
            progress_deltas=progress_deltas
        )
        
        report += """## 🎯 Adaptive Coaching Focus

This section uses intelligent prioritization based on measurement reliability, consistency, progress tracking, and severity to recommend the most impactful areas to work on.

"""
        
        # Critical issues (if any)
        if adaptive_focus['critical']:
            report += """### 🚨 Critical Issues (Address First)

These issues are severe, reliable, and require immediate attention:

"""
            for i, cue in enumerate(adaptive_focus['critical'][:3], 1):
                report += f"{i}. **{cue['cue_text']}**\n"
                report += f"   - Severity: {abs(cue['deviation']):.1f}{'°' if 'normalized' not in cue['metric'] else ''} deviation\n"
                report += f"   - Reliability: {cue['reliability']}\n"
                report += f"   - Priority Score: {cue['priority_score']:.1f}/100\n"
                if cue['progress_delta'] != 0:
                    trend = "↗" if cue['progress_delta'] > 0 else "↘"
                    report += f"   - Trend: {trend} {'+' if cue['progress_delta'] > 0 else ''}{cue['progress_delta']:.1f} points\n"
                report += "\n"
        
        # Priority issues
        if adaptive_focus['priority']:
            report += """### ⭐ Priority Issues (Focus Next)

Important areas with reliable measurements that need attention:

"""
            for i, cue in enumerate(adaptive_focus['priority'][:3], 1):
                report += f"{i}. **{cue['cue_text']}**\n"
                report += f"   - Deviation: {abs(cue['deviation']):.1f}{'°' if 'normalized' not in cue['metric'] else ''}\n"
                report += f"   - Reliability: {cue['reliability']} | Phase Stability: {cue['phase_stability']:.1f}/100\n"
                report += f"   - Priority Score: {cue['priority_score']:.1f}/100\n"
                report += "\n"
        
        # Monitoring (improvements or less critical)
        if adaptive_focus['monitor']:
            report += """### 📊 Monitoring (Track Progress)

These areas are either improving or require monitoring before acting:

"""
            for i, cue in enumerate(adaptive_focus['monitor'][:3], 1):
                report += f"{i}. **{cue['metric'].replace('_', ' ').title()}** ({cue['phase'].title()})\n"
                report += f"   - Status: {cue['recommendation']}\n"
                if cue['progress_delta'] < -5:
                    report += f"   - 🎉 Improving: {cue['progress_delta']:.1f} points better\n"
                elif cue['reliability'] == 'Low':
                    report += f"   - ⚠️ Low reliability - verify measurement quality\n"
                report += "\n"
        
        # Suppressed issues (low reliability or minor)
        if adaptive_focus['suppressed']:
            report += f"""### 🔇 Deprioritized Issues ({len(adaptive_focus['suppressed'])} items)

The following issues have been deprioritized due to low measurement reliability or minor severity. Focus on the priorities above first.

"""
            suppressed_list = [f"{c['metric'].replace('_', ' ').title()} ({c['reliability']} reliability)" 
                             for c in adaptive_focus['suppressed'][:5]]
            for item in suppressed_list:
                report += f"- {item}\n"
            report += "\n"
        
        report += """### 📈 How Adaptive Coaching Works

**Priority Scoring considers:**
1. **Severity** (40%): How far from pro technique
2. **Reliability** (25%): Measurement confidence
3. **Phase Importance** (20%): Critical phases weighted higher
4. **Consistency** (15%): Stable issues vs random noise
5. **Progress Modifier** (±10%): Escalates worsening issues, deprioritizes improving ones

**Classifications:**
- 🚨 **Critical**: Severe + reliable + persistent → Address immediately
- ⭐ **Priority**: Significant + reliable → Focus on these
- 📊 **Monitor**: Improving or needs verification → Track progress
- 🔇 **Suppressed**: Low reliability or minor → Deprioritized

This ensures you work on issues that are:
- **Real** (high measurement confidence)
- **Significant** (meaningful impact on technique)
- **Actionable** (stable patterns, not random variation)
- **Persistent** (not already improving)

"""
        
        report += "---\n\n"
        
        # Recommended Training Interventions section
        drill_recommendations = generate_adaptive_drill_recommendations(adaptive_focus)
        
        report += """## 💪 Recommended Training Interventions

This section provides specific drills and exercises tailored to your adaptive coaching priorities. Drill intensity and frequency are adjusted based on issue severity, reliability, and progress tracking.

"""
        
        # Critical drills (HIGH urgency)
        if drill_recommendations['critical_drills']:
            report += """### 🚨 High-Priority Drills (Address Immediately)

These drills target critical issues that require urgent attention:

"""
            for i, drill in enumerate(drill_recommendations['critical_drills'], 1):
                report += f"**{i}. {drill['drill_name']}** (Intensive Program)\n\n"
                report += f"**Target**: {drill['issue_metric'].replace('_', ' ').title()} ({drill['issue_phase'].title()} phase)\n\n"
                report += f"**Description**: {drill['drill_description']}\n\n"
                report += f"**Prescription**: {drill['prescription']}\n\n"
                report += f"**Why this drill**: {drill['rationale']}\n\n"
                report += f"**Urgency Reason**: {drill['reason']}\n\n"
                report += "---\n\n"
        
        # Priority drills (MODERATE urgency)
        if drill_recommendations['priority_drills']:
            report += """### ⭐ Priority Drills (Focus Training)

These drills address important areas that need focused work:

"""
            for i, drill in enumerate(drill_recommendations['priority_drills'], 1):
                report += f"**{i}. {drill['drill_name']}** (Moderate Program)\n\n"
                report += f"**Target**: {drill['issue_metric'].replace('_', ' ').title()} ({drill['issue_phase'].title()} phase)\n\n"
                report += f"**Description**: {drill['drill_description']}\n\n"
                report += f"**Prescription**: {drill['prescription']}\n\n"
                report += f"**Why this drill**: {drill['rationale']}\n\n"
                report += "---\n\n"
        
        # Maintenance drills (LOW urgency)
        if drill_recommendations['maintenance_drills']:
            report += """### 📊 Maintenance Drills (Continue Progress)

Light drills to maintain improvements in areas that are already getting better:

"""
            for i, drill in enumerate(drill_recommendations['maintenance_drills'], 1):
                report += f"**{i}. {drill['drill_name']}** (Light Program)\n\n"
                report += f"**Target**: {drill['issue_metric'].replace('_', ' ').title()} ({drill['issue_phase'].title()} phase)\n\n"
                report += f"**Prescription**: {drill['prescription']}\n\n"
                report += f"**Why continue**: {drill['reason']}\n\n"
                report += "---\n\n"
        
        # Suppressed drills note
        if drill_recommendations['suppressed_count'] > 0:
            report += f"""### 🔇 No Drills Recommended ({drill_recommendations['suppressed_count']} issues)

The adaptive coaching engine has deprioritized {drill_recommendations['suppressed_count']} issue(s) due to low measurement reliability. Focus on the drills above first, which target reliable and actionable issues.

"""
        
        # Explanation of drill adaptation
        report += """### 📈 How Drill Recommendations Adapt

**Intensity Levels**:
- **Intensive** (🚨 Critical): Daily practice, high volume, may include resistance training
- **Moderate** (⭐ Priority): 3-5x per week, standard volume, focused repetition
- **Light** (📊 Maintenance): 2-3x per week, lower volume, maintain progress

**Drill Selection Logic**:
1. **Issue Classification**: Critical issues get intensive drills, priorities get moderate drills
2. **Reliability Filtering**: No drills for low-reliability measurements (focus on what's measurable)
3. **Progress Awareness**: Improving areas get light maintenance drills, not intensive ones
4. **Phase Specificity**: Drills target the specific phase where the issue occurs

**Session-to-Session Adaptation**:
- **Worsening issues**: Drills escalate to higher intensity
- **Improving issues**: Drills reduce to maintenance level
- **New issues**: Drills added at appropriate intensity
- **Resolved issues**: Drills removed or reduced

This ensures your practice time is spent efficiently on the most impactful interventions.

"""
        
        report += "---\n\n"
    
    # Progress Since Last Session section
    if progress_deltas and previous_session_id:
        report += """## 📈 Progress Since Last Session

"""
        report += f"*Comparing to session: {previous_session_id}*\n\n"
        
        # Overall score progress
        if 'overall_score' in progress_deltas:
            delta_info = progress_deltas['overall_score']
            status, icon = delta_info['status']
            delta_val = delta_info['delta']
            sign = "+" if delta_val > 0 else ""
            
            report += f"""**Overall Technique Score:** {delta_info['current']}/100 → {status} {icon}
- Previous: {delta_info['previous']}/100
- Change: {sign}{delta_val:.1f} points

"""
        
        # Phase-weighted score progress
        if 'phase_weighted_score' in progress_deltas:
            delta_info = progress_deltas['phase_weighted_score']
            status, icon = delta_info['status']
            delta_val = delta_info['delta']
            sign = "+" if delta_val > 0 else ""
            
            report += f"""**Phase-Weighted Score:** {delta_info['current']}/100 → {status} {icon}
- Previous: {delta_info['previous']}/100
- Change: {sign}{delta_val:.1f} points

"""
        
        # Phase-specific progress
        if 'phase_deltas' in progress_deltas:
            report += "**Phase-by-Phase Progress:**\n\n"
            
            phase_labels = {
                'preparation': 'Preparation',
                'load': 'Load',
                'contact': 'Contact',
                'follow_through': 'Follow-through'
            }
            
            for phase_key, phase_label in phase_labels.items():
                if phase_key in progress_deltas['phase_deltas']:
                    delta_info = progress_deltas['phase_deltas'][phase_key]
                    status, icon = delta_info['status']
                    delta_val = delta_info['delta']
                    sign = "+" if delta_val > 0 else ""
                    
                    report += f"- **{phase_label}**: {delta_info['current']:.1f} → {delta_info['previous']:.1f} "
                    report += f"({sign}{delta_val:.1f}) {icon} {status}\n"
            
            report += "\n"
        
        # Summary interpretation
        improved_count = 0
        regressed_count = 0
        
        if 'overall_score' in progress_deltas:
            if progress_deltas['overall_score']['status'][0] == 'Improved':
                improved_count += 1
            elif progress_deltas['overall_score']['status'][0] == 'Regressed':
                regressed_count += 1
        
        if 'phase_deltas' in progress_deltas:
            for delta_info in progress_deltas['phase_deltas'].values():
                if delta_info['status'][0] == 'Improved':
                    improved_count += 1
                elif delta_info['status'][0] == 'Regressed':
                    regressed_count += 1
        
        if improved_count > regressed_count:
            summary = f"**Overall Trend:** Positive! {improved_count} area(s) improved, {regressed_count} regressed. Keep up the good work!"
        elif regressed_count > improved_count:
            summary = f"**Overall Trend:** {regressed_count} area(s) regressed, {improved_count} improved. Review the coaching cues and focus on fundamentals."
        else:
            summary = "**Overall Trend:** Mixed results. Stay consistent with practice and focus on the priority areas."
        
        report += f"{summary}\n\n---\n\n"
    
    # Key metrics comparison
    report += """## 📊 Key Metrics Comparison

| Metric | Your Stroke | Pro Reference | Difference |
|--------|-------------|---------------|------------|
"""
    
    metric_labels = {
        'left_elbow_angle': 'Left Elbow Angle',
        'right_elbow_angle': 'Right Elbow Angle',
        'left_knee_angle': 'Left Knee Angle',
        'right_knee_angle': 'Right Knee Angle',
        'hip_rotation': 'Hip Rotation',
        'spine_lean': 'Spine Lean',
        'stance_width_normalized': 'Stance Width (norm)',
    }
    
    for key, label in metric_labels.items():
        user_val = user_metrics.get(key, 0)
        ref_val = ref_metrics.get(key, 0)
        diff = user_val - ref_val
        sign = "+" if diff > 0 else ""
        
        if key == 'stance_width_normalized':
            report += f"| {label} | {user_val:.2f} | {ref_val:.2f} | {sign}{diff:.2f} |\n"
        else:
            report += f"| {label} | {user_val:.1f}° | {ref_val:.1f}° | {sign}{diff:.1f}° |\n"
    
    report += f"""
*Impact frame detected: Frame {user_impact_frame} (you) vs Frame {ref_impact_frame} (reference)*

---
"""
    
    # Add phase segmentation section if available
    if user_phases and ref_phases and user_phase_metrics and ref_phase_metrics:
        report += """
## 🔄 Movement Phase Analysis

Your stroke has been segmented into four phases. Here's how each phase compares:

"""
        
        phase_labels = {
            'preparation': 'Preparation',
            'load': 'Load',
            'contact': 'Contact',
            'follow_through': 'Follow-through'
        }
        
        for phase_key, phase_label in phase_labels.items():
            if phase_key in user_phases and phase_key in user_phase_metrics:
                user_start, user_end = user_phases[phase_key]
                ref_start, ref_end = ref_phases[phase_key]
                
                report += f"""### {phase_label} Phase

**Frames**: {user_start}-{user_end} (you) | {ref_start}-{ref_end} (reference)

| Metric | Your Value | Pro Value | Difference |
|--------|-----------|-----------|------------|
"""
                
                user_pm = user_phase_metrics[phase_key]
                ref_pm = ref_phase_metrics[phase_key]
                
                # Key metrics per phase
                key_metrics = ['hip_rotation', 'left_elbow_angle', 'right_elbow_angle', 
                              'left_knee_angle', 'right_knee_angle', 'spine_lean']
                
                for metric in key_metrics:
                    if metric in user_pm and metric in ref_pm:
                        user_val = user_pm[metric]
                        ref_val = ref_pm[metric]
                        if not np.isnan(user_val) and not np.isnan(ref_val):
                            diff = user_val - ref_val
                            sign = "+" if diff > 0 else ""
                            
                            metric_name = metric.replace('_', ' ').title()
                            report += f"| {metric_name} | {user_val:.1f}° | {ref_val:.1f}° | {sign}{diff:.1f}° |\n"
                
                report += "\n"
        
        report += "---\n\n"
    
    # Add Movement Quality & Consistency section if data available
    if user_consistency and ref_consistency and phase_weighted_score is not None:
        report += """## ⚡ Movement Quality & Consistency

This section analyzes the smoothness and repeatability of your technique across the stroke timeline.

"""
        
        # Phase-weighted score
        report += f"""### Phase-Weighted Technique Score

**Overall Quality Score: {phase_weighted_score}/100**

*This score weights contact (35%) and follow-through (25%) more heavily than preparation (15%) and load (25%), reflecting their biomechanical importance.*

"""
        
        # Consistency analysis per phase
        report += """### Consistency Analysis

Lower values indicate more repeatable, controlled movement. Higher values suggest instability or timing issues.

"""
        
        phase_labels = {
            'preparation': 'Preparation',
            'load': 'Load',
            'contact': 'Contact',
            'follow_through': 'Follow-through'
        }
        
        for phase_key, phase_label in phase_labels.items():
            if phase_key in user_consistency and phase_key in ref_consistency:
                report += f"""#### {phase_label} Phase

| Metric | Your Consistency | Pro Consistency | Rating |
|--------|-----------------|-----------------|--------|
"""
                
                user_phase_cons = user_consistency[phase_key]
                ref_phase_cons = ref_consistency[phase_key]
                
                # Key metrics for consistency reporting
                consistency_metrics = [
                    ('hip_rotation', 'Hip Rotation', 'angle'),
                    ('left_elbow_angle', 'Left Elbow', 'angle'),
                    ('right_elbow_angle', 'Right Elbow', 'angle'),
                    ('left_knee_angle', 'Left Knee', 'angle'),
                    ('right_knee_angle', 'Right Knee', 'angle'),
                ]
                
                for metric_key, metric_label, metric_type in consistency_metrics:
                    if metric_key in user_phase_cons and metric_key in ref_phase_cons:
                        user_cons = user_phase_cons[metric_key]
                        ref_cons = ref_phase_cons[metric_key]
                        
                        if not np.isnan(user_cons) and not np.isnan(ref_cons):
                            rating, indicator = interpret_consistency(user_cons, metric_type)
                            report += f"| {metric_label} | {user_cons:.2f}° | {ref_cons:.2f}° | {indicator} {rating} |\n"
                
                report += "\n"
        
        # Interpretation guide
        report += """**Consistency Guide:**
- ✓ Excellent (< 3°): Very stable, professional-level control
- ~ Good (3-6°): Solid technique, minor variations
- ○ Fair (6-10°): Moderate inconsistency, work on timing
- ✗ Inconsistent (> 10°): Significant instability, focus on fundamentals

---

"""
    
    # Add ML-Based Technique Similarity section if available
    if ml_similarities and ml_overall is not None:
        report += """## 🤖 ML-Based Technique Similarity

This section uses machine learning (cosine similarity) to measure how closely your movement pattern matches the professional technique, independent of absolute metric values.

"""
        
        report += f"""**Overall ML Similarity: {ml_overall}/100**

*{interpret_ml_similarity(ml_overall)}*

### How to Interpret These Scores

**What it measures:** Cosine similarity analyzes the *shape* and *pattern* of your technique by comparing 9 biomechanical features (shoulder/elbow/knee angles, hip rotation, spine lean, stance width) across each movement phase.

**What the numbers mean:**
- **85-100**: Excellent pattern match - your technique follows the same biomechanical pattern as the pro
- **70-84**: Good similarity - overall pattern is correct with some refinements needed
- **55-69**: Moderate similarity - technique shows partial alignment but significant differences remain
- **Below 55**: Substantial differences - movement pattern diverges from professional technique

**Key insight:** Unlike rule-based scoring (which measures specific angle deviations), ML similarity captures the *overall coordination pattern*. A high ML score means your body segments move in similar relationships to each other, even if absolute angles differ.

### Phase-by-Phase ML Similarity

"""
        
        phase_labels = {
            'preparation': 'Preparation',
            'load': 'Load',
            'contact': 'Contact',
            'follow_through': 'Follow-through'
        }
        
        for phase_key, phase_label in phase_labels.items():
            if phase_key in ml_similarities and ml_similarities[phase_key] is not None:
                score = ml_similarities[phase_key]
                
                # Visual indicator
                if score >= 85:
                    indicator = "✓ Excellent"
                elif score >= 70:
                    indicator = "~ Good"
                elif score >= 55:
                    indicator = "○ Fair"
                else:
                    indicator = "✗ Needs Work"
                
                report += f"- **{phase_label}**: {score}/100 {indicator}\n"
        
        report += "\n---\n\n"
    
    report += """## 📝 All Coaching Cues

Here's the complete list of areas to work on, ranked by priority:

"""
    
    for i, cue in enumerate(all_cues, 1):
        report += f"{i}. {cue}\n\n"
    
    report += """---

## 💪 Suggested Drills

Try these drills to address the areas we identified:

"""
    
    for i, drill in enumerate(drills, 1):
        report += f"### Drill {i}\n\n{drill}\n\n"
    
    report += """---

"""
    
    # Add System Reliability & Confidence Analysis section (optional)
    if user_confidence_stats and user_reliability:
        report += """## 🔍 System Reliability & Confidence Analysis

This section provides insight into measurement quality and technique stability during your session.

### What This Means

**Measurement Reliability** assesses how consistent and trustworthy each biomechanical measurement is throughout your stroke. High reliability means the system tracked that metric accurately with minimal noise.

**Intra-Phase Stability** measures how consistent your technique is within each movement phase. Higher stability indicates better technique repeatability.

### Measurement Reliability

"""
        
        # Group metrics by reliability level
        high_rel = []
        medium_rel = []
        low_rel = []
        
        for metric, rel_data in user_reliability.items():
            metric_name = metric.replace('_', ' ').title()
            level = rel_data['level']
            std = rel_data['std']
            
            if level == 'High':
                high_rel.append(f"- **{metric_name}**: {std:.1f}° std dev")
            elif level == 'Medium':
                medium_rel.append(f"- **{metric_name}**: {std:.1f}° std dev")
            else:
                low_rel.append(f"- **{metric_name}**: {std:.1f}° std dev")
        
        if high_rel:
            report += f"**✓ High Reliability** - Very stable measurements:\n"
            for item in high_rel:
                report += f"{item}\n"
            report += "\n"
        
        if medium_rel:
            report += f"**~ Medium Reliability** - Moderate variation:\n"
            for item in medium_rel:
                report += f"{item}\n"
            report += "\n"
        
        if low_rel:
            report += f"**✗ Lower Reliability** - Higher variation (may indicate dynamic movement or measurement noise):\n"
            for item in low_rel:
                report += f"{item}\n"
            report += "\n"
        
        # Add phase stability if available
        if user_phase_stability:
            report += """### Technique Stability by Phase

Stability scores indicate how consistent your biomechanics are within each phase (0-100, higher is better):

"""
            phase_labels = {
                'preparation': 'Preparation',
                'load': 'Load',
                'contact': 'Contact',
                'follow_through': 'Follow-through'
            }
            
            for phase_key, phase_label in phase_labels.items():
                if phase_key in user_phase_stability:
                    score = user_phase_stability[phase_key]['overall_score']
                    
                    if score >= 90:
                        indicator = "✓ Excellent"
                    elif score >= 75:
                        indicator = "✓ Good"
                    elif score >= 60:
                        indicator = "~ Fair"
                    else:
                        indicator = "○ Variable"
                    
                    report += f"- **{phase_label}**: {score:.1f}/100 {indicator}\n"
            
            report += "\n"
        
        report += """### Interpretation Guide

**High Reliability Metrics**: These measurements are trustworthy and can be used confidently for technique analysis.

**Medium Reliability Metrics**: Acceptable for analysis but may have some natural variation due to dynamic movement.

**Lower Reliability Metrics**: Use with caution - high variation may be due to:
- Rapid dynamic movement (natural in sports)
- Camera angle or lighting issues
- Occlusion of body landmarks
- Actual technique inconsistency

**Stability Scores**:
- **90-100**: Highly repeatable technique within the phase
- **75-89**: Good consistency with minor variations
- **60-74**: Moderate consistency - some refinement possible
- **<60**: Variable technique - focus on consistency

---

"""
    
    # Add Match Readiness section (optional)
    if match_readiness:
        report += """## 🎯 Match Readiness Assessment

This synthesis combines technique, movement, fatigue, and measurement trust into a single readiness signal.

**IMPORTANT**: This is NOT a performance prediction or injury risk assessment. It is a training and competition guidance signal to help you decide when to compete and how to adjust training intensity.

"""
        
        readiness_score = match_readiness['readiness_score']
        readiness_level = match_readiness['readiness_level']
        confidence = match_readiness['confidence']
        explanation = match_readiness['explanation']
        contributors = match_readiness['contributors']
        flags = match_readiness['flags']
        
        # Display overall readiness
        level_emoji = {
            'Excellent': '🟢',
            'Good': '🟢',
            'Fair': '🟡',
            'Poor': '🔴'
        }
        
        report += f"### Overall Readiness: {level_emoji.get(readiness_level, '⚪')} {readiness_level}\n\n"
        report += f"**Score**: {readiness_score:.1f}/100 (Confidence: {confidence:.0%})\n\n"
        report += f"**Summary**: {explanation}\n\n"
        
        # Display contributors
        report += """### Contributing Factors

This readiness score synthesizes the following components:

"""
        
        for component, data in contributors.items():
            component_names = {
                'technique': '🎾 Technique Quality',
                'movement': '👟 Movement Quality',
                'fatigue': '⚡ Energy Level',
                'trust': '📊 Signal Quality'
            }
            
            name = component_names.get(component, component.title())
            raw_score = data['raw_score']
            weight = data['weight']
            contribution = data['weighted_contribution']
            
            report += f"- **{name}**: {raw_score:.1f}/100 (weight: {weight:.0%}) → contributes {contribution:.1f} points\n"
        
        report += "\n"
        
        # Display flags if any
        if flags:
            report += """### 🚩 Attention Points

"""
            for flag in flags:
                report += f"- {flag}\n"
            report += "\n"
        
        # Add interpretation guide
        report += """### What This Means For You

**Excellent Readiness (85-100)**: You're in peak form. Ready for competition or high-intensity training.

**Good Readiness (70-84)**: Solid condition. Can compete or train hard, but monitor for any warning signs.

**Fair Readiness (55-69)**: Adequate for moderate training. Consider technical drills over high-intensity competition.

**Poor Readiness (<55)**: Focus on recovery, technique refinement, or addressing specific issues before competing.

**Confidence Score**: Reflects data availability and measurement quality. Higher confidence = more reliable assessment.

---

"""
    
    # Add Training Load & Session Planning section (optional)
    if training_load:
        report += """## 🎯 Training Load & Session Planning

This section provides training guidance based on your current readiness, fatigue, and measurement quality.

**IMPORTANT**: This is general training guidance, NOT medical advice or personalized workout prescription. Always consult with qualified coaches and medical professionals before adjusting your training load.

"""
        
        session_type = training_load['session_type']
        intensity = training_load['intensity']
        focus_areas = training_load['focus_areas']
        avoid_areas = training_load['avoid_areas']
        rationale = training_load['rationale']
        confidence = training_load['confidence']
        warnings = training_load['warnings']
        
        # Display recommended session
        intensity_emoji = {
            'Low': '🟢',
            'Moderate': '🟡',
            'High': '🔴'
        }
        
        report += f"### Recommended Session: {session_type}\n\n"
        report += f"**Intensity**: {intensity_emoji.get(intensity, '⚪')} {intensity}\n\n"
        report += f"**Confidence**: {confidence:.0%}\n\n"
        
        # Display rationale
        report += f"### Why This Recommendation?\n\n{rationale}\n\n"
        
        # Display focus areas
        if focus_areas:
            report += """### 🎯 Focus Areas for This Session

"""
            for area in focus_areas:
                report += f"- {area}\n"
            report += "\n"
        
        # Display avoid areas
        if avoid_areas:
            report += """### ⚠️ Areas to Avoid Today

"""
            for area in avoid_areas:
                report += f"- {area}\n"
            report += "\n"
        
        # Display warnings
        if warnings:
            report += """### 🚨 Important Notices

"""
            for warning in warnings:
                report += f"- {warning}\n"
            report += "\n"
        
        # Add session type guide
        report += """### Session Type Guide

**Recovery**: Active recovery, mobility, light movement. No high-intensity work.

**Technique**: Focus on form and mechanics at controlled pace. Quality over quantity.

**Movement**: Footwork patterns, balance, agility work. Moderate intensity acceptable.

**Conditioning**: Fitness-focused training with technique maintenance. Build capacity.

**Full**: Complete training session combining technique, movement, and conditioning.

**Match-sim**: Competition simulation. High intensity, strategic scenarios, mental toughness.

---

"""
    
    # Add Player Baseline & Personalization section (optional)
    if player_baseline and player_baseline.get('has_baseline') and baseline_comparisons:
        report += """## 📊 Personal Baseline & Progress Context

This section provides personalized context by comparing your current session to your personal baseline (average of recent sessions).

**IMPORTANT**: Baselines represent YOUR typical performance, not absolute standards or goals. They help track YOUR relative improvement over time.

"""
        
        session_count = player_baseline['session_count']
        baseline_technique = player_baseline.get('baseline_technique_score')
        baseline_readiness = player_baseline.get('baseline_readiness_score')
        
        report += f"### Your Baseline (computed from {session_count} sessions)\n\n"
        
        if baseline_technique:
            report += f"**Typical Technique Score**: {baseline_technique:.1f}%\n\n"
        
        if baseline_readiness:
            report += f"**Typical Readiness Score**: {baseline_readiness:.1f}/100\n\n"
        
        # Show comparisons
        if baseline_comparisons:
            report += """### Today's Session vs Your Baseline

"""
            
            for metric_key, comparison in baseline_comparisons.items():
                delta_direction = comparison['delta_direction']
                interpretation = comparison['interpretation']
                delta_percent = comparison['delta_percent']
                
                # Choose emoji based on direction
                if delta_direction == 'above':
                    emoji = '📈'
                elif delta_direction == 'below':
                    emoji = '📉'
                else:
                    emoji = '➡️'
                
                report += f"**{emoji} {interpretation}**\n\n"
        
        # Add interpretation guide
        report += """### How to Interpret Baseline Comparisons

**Above Baseline**: You're performing better than your typical level. Good sign!

**Stable (within 5%)**: Consistent with your usual performance. This is normal day-to-day variation.

**Below Baseline**: You're performing below your typical level. Could indicate fatigue, technique regression, or simply a bad day.

**Important Notes**:
- Baselines update automatically as you complete more sessions
- Short-term drops are normal - focus on long-term trends
- Baselines reflect YOUR performance, not professional standards
- Use baselines to track YOUR improvement journey

---

"""
    
    # Add Progress Narrative & Coach Summary section (optional)
    if progress_narrative and progress_narrative.get('has_narrative'):
        report += """## 📈 Progress & Coach Summary

This section provides a coach-style narrative of your recent trends based on the last several sessions.

**IMPORTANT**: This is interpretive analysis based on observed patterns, NOT predictive modeling or performance guarantees. Trends can change - use this as feedback, not forecast.

"""
        
        session_count = progress_narrative['session_count']
        narrative_summary = progress_narrative['narrative_summary']
        coach_take = progress_narrative['coach_take']
        trends = progress_narrative.get('trends', {})
        
        report += f"### Progress Summary (last {session_count} sessions)\n\n"
        report += f"{narrative_summary}\n\n"
        
        # Show trend details
        if trends:
            report += """### Trend Details\n\n"""
            
            if 'technique' in trends and trends['technique'].get('has_trend'):
                tech = trends['technique']
                trend_emoji = {
                    'improving': '📈',
                    'stable': '➡️',
                    'declining': '📉'
                }
                
                emoji = trend_emoji.get(tech['trend'], '➡️')
                report += f"**{emoji} Technique**: {tech['trend'].capitalize()} "
                report += f"(from {tech['earlier_avg']:.1f}% to {tech['recent_avg']:.1f}%, "
                report += f"{tech['percent_change']:+.1f}%)\n\n"
            
            if 'readiness' in trends and trends['readiness'].get('has_trend'):
                ready = trends['readiness']
                trend_emoji = {
                    'improving': '📈',
                    'stable': '➡️',
                    'declining': '📉'
                }
                
                emoji = trend_emoji.get(ready['trend'], '➡️')
                report += f"**{emoji} Readiness**: {ready['trend'].capitalize()} "
                report += f"(from {ready['earlier_avg']:.1f}/100 to {ready['recent_avg']:.1f}/100, "
                report += f"{ready['percent_change']:+.1f}%)\n\n"
        
        # Add coach's take
        report += """### 🎓 Coach's Take\n\n"""
        report += f"{coach_take}\n\n"
        
        # Add interpretation guide
        report += """### How to Interpret Trends

**Improving**: Recent sessions show upward trend. Keep doing what you're doing!

**Stable**: Consistent performance across sessions. Consistency is valuable.

**Declining**: Recent sessions show downward trend. Review fundamentals, check fatigue, adjust training.

**Remember**: Short-term dips are normal. Focus on long-term trends (5-10 sessions).

---

"""
    
    # ==================================================================
    # Ball & Rally Intelligence Section (NEW - Tennis Pro Analytics)
    # ==================================================================
    if ball_stats and rally_data:
        report += """## 🎾 Ball & Rally Intelligence

*Ball tracking powered by YOLOv8 + Tennis Pro Analytics*

"""
        
        # Ball Statistics
        report += """### ⚡ Ball Statistics

"""
        report += f"**Total Ball Detections**: {ball_stats['total_detections']}\n\n"
        report += f"**Average Ball Speed**: {ball_stats['avg_speed']:.1f} px/frame\n\n"
        report += f"**Maximum Ball Speed**: {ball_stats['max_speed']:.1f} px/frame\n\n"
        
        # Speed Distribution
        report += """### 📊 Speed Distribution

"""
        dist = ball_stats['speed_distribution']
        total = sum(dist.values()) if dist.values() else 1
        
        for category, emoji in [('slow', '🟢'), ('medium', '🟡'), ('fast', '🟠'), ('bullet', '🔴')]:
            count = dist.get(category, 0)
            pct = (count / total) * 100 if total > 0 else 0
            report += f"- **{emoji} {category.upper()}**: {pct:.1f}% ({count} shots)\n"
        
        report += "\n"
        
        # Rally Statistics
        if rally_data and rally_data.get('stats'):
            rally_stats = rally_data['stats']
            report += """### 🏓 Rally Analysis

"""
            report += f"**Total Rallies Detected**: {rally_stats.get('total_rallies', 0)}\n\n"
            
            if rally_stats.get('total_rallies', 0) > 0:
                report += f"**Average Rally Length**: {rally_stats.get('avg_rally_length', 0):.1f} shots\n\n"
                report += f"**Longest Rally**: {rally_stats.get('longest_rally', 0)} shots\n\n"
                report += f"**Shortest Rally**: {rally_stats.get('shortest_rally', 0)} shots\n\n"
                report += f"**Average Rally Duration**: {rally_stats.get('avg_duration', 0):.1f} seconds\n\n"
        
        # Court Zones
        report += """### 📍 Shot Placement (Court Zones)

"""
        zones = ball_stats.get('court_zones', {})
        
        # Horizontal zones
        report += "**Horizontal Distribution**:\n"
        h_zones = ['left', 'center', 'right']
        h_total = sum(zones.get(z, 0) for z in h_zones)
        for zone in h_zones:
            count = zones.get(zone, 0)
            pct = (count / h_total) * 100 if h_total > 0 else 0
            report += f"- {zone.capitalize()}: {pct:.1f}% ({count} shots)\n"
        
        report += "\n**Vertical Distribution**:\n"
        v_zones = ['net', 'mid', 'baseline']
        v_total = sum(zones.get(z, 0) for z in v_zones)
        for zone in v_zones:
            count = zones.get(zone, 0)
            pct = (count / v_total) * 100 if v_total > 0 else 0
            report += f"- {zone.capitalize()}: {pct:.1f}% ({count} shots)\n"
        
        report += "\n"
        
        # Visualizations reference
        if session_id:
            report += """### 📸 Visualizations

Check the following files in your session directory:

- **`heatmaps/court_zones.png`**: Shot placement heatmap
- **`heatmaps/speed_distribution.png`**: Speed distribution chart
- **`overlay_broadcast.mp4`**: Broadcast-style video with ball tracking overlay

"""
        
        report += """### 💡 What This Means

**Speed Distribution**: A good mix of speeds shows tactical variety. Too many slow shots may indicate hesitancy; too many fast shots may suggest loss of control.

**Rally Length**: Longer rallies indicate consistency and endurance. Shorter rallies may suggest aggressive play or unforced errors.

**Court Zones**: Balanced zone distribution shows court coverage and tactical awareness. Heavy concentration in one zone may reveal predictability.

---

"""
    
    report += """## 💭 Final Thoughts

Remember: improvement takes time and consistent practice. Focus on one or two cues at a time rather than trying to fix everything at once. Film yourself regularly to track progress.

Keep grinding—your backhand is going to be a weapon!

---
*Report generated by Coach AI*
"""
    
    return report


# ============================================================================
# Ball Tracking & Rally Analysis (Tennis Pro Analytics Integration)
# ============================================================================

def is_ball_tracking_available() -> bool:
    """Check if YOLO model is available for ball tracking."""
    model_path = Path("models/best.pt")
    return model_path.exists()


def run_ball_detection(video_path: str, model_path: str = "models/best.pt", fps: float = 30.0) -> List:
    """
    Run YOLOv8 ball tracking on video.
    
    Args:
        video_path: Path to video file
        model_path: Path to YOLO model weights
        fps: Video frame rate (for timestamp calculation)
    
    Returns:
        List of Ball objects from ball_tracking_models
    """
    try:
        from ultralytics import YOLO
        from vision.ball_tracking_models import Ball, CourtZoneAnalyzer
        import math
        
        if not Path(model_path).exists():
            print(f"  [WARN] Ball tracking model not found at {model_path}")
            return []
        
        print(f"\n[BALL TRACKING] Initializing YOLOv8...")
        model = YOLO(model_path)
        
        # Open video to get dimensions
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"  [WARN] Cannot open video for ball tracking: {video_path}")
            return []
        
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        print(f"[BALL TRACKING] Detecting balls in {total_frames} frames...")
        
        # Run detection with tracking
        results = model.track(str(video_path), persist=True, conf=0.3, verbose=False)
        
        ball_trajectory = []
        prev_ball = None
        
        for frame_idx, result in enumerate(results):
            if frame_idx % 50 == 0:
                progress = (frame_idx / total_frames) * 100
                print(f"  Ball tracking progress: {progress:.1f}%", end='\r')
            
            # Get best detection for this frame
            best_detection = None
            best_conf = 0
            
            if result.boxes is not None:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    if conf > best_conf:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                        best_detection = (cx, cy, conf)
                        best_conf = conf
            
            if best_detection:
                cx, cy, conf = best_detection
                
                # Calculate speed from previous frame
                speed = 0.0
                if prev_ball:
                    dx = cx - prev_ball.x
                    dy = cy - prev_ball.y
                    speed = math.sqrt(dx**2 + dy**2)
                
                # Create Ball object
                ball = Ball(
                    frame_id=frame_idx + 1,  # 1-indexed
                    x=cx,
                    y=cy,
                    speed=speed,
                    timestamp=(frame_idx + 1) / fps,
                    confidence=conf
                )
                
                ball_trajectory.append(ball)
                prev_ball = ball
        
        print(f"\n[BALL TRACKING] Detected {len(ball_trajectory)} ball positions")
        return ball_trajectory
        
    except ImportError:
        print("  [WARN] ultralytics not installed. Ball tracking disabled.")
        print("  Install with: pip install ultralytics")
        return []
    except Exception as e:
        print(f"  [WARN] Ball tracking failed: {e}")
        return []


def compute_ball_statistics(ball_trajectory: List) -> Dict:
    """
    Compute statistics from ball trajectory.
    
    Args:
        ball_trajectory: List of Ball objects
    
    Returns:
        Dictionary with ball statistics
    """
    from vision.ball_tracking_models import RallyStatistics, CourtZoneAnalyzer
    
    if not ball_trajectory:
        return None
    
    stats = RallyStatistics()
    stats.total_frames = len(ball_trajectory)
    stats.ball_detections = len(ball_trajectory)
    
    # Get frame dimensions from first ball (assuming consistent video)
    # Note: We'd need to pass frame dimensions, for now use placeholders
    frame_width = 1920  # Will be updated in run_pipeline
    frame_height = 1080
    
    for ball in ball_trajectory:
        # Update speed stats
        if ball.speed > 0:
            stats.update_speed_stats(ball.speed)
        
        # Update court zones
        h_zone, v_zone = CourtZoneAnalyzer.get_zone(
            ball.x, ball.y, frame_width, frame_height
        )
        stats.update_court_zone(h_zone, v_zone)
    
    return {
        'total_detections': stats.ball_detections,
        'avg_speed': stats.avg_ball_speed,
        'max_speed': stats.max_ball_speed,
        'speed_distribution': stats.speed_distribution,
        'court_zones': stats.court_zones_hit
    }


def run_pipeline(config_path: str = None):
    """
    Run the full analysis pipeline with session management.
    
    Args:
        config_path: Optional path to YAML configuration file.
                    If None, uses hardcoded tennis backhand defaults.
    """
    # Load optional configuration (purely additive, maintains backward compatibility)
    config = load_config(config_path)
    
    print("=" * 60)
    print("Coach AI - Two-Handed Backhand Analysis")
    print("=" * 60)
    
    # Check if input videos exist
    if not Path(USER_VIDEO).exists():
        print(f"\n[ERROR] User video not found at {USER_VIDEO}")
        print("   Please place your video at: data/user/input.mp4")
        return False
    
    if not Path(REF_VIDEO).exists():
        print(f"\n[ERROR] Reference video not found at {REF_VIDEO}")
        print("   Please place reference video at: data/reference/djokovic_backhand.mp4")
        return False
    
    # Initialize session management with fallback
    session_id = None
    output_paths = None
    
    try:
        # Generate unique session ID
        session_id = generate_session_id()
        print(f"\n[SESSION] Session ID: {session_id}")
        
        # Create session directory
        session_dir = create_session_directory(session_id)
        print(f"[SESSION] Output directory: {session_dir}")
        
        # Get session-specific paths
        output_paths = get_session_paths(session_id)
        
    except Exception as e:
        # Fallback to legacy output directory
        print(f"\n[WARNING] Session creation failed: {e}")
        print("[WARNING] Falling back to legacy output mode (outputs/)")
        session_id = None
        
        # Ensure base outputs directory exists
        Path("outputs").mkdir(exist_ok=True)
        
        # Use legacy paths
        output_paths = get_session_paths(session_id=None)
    
    # Get video FPS
    user_fps = get_video_fps(USER_VIDEO)
    ref_fps = get_video_fps(REF_VIDEO)
    
    print(f"\n[VIDEO] User video: {USER_VIDEO} ({user_fps:.1f} fps)")
    print(f"[VIDEO] Reference video: {REF_VIDEO} ({ref_fps:.1f} fps)")
    
    # Step 1: Extract pose landmarks
    print("\n[1/5] Extracting pose landmarks...")
    print("  -> Processing user video...")
    user_landmarks = extract_pose_landmarks(USER_VIDEO)
    
    print("  -> Processing reference video...")
    ref_landmarks = extract_pose_landmarks(REF_VIDEO)
    
    # Step 2: Create overlay videos
    print("\n[2/5] Creating overlay videos...")
    print("  -> User overlay...")
    create_overlay_video(USER_VIDEO, str(output_paths['overlay_user']))
    
    print("  -> Reference overlay...")
    create_overlay_video(REF_VIDEO, str(output_paths['overlay_ref']))
    
    # Note: Broadcast overlay with ball tracking will be created in Step 4.9 after ball detection
    
    # Step 3: Compute features
    print("\n[3/5] Computing biomechanical features...")
    user_features = compute_features_from_landmarks(user_landmarks)
    user_features = compute_wrist_speed(user_features, user_fps)
    save_features(user_features, str(output_paths['features_user']))
    
    ref_features = compute_features_from_landmarks(ref_landmarks)
    ref_features = compute_wrist_speed(ref_features, ref_fps)
    save_features(ref_features, str(output_paths['features_ref']))
    
    # Step 4: Detect impact frames
    print("\n[4/5] Detecting impact frames...")
    user_impact = detect_impact_frame(user_features)
    ref_impact = detect_impact_frame(ref_features)
    print(f"  -> User impact frame: {user_impact}")
    print(f"  -> Reference impact frame: {ref_impact}")
    
    # Get metrics at impact
    user_metrics = get_impact_metrics(user_features, user_impact)
    ref_metrics = get_impact_metrics(ref_features, ref_impact)
    
    # Segment strokes into phases
    print("\n[4.5/5] Segmenting movement phases...")
    user_phases = segment_stroke_phases(user_features, user_impact)
    ref_phases = segment_stroke_phases(ref_features, ref_impact)
    
    print(f"  -> User phases: Prep(0-{user_phases['preparation'][1]}), "
          f"Load({user_phases['load'][0]}-{user_phases['load'][1]}), "
          f"Contact({user_phases['contact'][0]}-{user_phases['contact'][1]}), "
          f"Follow({user_phases['follow_through'][0]}-{user_phases['follow_through'][1]})")
    
    # Compute phase-specific metrics
    user_phase_metrics = compute_phase_metrics(user_features, user_phases)
    ref_phase_metrics = compute_phase_metrics(ref_features, ref_phases)
    
    # Step 4.6: Temporal intelligence - normalize timelines and compute consistency
    print("\n[4.6/5] Computing temporal consistency metrics...")
    
    # Normalize phase timelines to 0-100%
    user_normalized = normalize_phase_timeline(user_features, user_phases)
    ref_normalized = normalize_phase_timeline(ref_features, ref_phases)
    
    # Compute consistency (std dev) within each phase
    user_consistency = compute_phase_consistency(user_normalized)
    ref_consistency = compute_phase_consistency(ref_normalized)
    
    # Compute similarity scores for progress tracking
    overall_score = compute_similarity_score(user_metrics, ref_metrics)
    
    # Compute phase-weighted score (contact and follow-through weighted higher)
    phase_scores = compute_phase_similarity_scores(user_phase_metrics, ref_phase_metrics)
    phase_weighted_score = compute_phase_weighted_score(phase_scores, config=config)
    
    print(f"  -> Overall similarity score: {overall_score}/100")
    print(f"  -> Phase-weighted score: {phase_weighted_score}/100")
    
    # Step 4.7: Progress tracking - compare with previous session
    print("\n[4.7/5] Checking for previous session...")
    previous_session_id = None
    progress_deltas = None
    
    if session_id:  # Only track progress if we have a session ID
        previous_session_id = find_previous_session(base_dir="outputs", current_session_id=session_id)
        
        if previous_session_id:
            print(f"  -> Found previous session: {previous_session_id}")
            
            # Load previous metrics
            previous_metrics = load_previous_metrics(previous_session_id, base_dir="outputs")
            
            if previous_metrics:
                # Prepare current metrics for comparison
                current_metrics = {
                    'overall_score': overall_score,
                    'phase_weighted_score': phase_weighted_score,
                    'phase_scores': phase_scores
                }
                
                # Compute deltas
                progress_deltas = compute_progress_deltas(current_metrics, previous_metrics)
                print(f"  -> Progress computed: {len(progress_deltas)} metrics compared")
            else:
                print("  -> Could not load previous metrics")
        else:
            print("  -> No previous session found (first run)")
    
    # Step 4.8: ML-based similarity analysis
    print("\n[4.8/5] Computing ML-based technique similarity...")
    ml_similarities = None
    ml_overall = None
    
    try:
        # Compute per-phase ML similarities using cosine similarity
        ml_similarities = compute_ml_phase_similarity(user_phase_metrics, ref_phase_metrics, config=config)
        
        # Compute overall weighted ML similarity using config-based weights
        phase_weights = get_phase_weights(config)
        ml_overall = compute_ml_overall_similarity(ml_similarities, phase_weights=phase_weights)
        
        print(f"  -> ML overall similarity: {ml_overall}/100")
        print(f"  -> Phase similarities: Prep={ml_similarities.get('preparation', 'N/A')}, "
              f"Load={ml_similarities.get('load', 'N/A')}, "
              f"Contact={ml_similarities.get('contact', 'N/A')}, "
              f"Follow={ml_similarities.get('follow_through', 'N/A')}")
    except Exception as e:
        print(f"[WARNING] ML similarity computation failed: {e}")
        print("  -> Continuing with rule-based scores only")
    
    # Step 4.9: Compute system reliability and confidence metrics
    print("\n[4.9/5] Computing reliability and confidence metrics...")
    user_confidence_stats = None
    user_reliability = None
    user_phase_stability = None
    
    try:
        # Compute confidence statistics (mean, std) for each metric
        user_confidence_stats = compute_confidence_statistics(user_features, user_phases)
        
        # Assess measurement reliability based on variance
        user_reliability = assess_measurement_reliability(user_confidence_stats)
        
        # Compute intra-phase stability
        user_phase_stability = compute_intra_phase_stability(user_features, user_phases)
        
        # Summary stats
        if user_reliability:
            high_count = sum(1 for r in user_reliability.values() if r['level'] == 'High')
            medium_count = sum(1 for r in user_reliability.values() if r['level'] == 'Medium')
            low_count = sum(1 for r in user_reliability.values() if r['level'] == 'Low')
            print(f"  -> Reliability: {high_count} high, {medium_count} medium, {low_count} low")
        
        if user_phase_stability:
            avg_stability = np.mean([phase['overall_score'] for phase in user_phase_stability.values()])
            print(f"  -> Average phase stability: {avg_stability:.1f}/100")
    
    except Exception as e:
        print(f"  [WARNING] Could not compute reliability metrics: {e}")
        # Continue without reliability metrics
    
    # Step 4.10: Compute match readiness (synthesis layer - read-only)
    match_readiness = None
    
    try:
        print("\n[4.10/5] Computing match readiness...")
        
        # Use phase-weighted score as technique quality (or overall score if not available)
        technique_score = phase_weighted_score if phase_weighted_score else compute_similarity_score(user_metrics, ref_metrics)
        
        # Extract movement metrics if available (from CV extraction)
        movement_data = None
        if hasattr(user_features, 'attrs') and 'movement_metrics' in user_features.attrs:
            movement_data = user_features.attrs['movement_metrics']
        
        # Extract fatigue analysis if available
        fatigue_data = None
        # Note: Fatigue inference would typically run here if we had rally data
        # For now, we skip if not available
        
        # Extract signal quality if available
        signal_quality_data = None
        if hasattr(user_features, 'attrs') and 'signal_quality' in user_features.attrs:
            signal_quality_data = user_features.attrs['signal_quality']
        
        # Compute match readiness
        match_readiness = compute_match_readiness(
            technique_score=technique_score,
            movement_metrics=movement_data,
            fatigue_analysis=fatigue_data,
            signal_quality=signal_quality_data
        )
        
        # Display summary
        if match_readiness:
            level = match_readiness['readiness_level']
            score = match_readiness['readiness_score']
            confidence = match_readiness['confidence']
            print(f"  -> Readiness: {level} ({score:.1f}/100, confidence: {confidence:.0%})")
            
            if match_readiness['flags']:
                print(f"  -> Flags: {len(match_readiness['flags'])} attention points")
    
    except Exception as e:
        print(f"  [WARNING] Could not compute match readiness: {e}")
        # Continue without match readiness
    
    # Step 4.11: Compute training load recommendation (synthesis layer - read-only)
    training_load = None
    
    try:
        print("\n[4.11/5] Computing training load recommendation...")
        
        # Extract adaptive coaching priorities if available
        adaptive_coaching_data = None
        # Note: Adaptive coaching would typically be extracted here if available
        # For now, we skip if not available
        
        # Compute training load recommendation
        training_load = compute_training_load_recommendation(
            match_readiness=match_readiness,
            fatigue_analysis=fatigue_data,
            signal_quality=signal_quality_data,
            adaptive_coaching=adaptive_coaching_data
        )
        
        # Display summary
        if training_load:
            session_type = training_load['session_type']
            intensity = training_load['intensity']
            confidence = training_load['confidence']
            print(f"  -> Recommended: {session_type} session at {intensity} intensity (confidence: {confidence:.0%})")
            
            if training_load['warnings']:
                print(f"  -> Warnings: {len(training_load['warnings'])} advisory note(s)")
    
    except Exception as e:
        print(f"  [WARNING] Could not compute training load: {e}")
        # Continue without training load
    
    # Step 4.12: Compute player baseline (personalization layer - read-only)
    player_baseline = None
    baseline_comparisons = None
    
    try:
        print("\n[4.12/5] Computing player baseline...")
        
        # Load historical sessions
        historical_sessions = load_historical_sessions(output_dir="outputs", max_sessions=10)
        
        if historical_sessions:
            print(f"  -> Found {len(historical_sessions)} historical session(s)")
            
            # Compute baseline
            player_baseline = compute_player_baseline(historical_sessions, min_sessions=3)
            
            if player_baseline.get('has_baseline'):
                print(f"  -> Baseline computed from {player_baseline['session_count']} sessions")
                
                # Compare current session to baseline
                baseline_comparisons = {}
                
                if player_baseline.get('baseline_technique_score') and phase_weighted_score:
                    baseline_comparisons['technique'] = compare_to_baseline(
                        current_value=phase_weighted_score,
                        baseline_value=player_baseline['baseline_technique_score'],
                        metric_name='Technique score'
                    )
                
                if player_baseline.get('baseline_readiness_score') and match_readiness:
                    current_readiness = match_readiness.get('readiness_score')
                    if current_readiness:
                        baseline_comparisons['readiness'] = compare_to_baseline(
                            current_value=current_readiness,
                            baseline_value=player_baseline['baseline_readiness_score'],
                            metric_name='Readiness score'
                        )
                
                if baseline_comparisons:
                    print(f"  -> Generated {len(baseline_comparisons)} baseline comparison(s)")
                
                # Generate progress narrative (uses same historical data)
                try:
                    progress_narrative = generate_progress_narrative(
                        historical_sessions=historical_sessions,
                        num_sessions=5,
                        min_sessions=3
                    )
                    
                    if progress_narrative.get('has_narrative'):
                        print(f"  -> Progress narrative generated ({progress_narrative['session_count']} sessions)")
                    else:
                        progress_narrative = None
                
                except Exception as e:
                    print(f"  [WARNING] Could not generate progress narrative: {e}")
                    progress_narrative = None
            else:
                reason = player_baseline.get('reason', 'Unknown')
                print(f"  -> Insufficient data for baseline: {reason}")
                progress_narrative = None
        else:
            print(f"  -> No historical sessions found")
            progress_narrative = None
    
    except Exception as e:
        print(f"  [WARNING] Could not compute player baseline: {e}")
        # Continue without baseline
        progress_narrative = None
    
    # Step 4.9: Ball tracking and rally analysis (OPTIONAL - graceful degradation)
    ball_trajectory = []
    ball_stats = None
    rally_data = None
    
    if is_ball_tracking_available():
        try:
            print("\n[4.9/5] Running ball tracking & rally analysis...")
            ball_trajectory = run_ball_detection(USER_VIDEO, fps=user_fps)
            
            if ball_trajectory:
                # Compute ball statistics
                ball_stats = compute_ball_statistics(ball_trajectory)
                
                # Segment into rallies (will be used in next step)
                from vision.ball_tracking_models import segment_rallies, compute_rally_statistics
                rallies = segment_rallies(ball_trajectory, user_fps)
                rally_stats = compute_rally_statistics(rallies)
                
                rally_data = {
                    'rallies': rallies,
                    'stats': rally_stats
                }
                
                print(f"  -> Ball tracking complete: {len(ball_trajectory)} detections")
                print(f"  -> Rally analysis: {rally_stats.get('total_rallies', 0)} rallies detected")
                
                # Generate heatmaps if we have session directory
                if session_id and ball_trajectory:
                    try:
                        from vision.broadcast_overlay import (
                            generate_player_heatmap,
                            generate_court_zones_heatmap,
                            generate_speed_distribution_chart
                        )
                        from vision.ball_tracking_models import RallyStatistics
                        
                        # Create heatmaps directory
                        heatmap_dir = Path("outputs") / session_id / "heatmaps"
                        heatmap_dir.mkdir(exist_ok=True)
                        
                        # Get video dimensions
                        cap = cv2.VideoCapture(USER_VIDEO)
                        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        cap.release()
                        
                        print("  -> Generating heatmaps...")
                        
                        # Court zones heatmap (ball placement)
                        generate_court_zones_heatmap(
                            ball_trajectory,
                            frame_width,
                            frame_height,
                            str(heatmap_dir / "court_zones.png")
                        )
                        
                        # Speed distribution chart
                        if ball_stats:
                            rally_stats_obj = RallyStatistics()
                            rally_stats_obj.speed_distribution = ball_stats['speed_distribution']
                            generate_speed_distribution_chart(
                                rally_stats_obj,
                                str(heatmap_dir / "speed_distribution.png")
                            )
                        
                        print(f"  -> Heatmaps saved to {heatmap_dir}")
                    except Exception as e:
                        print(f"  [WARNING] Heatmap generation failed: {e}")
                
                # Generate broadcast overlay video with ball tracking
                if session_id and ball_trajectory and ball_stats:
                    try:
                        from vision.broadcast_overlay import create_broadcast_overlay
                        from vision.ball_tracking_models import RallyStatistics
                        
                        print("  -> Creating broadcast-style overlay video...")
                        
                        # Create RallyStatistics object
                        rally_stats_obj = RallyStatistics()
                        rally_stats_obj.ball_detections = ball_stats['total_detections']
                        rally_stats_obj.avg_ball_speed = ball_stats['avg_speed']
                        rally_stats_obj.max_ball_speed = ball_stats['max_speed']
                        rally_stats_obj.speed_distribution = ball_stats['speed_distribution']
                        rally_stats_obj.court_zones_hit = ball_stats['court_zones']
                        
                        # Create broadcast overlay
                        broadcast_output = Path("outputs") / session_id / "overlay_broadcast.mp4"
                        create_broadcast_overlay(
                            USER_VIDEO,
                            ball_trajectory,
                            str(broadcast_output),
                            rally_stats=rally_stats_obj,
                            fps=user_fps
                        )
                        
                        print(f"  -> Broadcast overlay saved: {broadcast_output}")
                    except Exception as e:
                        print(f"  [WARNING] Broadcast overlay creation failed: {e}")
            else:
                print("  -> No ball detections found")
        except Exception as e:
            print(f"  [WARNING] Ball tracking failed: {e}")
            print("  -> Continuing with pose-only analysis")
            ball_trajectory = []
            ball_stats = None
            rally_data = None
    else:
        print("\n[4.9/5] Ball tracking disabled (no YOLO model found)")
        print("  -> To enable ball tracking, see models/README.md")
    
    # Step 5: Generate report
    print("\n[5/5] Generating coaching report...")
    report = generate_report(
        user_metrics, ref_metrics, 
        user_impact, ref_impact,
        user_phases, ref_phases,
        user_phase_metrics, ref_phase_metrics,
        session_id=session_id,  # Include session metadata if available
        user_consistency=user_consistency,
        ref_consistency=ref_consistency,
        phase_weighted_score=phase_weighted_score,
        progress_deltas=progress_deltas,
        previous_session_id=previous_session_id,
        ml_similarities=ml_similarities,
        ml_overall=ml_overall,
        user_confidence_stats=user_confidence_stats,
        user_reliability=user_reliability,
        user_phase_stability=user_phase_stability,
        match_readiness=match_readiness,
        training_load=training_load,
        player_baseline=player_baseline,
        baseline_comparisons=baseline_comparisons,
        progress_narrative=progress_narrative,
        ball_stats=ball_stats,  # NEW: Ball tracking data
        rally_data=rally_data   # NEW: Rally analysis data
    )
    
    with open(output_paths['report'], 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  -> Saved report to {output_paths['report']}")
    
    # Step 5.5: Track drill outcomes (learning layer - no side effects)
    # This happens AFTER report generation and has no impact on recommendations
    try:
        # Only track if we have previous session data and current drill recommendations were generated
        if previous_session_id and user_phase_metrics:
            # Load previous session's drill recommendations (if stored)
            prev_drill_file = Path("outputs") / previous_session_id / "drill_recommendations.json"
            
            if prev_drill_file.exists():
                with open(prev_drill_file, 'r') as f:
                    prev_drill_recs = json.load(f)
                
                # Track outcomes by comparing previous vs current metrics
                outcomes = track_drill_outcomes(
                    previous_session_id=previous_session_id,
                    previous_session_metrics=None,  # Would need to load from previous session
                    current_session_metrics=user_phase_metrics,
                    drill_recommendations=prev_drill_recs,
                    current_session_id=session_id,
                    reliability_data=user_reliability
                )
                
                # Save outcomes (append-only)
                if outcomes:
                    save_drill_outcomes(outcomes, output_dir="outputs")
                    print(f"  [INFO] Tracked {len(outcomes)} drill outcome(s)")
        
        # Store current session's drill recommendations for next session
        # (generated inside report generation, would need to extract)
        # For now, this is a placeholder for future enhancement
        
    except Exception as e:
        # Silently fail - tracking is optional and should never break the pipeline
        print(f"  [INFO] Drill outcome tracking skipped: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE!")
    print("=" * 60)
    
    if session_id:
        print(f"\n[SESSION] All outputs saved to: {output_paths['output_dir']}")
    
    print(f"\nOutputs generated:")
    print(f"  • {output_paths['overlay_user']}")
    print(f"  • {output_paths['overlay_ref']}")
    print(f"  • {output_paths['features_user']}")
    print(f"  • {output_paths['features_ref']}")
    print(f"  • {output_paths['report']}")
    print(f"\nOpen {output_paths['report']} to see your personalized coaching feedback!")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Coach AI - Sports Technique Analysis")
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to YAML configuration file (optional, defaults to tennis backhand)'
    )
    
    args = parser.parse_args()
    
    success = run_pipeline(config_path=args.config)
    sys.exit(0 if success else 1)

