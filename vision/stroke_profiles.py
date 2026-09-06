"""
stroke_profiles.py

Stroke Abstraction Layer: per-stroke biomechanical profiles and thresholds.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations

# hip_rotation ranges are on the measured scale: the absolute angle between
# the shoulder line and the hip line (features.py), which sits in roughly
# 0-40 degrees at contact. The values below are PROVISIONAL. They were set
# from one right-handed Djokovic backhand clip (about 7-14 degrees near
# contact) and scaled by stroke using the relative emphasis of the original
# profiles. Phase 2 labels enough clips to calibrate them properly.

STROKE_PROFILES = {
    'backhand': {
        'name': 'Two-Handed Backhand',
        'description': 'Baseline two-handed backhand stroke',
        'biomechanical_intent': {
            'hip_rotation': {
                'expected_range': (5, 35),  # degrees, |shoulder line - hip line|
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
                'expected_range': (10, 45),  # Larger than backhand
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
                'expected_range': (15, 60),  # Maximum rotation
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
                'expected_range': (0, 20),  # Minimal rotation
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
                'expected_range': (10, 50),  # Similar to serve
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
        (10, 45)  # Forehand expects larger rotation than backhand
        
        >>> get_stroke_aware_threshold('hip_rotation', 'backhand')
        (5, 35)  # Backhand default
        
        >>> get_stroke_aware_threshold('hip_rotation', 'unknown_stroke')
        (5, 35)  # Falls back to backhand
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

