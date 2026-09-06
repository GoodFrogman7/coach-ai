"""
intelligence.py

Progress tracking, player baseline, match readiness, training load, narratives.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

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
    fatigue_score = 30.0  # Default low fatigue
    trust_score = 0.8  # Default good trust
    
    if match_readiness:
        readiness_score = match_readiness.get('readiness_score', 70.0)
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
        
        except Exception:
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

