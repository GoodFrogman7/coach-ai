"""
compare.py
Full pipeline for comparing user video against reference video.
Generates overlay videos, feature CSVs, and coaching report.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

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
            
            # Normalize features (important for angles with different scales)
            scaler = StandardScaler()
            user_vec_scaled = scaler.fit_transform(user_vec)
            ref_vec_scaled = scaler.transform(ref_vec)
            
            # Compute cosine similarity
            cos_sim = cosine_similarity(user_vec_scaled, ref_vec_scaled)[0, 0]
            
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
        }
    }


def map_metric_to_drill_category(metric_name: str) -> str:
    """
    Map a biomechanical metric to its corresponding drill category.
    
    Args:
        metric_name: Name of the metric
        
    Returns:
        Drill category key
    """
    metric_lower = metric_name.lower()
    
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
    user_phase_stability: dict = None
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
    
    report += """## 💭 Final Thoughts

Remember: improvement takes time and consistent practice. Focus on one or two cues at a time rather than trying to fix everything at once. Film yourself regularly to track progress.

Keep grinding—your backhand is going to be a weapon!

---
*Report generated by Coach AI*
"""
    
    return report


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
        user_phase_stability=user_phase_stability
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

