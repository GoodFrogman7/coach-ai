"""
compare.py
Full pipeline for comparing a user video against a reference video.

This module was decomposed from a single 7.5k-line file into cohesive modules
(config_session, stroke_profiles, movement, reliability, adaptive, fatigue,
similarity, drills, intelligence, ball_tracking, report). It retains the
pipeline orchestration (run_pipeline) and re-exports every moved name so that
`from vision.compare import X` continues to work for all existing callers.
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

from vision.extract_pose import extract_pose_landmarks, save_landmarks
from vision.overlay_pose import create_overlay_video
from vision.features import (
    compute_features_from_landmarks,
    compute_wrist_speed,
    save_features,
    segment_stroke_phases,
    compute_phase_metrics,
)

# ---------------------------------------------------------------------------
# Re-export the decomposed modules so `from vision.compare import X` still works.
# ---------------------------------------------------------------------------
from vision.config_session import *          # noqa: F401,F403
from vision.stroke_profiles import *         # noqa: F401,F403
from vision.movement import *                # noqa: F401,F403
from vision.reliability import *             # noqa: F401,F403
from vision.adaptive import *                # noqa: F401,F403
from vision.fatigue import *                 # noqa: F401,F403
from vision.similarity import *              # noqa: F401,F403
from vision.drills import *                  # noqa: F401,F403
from vision.intelligence import *            # noqa: F401,F403
from vision.ball_tracking import *           # noqa: F401,F403
from vision.report import *                  # noqa: F401,F403
# Underscore-prefixed helpers are not picked up by `import *`; re-export explicitly
# because existing callers (e.g. test_progress_narrative.py) import them directly.
from vision.config_session import (
    USER_VIDEO, REF_VIDEO, OUTPUT_USER_OVERLAY, OUTPUT_REF_OVERLAY,
    OUTPUT_USER_FEATURES, OUTPUT_REF_FEATURES, OUTPUT_REPORT,
)
from vision.intelligence import _generate_coach_take  # noqa: F401


def get_video_fps(video_path: str) -> float:
    """Get FPS from video file."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps > 0 else 30.0


def validate_video(path: str, role: str = "video") -> Tuple[bool, str]:
    """
    Validate that a path points to a readable video with at least one frame.

    Anticipates the common upload failure modes: missing file, wrong/empty
    path, unsupported codec, and zero-frame/corrupt files.

    Args:
        path: Filesystem path to the video.
        role: Human-readable role for error messages (e.g. "user video").

    Returns:
        (ok, message). When ok is False, message explains why.
    """
    if not path:
        return False, f"No {role} provided."

    p = Path(path)
    if not p.exists():
        return False, f"{role.capitalize()} not found: {path}"

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return False, f"Could not open {role} (unsupported codec or corrupt file): {p.name}"

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    # Frame-count metadata is unreliable for some containers; confirm by reading one frame.
    ok_read, _ = cap.read()
    cap.release()

    if frame_count <= 0 and not ok_read:
        return False, f"{role.capitalize()} contains no readable frames: {p.name}"

    n = frame_count if frame_count > 0 else "?"
    return True, f"OK - {n} frames @ {fps:.0f} fps"


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


def run_pipeline(config_path: str = None, user_video: str = None,
                 ref_video: str = None, stroke: str = "backhand"):
    """
    Run the full analysis pipeline with session management.

    Args:
        config_path: Optional path to YAML configuration file.
                    If None, uses hardcoded tennis backhand defaults.
        user_video: Path to the user's video. Falls back to USER_VIDEO.
        ref_video: Path to the reference video. Falls back to REF_VIDEO.
        stroke: Stroke type being analyzed (backhand, forehand, serve,
                volley, overhead). Recorded in the report metadata.
    """
    # Load optional configuration (purely additive, maintains backward compatibility)
    config = load_config(config_path)

    # Resolve inputs; fall back to the built-in defaults for backward compatibility.
    user_video = user_video or USER_VIDEO
    ref_video = ref_video or REF_VIDEO

    print("=" * 60)
    print("Coach AI - Sports Technique Analysis")
    print("=" * 60)

    # Validate inputs (existence + readable video with frames)
    ok, msg = validate_video(user_video, role="user video")
    if not ok:
        print(f"\n[ERROR] {msg}")
        return False

    ok, msg = validate_video(ref_video, role="reference video")
    if not ok:
        print(f"\n[ERROR] {msg}")
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
    user_fps = get_video_fps(user_video)
    ref_fps = get_video_fps(ref_video)

    print(f"\n[VIDEO] User video: {user_video} ({user_fps:.1f} fps)")
    print(f"[VIDEO] Reference video: {ref_video} ({ref_fps:.1f} fps)")
    print(f"[STROKE] {stroke}")

    # Step 1: Extract pose landmarks
    print("\n[1/5] Extracting pose landmarks...")
    print("  -> Processing user video...")
    user_landmarks = extract_pose_landmarks(user_video)

    print("  -> Processing reference video...")
    ref_landmarks = extract_pose_landmarks(ref_video)

    # Step 2: Create overlay videos
    print("\n[2/5] Creating overlay videos...")
    print("  -> User overlay...")
    create_overlay_video(user_video, str(output_paths['overlay_user']))

    print("  -> Reference overlay...")
    create_overlay_video(ref_video, str(output_paths['overlay_ref']))
    
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
    
    # Stroke-aware phase weighting: non-backhand strokes emphasize different
    # phases (e.g. serve/volley weight contact higher, forehand weights load
    # higher). Backhand keeps the config-derived weights, so a backhand run --
    # including one with a custom --config -- behaves exactly as before.
    stroke_phase_weights = (
        get_stroke_phase_weights(stroke)
        if stroke and stroke.lower().strip() != 'backhand'
        else None
    )
    if stroke_phase_weights:
        print(f"  -> Stroke-aware phase weights ({stroke}): {stroke_phase_weights}")

    # Compute phase-weighted score (contact and follow-through weighted higher)
    phase_scores = compute_phase_similarity_scores(user_phase_metrics, ref_phase_metrics)
    phase_weighted_score = compute_phase_weighted_score(
        phase_scores, config=config, phase_weights=stroke_phase_weights
    )
    
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
        
        # Compute overall weighted ML similarity using stroke-aware weights when
        # a non-backhand stroke is selected, otherwise config-based weights.
        phase_weights = stroke_phase_weights if stroke_phase_weights else get_phase_weights(config)
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
            ball_trajectory = run_ball_detection(user_video, fps=user_fps)
            
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
                        cap = cv2.VideoCapture(user_video)
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
                            user_video,
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
        ref_video=ref_video,
        stroke_type=stroke,
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
    parser.add_argument(
        '--user',
        type=str,
        default=None,
        help='Path to the user video (default: data/user/input.mp4)'
    )
    parser.add_argument(
        '--reference',
        type=str,
        default=None,
        help='Path to the reference video (default: data/reference/djokovic_backhand.mp4)'
    )
    parser.add_argument(
        '--stroke',
        type=str,
        default='backhand',
        choices=['backhand', 'forehand', 'serve', 'volley', 'overhead'],
        help='Stroke type being analyzed (default: backhand)'
    )

    args = parser.parse_args()

    success = run_pipeline(
        config_path=args.config,
        user_video=args.user,
        ref_video=args.reference,
        stroke=args.stroke,
    )
    sys.exit(0 if success else 1)
