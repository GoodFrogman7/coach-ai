"""
report.py

Coaching report generation (assembles all analysis into report.md).

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import numpy as np
from vision.similarity import (compute_phase_similarity_scores, compute_similarity_score,
                               generate_coaching_cues, generate_drills,
                               interpret_consistency, interpret_ml_similarity)
from vision.adaptive import generate_adaptive_coaching_focus
from vision.drills import generate_adaptive_drill_recommendations
from vision.config_session import REF_VIDEO
from vision.stroke_profiles import STROKE_PROFILES
from vision.comparison import STRATEGY_REFERENCE, STRATEGY_RANGE, describe_strategy

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
    ref_video: str = None,
    stroke_type: str = "backhand",
    handedness: str = "right",
    reference_player: str = None,
    comparison_strategy: str = STRATEGY_REFERENCE,
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
    stroke_key = (stroke_type or 'backhand').lower().strip()
    if stroke_key not in STROKE_PROFILES:
        stroke_key = 'backhand'
    stroke_name = STROKE_PROFILES[stroke_key]['name']
    range_mode = comparison_strategy == STRATEGY_RANGE
    ref_column = 'Expected Range' if range_mode else 'Pro Reference'

    primary_cues, all_cues, ranked_cues = generate_coaching_cues(
        user_metrics, ref_metrics, 
        user_phase_metrics, ref_phase_metrics,
        stroke=stroke_key,
    )
    drills = generate_drills(user_metrics, ref_metrics, stroke=stroke_key)
    
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
        ref_video_name = Path(ref_video).name if ref_video else Path(REF_VIDEO).name

        report += f"""---
session_id: {session_id}
user_id: {user_id}
stroke: {stroke_type}
handedness: {handedness}
reference_video: {ref_video_name if not range_mode else "none"}
reference_player: {reference_player or "unknown"}
comparison: {comparison_strategy}
generated_at: {generated_at}
---

"""
    
    report += f"""# {stroke_name} Analysis Report

"""
    if range_mode:
        report += f"> {describe_strategy(STRATEGY_RANGE, stroke_key)}\n\n"
    
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
        report += """**🎯 Key Areas for Improvement:**
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
    
    compared_to = ("the expected ranges for the stroke" if range_mode
                   else f"a professional reference ({reference_player or 'Djokovic'})")
    report += f"""---

## Overview

Great work putting in the reps! I've analyzed your {stroke_name.lower()} against {compared_to}. Below you'll find detailed analysis, specific coaching cues, and practice drills to take your game to the next level.

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
                    report += "   - ⚠️ Low reliability - verify measurement quality\n"
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
        drill_recommendations = generate_adaptive_drill_recommendations(adaptive_focus, stroke=stroke_key)
        
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
    report += f"""## 📊 Key Metrics Comparison

| Metric | Your Stroke | {ref_column} | Difference |
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
*Impact frame detected: Frame {user_impact_frame} (you){'' if range_mode else f' vs Frame {ref_impact_frame} (reference)'}*

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
            report += "**✓ High Reliability** - Very stable measurements:\n"
            for item in high_rel:
                report += f"{item}\n"
            report += "\n"
        
        if medium_rel:
            report += "**~ Medium Reliability** - Moderate variation:\n"
            for item in medium_rel:
                report += f"{item}\n"
            report += "\n"
        
        if low_rel:
            report += "**✗ Lower Reliability** - Higher variation (may indicate dynamic movement or measurement noise):\n"
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

