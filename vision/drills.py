"""
drills.py

Drill knowledge base, recommendations, and outcome/effectiveness tracking.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
import numpy as np
from vision.movement import is_movement_metric

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
                    'reason': "Currently improving - maintain progress with light practice"
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
    
    except Exception:
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
    
    except Exception:
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

