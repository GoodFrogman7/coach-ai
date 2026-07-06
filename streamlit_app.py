"""
Coach AI - Product-Grade Gamified Dashboard

Professional, investor-presentable UI with gamification.
Strava/Duolingo-inspired design: clean, modern, motivational (not judgmental).

READ-ONLY: No modifications to intelligence logic.
"""

import streamlit as st
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import re
import sys

try:
    from upload_page import render_upload_page
    UPLOAD_AVAILABLE = True
except ImportError:
    UPLOAD_AVAILABLE = False

# Add vision directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import read-only helpers
try:
    from vision.compare import (
        load_historical_sessions,
        compute_player_baseline,
        generate_progress_narrative,
        compute_drill_confidence_scores
    )
except ImportError:
    load_historical_sessions = None
    compute_player_baseline = None
    generate_progress_narrative = None
    compute_drill_confidence_scores = None

# The upload / "New Analysis" page (write path) lives in upload_page.py
# (render_upload_page). streamlit_app.py itself only reads existing sessions.


# ============================================================================
# Data Loading Helpers
# ============================================================================

def get_latest_session(base_dir: str = "outputs") -> str:
    """Get most recent session directory."""
    try:
        outputs_path = Path(base_dir)
        if not outputs_path.exists():
            return None
        
        sessions = [d.name for d in outputs_path.iterdir() if d.is_dir() and len(d.name) == 19]
        if not sessions:
            return None
        
        return sorted(sessions, reverse=True)[0]
    except:
        return None


def get_recent_sessions(base_dir: str = "outputs", n: int = 10) -> list:
    """Get N most recent session IDs."""
    try:
        outputs_path = Path(base_dir)
        if not outputs_path.exists():
            return []
        
        sessions = [d.name for d in outputs_path.iterdir() if d.is_dir() and len(d.name) == 19]
        return sorted(sessions, reverse=True)[:n]
    except:
        return []


def load_report_data(session_id: str, base_dir: str = "outputs") -> dict:
    """Load all relevant data from session report."""
    try:
        report_path = Path(base_dir) / session_id / "report.md"
        if not report_path.exists():
            return None
        
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        data = {'session_id': session_id, 'raw_content': content}
        
        # Extract technique score (updated format)
        match = re.search(r'Overall Technique Score:\s*(\d+\.?\d*)/100', content)
        if match:
            data['technique_score'] = float(match.group(1))
        else:
            # Fallback to old format
            match = re.search(r'Overall Similarity:\s*\*\*(\d+\.?\d*)%\*\*', content)
            if match:
                data['technique_score'] = float(match.group(1))
        
        # Extract readiness score (use technique score if readiness not found)
        match = re.search(r'## 🎯 Match Readiness Assessment.*?Score\*\*:\s*(\d+\.?\d*)/100', content, re.DOTALL)
        if match:
            data['readiness_score'] = float(match.group(1))
            
            # Extract readiness level
            level_match = re.search(r'Overall Readiness:.*?(Excellent|Good|Fair|Poor)', content)
            if level_match:
                data['readiness_level'] = level_match.group(1)
            
            # Extract readiness confidence
            conf_match = re.search(r'Confidence:\s*(\d+)%', content)
            if conf_match:
                data['readiness_confidence'] = int(conf_match.group(1))
        else:
            # Use technique score as fallback readiness score
            if 'technique_score' in data:
                data['readiness_score'] = data['technique_score']
                # Determine level based on score
                score = data['technique_score']
                if score >= 80:
                    data['readiness_level'] = 'Excellent'
                elif score >= 65:
                    data['readiness_level'] = 'Good'
                elif score >= 45:
                    data['readiness_level'] = 'Fair'
                else:
                    data['readiness_level'] = 'Poor'
                data['readiness_confidence'] = int(min(score, 80))  # Confidence based on score
        
        # Extract training load recommendation
        match = re.search(r'Recommended Session:\s*(\w+)', content)
        if match:
            data['session_type'] = match.group(1)
        else:
            # Infer from technique score
            if 'technique_score' in data:
                score = data['technique_score']
                if score < 50:
                    data['session_type'] = 'Technique'
                elif score < 70:
                    data['session_type'] = 'Refinement'
                else:
                    data['session_type'] = 'Maintenance'
        
        match = re.search(r'Intensity\*\*:.*?(Low|Moderate|High)', content)
        if match:
            data['intensity'] = match.group(1)
        else:
            # Infer intensity
            if 'technique_score' in data:
                score = data['technique_score']
                if score < 60:
                    data['intensity'] = 'Moderate'
                else:
                    data['intensity'] = 'Low'
        
        # Extract focus areas from "Today's Focus" section
        focus_section = re.search(r'## Today\'s Focus.*?Your Top.*?:\s*\n(.*?)\n##', content, re.DOTALL)
        if focus_section:
            focus_text = focus_section.group(1)
            # Extract numbered priorities
            priorities = re.findall(r'\d+\.\s*\*\*\[?([^\]]*?)\]?\*\*\s*(.*?)(?=\n\d+\.|\n\n|\*Primary)', focus_text, re.DOTALL)
            data['focus_areas'] = []
            for phase, description in priorities:
                clean_desc = description.strip().split('\n')[0]  # Get first line only
                data['focus_areas'].append(f"{phase}: {clean_desc}")
        
        # Extract suggested drills
        drill_section = re.search(r'## Suggested Drills.*?\n(.*?)\n---', content, re.DOTALL)
        if drill_section:
            drill_text = drill_section.group(1)
            # Extract drill titles and descriptions
            drills = re.findall(r'### Drill \d+\s*\n\s*\*\*(.*?)\*\*:\s*(.*?)(?=\n\n|### Drill|\Z)', drill_text, re.DOTALL)
            data['drills'] = []
            for title, description in drills:
                data['drills'].append({
                    'title': title.strip(),
                    'description': description.strip()
                })
        
        # Extract avoid areas
        avoid_section = re.search(r'### ⚠️ Areas to Avoid.*?\n(.*?)\n\n', content, re.DOTALL)
        if avoid_section:
            avoid_text = avoid_section.group(1)
            data['avoid_areas'] = [line.strip('- ').strip() for line in avoid_text.split('\n') if line.strip().startswith('-')]
        
        # Extract progress narrative
        narrative_section = re.search(r'### Progress Summary.*?\n\n(.*?)\n\n', content, re.DOTALL)
        if narrative_section:
            data['progress_summary'] = narrative_section.group(1).strip()
        
        # Extract coach's take
        coach_section = re.search(r"### 🎓 Coach's Take\n\n(.*?)\n\n", content, re.DOTALL)
        if coach_section:
            data['coach_take'] = coach_section.group(1).strip()
        
        # Extract baseline comparisons
        baseline_section = re.search(r"Today's Session vs Your Baseline(.*?)###", content, re.DOTALL)
        if baseline_section:
            baseline_text = baseline_section.group(1)
            data['baseline_comparisons'] = []
            
            for line in baseline_text.split('\n'):
                if '📈' in line or '📉' in line or '➡️' in line:
                    data['baseline_comparisons'].append(line.strip('*').strip())
        
        return data
    except:
        return None


def calculate_streak(base_dir: str = "outputs") -> int:
    """Calculate training streak (consecutive days with sessions)."""
    try:
        sessions = get_recent_sessions(base_dir, n=30)
        if not sessions:
            return 0
        
        # Parse dates
        dates = []
        for session_id in sessions:
            try:
                date_str = session_id.split('_')[0]
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                dates.append(date)
            except:
                continue
        
        if not dates:
            return 0
        
        dates = sorted(set(dates), reverse=True)  # Unique dates, newest first
        
        # Calculate streak
        streak = 1
        current_date = dates[0]
        
        for i in range(1, len(dates)):
            next_date = dates[i]
            diff = (current_date - next_date).days
            
            if diff == 1:
                streak += 1
                current_date = next_date
            elif diff > 1:
                break
        
        return streak
    except:
        return 0


def calculate_achievements(base_dir: str = "outputs") -> dict:
    """Calculate achievement badges."""
    try:
        sessions = get_recent_sessions(base_dir, n=30)
        streak = calculate_streak(base_dir)
        
        # Load historical data for improvement tracking
        historical = None
        baseline = None
        
        if load_historical_sessions and compute_player_baseline:
            historical = load_historical_sessions(base_dir, max_sessions=10)
            if historical and len(historical) >= 3:
                baseline = compute_player_baseline(historical, min_sessions=3)
        
        achievements = {
            'consistency': [],
            'improvement': [],
            'discipline': []
        }
        
        # Consistency badges
        if streak >= 7:
            achievements['consistency'].append({
                'name': 'Week Warrior',
                'description': '7-day training streak',
                'icon': '🔥',
                'unlocked': True
            })
        else:
            achievements['consistency'].append({
                'name': 'Week Warrior',
                'description': f'{streak}/7 days',
                'icon': '🔒',
                'unlocked': False
            })
        
        if streak >= 14:
            achievements['consistency'].append({
                'name': 'Fortnight Fighter',
                'description': '14-day training streak',
                'icon': '⚡',
                'unlocked': True
            })
        else:
            achievements['consistency'].append({
                'name': 'Fortnight Fighter',
                'description': f'{streak}/14 days',
                'icon': '🔒',
                'unlocked': False
            })
        
        if streak >= 30:
            achievements['consistency'].append({
                'name': 'Monthly Master',
                'description': '30-day training streak',
                'icon': '👑',
                'unlocked': True
            })
        else:
            achievements['consistency'].append({
                'name': 'Monthly Master',
                'description': f'{streak}/30 days',
                'icon': '🔒',
                'unlocked': False
            })
        
        # Improvement badges
        if baseline and baseline.get('has_baseline'):
            # Check if technique improved vs baseline
            latest_data = load_report_data(sessions[0]) if sessions else None
            
            if latest_data and 'technique_score' in latest_data:
                baseline_tech = baseline.get('baseline_technique_score', 0)
                current_tech = latest_data['technique_score']
                
                if current_tech > baseline_tech * 1.05:  # 5% improvement
                    achievements['improvement'].append({
                        'name': 'Technique Boost',
                        'description': '5% above baseline',
                        'icon': '📈',
                        'unlocked': True
                    })
                else:
                    achievements['improvement'].append({
                        'name': 'Technique Boost',
                        'description': 'Reach 5% above baseline',
                        'icon': '🔒',
                        'unlocked': False
                    })
                
                if current_tech > baseline_tech * 1.10:  # 10% improvement
                    achievements['improvement'].append({
                        'name': 'Breakthrough',
                        'description': '10% above baseline',
                        'icon': '🌟',
                        'unlocked': True
                    })
                else:
                    achievements['improvement'].append({
                        'name': 'Breakthrough',
                        'description': 'Reach 10% above baseline',
                        'icon': '🔒',
                        'unlocked': False
                    })
        
        # Discipline badges
        if len(sessions) >= 5:
            achievements['discipline'].append({
                'name': 'Committed',
                'description': '5+ sessions logged',
                'icon': '🎯',
                'unlocked': True
            })
        else:
            achievements['discipline'].append({
                'name': 'Committed',
                'description': f'{len(sessions)}/5 sessions',
                'icon': '🔒',
                'unlocked': False
            })
        
        if len(sessions) >= 10:
            achievements['discipline'].append({
                'name': 'Dedicated',
                'description': '10+ sessions logged',
                'icon': '💪',
                'unlocked': True
            })
        else:
            achievements['discipline'].append({
                'name': 'Dedicated',
                'description': f'{len(sessions)}/10 sessions',
                'icon': '🔒',
                'unlocked': False
            })
        
        return achievements
    except Exception as e:
        return {'consistency': [], 'improvement': [], 'discipline': []}


# ============================================================================
# UI Components
# ============================================================================

def render_dashboard(session_data, streak):
    """Render Dashboard (Home) screen."""
    st.title("🏠 Dashboard")
    
    # Header stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        readiness = session_data.get('readiness_score', 0)
        level = session_data.get('readiness_level', 'Unknown')
        st.metric("Match Readiness", f"{readiness:.1f}/100", level)
    
    with col2:
        technique = session_data.get('technique_score', 0)
        st.metric("Technique", f"{technique:.1f}%")
    
    with col3:
        st.metric("Training Streak", f"{streak} days", "🔥" if streak > 0 else "")
    
    with col4:
        session_type = session_data.get('session_type', 'Not set')
        st.metric("Today's Plan", session_type)
    
    st.markdown("---")
    
    # Match Readiness Card
    st.subheader("🎯 Match Readiness")
    
    readiness = session_data.get('readiness_score', 0)
    level = session_data.get('readiness_level', 'Unknown')
    confidence = session_data.get('readiness_confidence', 0)
    
    # Color-coded readiness
    if level == 'Excellent':
        color = "🟢"
        bg_color = "#d4edda"
    elif level == 'Good':
        color = "🟡"
        bg_color = "#fff3cd"
    elif level == 'Fair':
        color = "🟠"
        bg_color = "#ffe5d0"
    else:
        color = "🔴"
        bg_color = "#f8d7da"
    
    st.markdown(f"""
    <div style="background-color: {bg_color}; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
        <h2>{color} {level} Readiness</h2>
        <p style="font-size: 24px; font-weight: bold;">{readiness:.1f}/100</p>
        <p style="font-size: 14px; color: #666;">Confidence: {confidence}%</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Training Plan Card
    st.subheader("📋 Today's Training Plan")
    
    session_type = session_data.get('session_type', 'Not available')
    intensity = session_data.get('intensity', 'Not available')
    focus_areas = session_data.get('focus_areas', [])
    avoid_areas = session_data.get('avoid_areas', [])
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        intensity_emoji = {'Low': '🟢', 'Moderate': '🟡', 'High': '🔴'}.get(intensity, '⚪')
        st.markdown(f"**Session Type:** {session_type}")
        st.markdown(f"**Intensity:** {intensity_emoji} {intensity}")
    
    with col2:
        if focus_areas:
            st.markdown("**Focus On:**")
            for area in focus_areas[:2]:  # Top 2
                st.markdown(f"- {area}")
    
    st.markdown("---")
    
    # Motivational Summary
    st.subheader("💬 Coach's Insight")
    
    progress_summary = session_data.get('progress_summary', '')
    coach_take = session_data.get('coach_take', '')
    
    if progress_summary:
        st.info(progress_summary)
    
    if coach_take:
        st.success(f"💡 {coach_take}")
    
    if not progress_summary and not coach_take:
        st.info("Complete more sessions to unlock personalized progress insights!")


def render_progress_trends(base_dir="outputs"):
    """Render Progress & Trends screen."""
    st.title("📈 Progress & Trends")
    
    sessions = get_recent_sessions(base_dir, n=10)
    
    if len(sessions) < 2:
        st.warning("⚠️ Need at least 2 sessions to show trends. Keep training!")
        return
    
    # Load data for all sessions
    session_data = []
    for session_id in reversed(sessions):  # Chronological order
        data = load_report_data(session_id, base_dir)
        if data:
            session_data.append(data)
    
    if not session_data:
        st.warning("⚠️ Could not load session data.")
        return
    
    # Extract metrics
    dates = [s['session_id'].split('_')[0] for s in session_data]
    technique_scores = [s.get('technique_score', None) for s in session_data]
    readiness_scores = [s.get('readiness_score', None) for s in session_data]
    
    # Filter out None values for plotting
    tech_data = [(d, t) for d, t in zip(dates, technique_scores) if t is not None]
    ready_data = [(d, r) for d, r in zip(dates, readiness_scores) if r is not None]
    
    # Technique trend chart
    if tech_data:
        st.subheader("🎾 Technique Progress")
        
        df = pd.DataFrame(tech_data, columns=['Date', 'Technique'])
        df = df.set_index('Date')
        st.line_chart(df)
        
        # Calculate trend
        if len(tech_data) >= 3:
            early_avg = np.mean([t for _, t in tech_data[:len(tech_data)//2]])
            recent_avg = np.mean([t for _, t in tech_data[len(tech_data)//2:]])
            change = ((recent_avg - early_avg) / early_avg) * 100
            
            if change > 3:
                st.success(f"📈 Improving trend: +{change:.1f}%")
            elif change < -3:
                st.warning(f"📉 Declining trend: {change:.1f}%")
            else:
                st.info(f"➡️ Stable: {change:+.1f}%")
    
    st.markdown("---")
    
    # Readiness trend chart
    if ready_data:
        st.subheader("⚡ Readiness Progress")
        
        df = pd.DataFrame(ready_data, columns=['Date', 'Readiness'])
        df = df.set_index('Date')
        st.line_chart(df)
        
        # Calculate trend
        if len(ready_data) >= 3:
            early_avg = np.mean([r for _, r in ready_data[:len(ready_data)//2]])
            recent_avg = np.mean([r for _, r in ready_data[len(ready_data)//2:]])
            change = ((recent_avg - early_avg) / early_avg) * 100
            
            if change > 3:
                st.success(f"📈 Improving trend: +{change:.1f}%")
            elif change < -3:
                st.warning(f"📉 Declining trend: {change:.1f}%")
            else:
                st.info(f"➡️ Stable: {change:+.1f}%")
    
    st.markdown("---")
    
    # Progress Narrative
    st.subheader("📝 Progress Narrative")
    
    latest_data = load_report_data(sessions[0], base_dir)
    if latest_data:
        progress_summary = latest_data.get('progress_summary', '')
        coach_take = latest_data.get('coach_take', '')
        
        if progress_summary:
            st.markdown(f"**Summary:** {progress_summary}")
        
        if coach_take:
            st.markdown(f"**Coach's Take:** {coach_take}")
        
        if latest_data.get('baseline_comparisons'):
            st.markdown("**vs Your Baseline:**")
            for comparison in latest_data['baseline_comparisons']:
                st.markdown(f"- {comparison}")
    
    if not latest_data or not latest_data.get('progress_summary'):
        st.info("Complete more sessions to unlock detailed progress narratives!")


def render_achievements(achievements):
    """Render Achievements & Badges screen."""
    st.title("🏆 Achievements & Badges")
    
    st.markdown("Rewards for consistency, improvement, and discipline.")
    
    # Count unlocked badges
    total_unlocked = sum(
        sum(1 for badge in category if badge['unlocked'])
        for category in achievements.values()
    )
    total_badges = sum(len(category) for category in achievements.values())
    
    st.progress(total_unlocked / total_badges if total_badges > 0 else 0)
    st.markdown(f"**{total_unlocked}/{total_badges} Badges Unlocked**")
    
    st.markdown("---")
    
    # Consistency Badges
    st.subheader("🔥 Consistency Badges")
    st.markdown("*Reward daily training discipline*")
    
    cols = st.columns(3)
    for idx, badge in enumerate(achievements.get('consistency', [])):
        with cols[idx % 3]:
            if badge['unlocked']:
                st.markdown(f"""
                <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 48px;">{badge['icon']}</div>
                    <div style="font-weight: bold;">{badge['name']}</div>
                    <div style="font-size: 12px; color: #666;">{badge['description']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; opacity: 0.6;">
                    <div style="font-size: 48px;">{badge['icon']}</div>
                    <div style="font-weight: bold;">{badge['name']}</div>
                    <div style="font-size: 12px; color: #666;">{badge['description']}</div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Improvement Badges
    st.subheader("📈 Improvement Badges")
    st.markdown("*Reward progress vs your baseline*")
    
    improvement_badges = achievements.get('improvement', [])
    if improvement_badges:
        cols = st.columns(3)
        for idx, badge in enumerate(improvement_badges):
            with cols[idx % 3]:
                if badge['unlocked']:
                    st.markdown(f"""
                    <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px;">
                        <div style="font-size: 48px;">{badge['icon']}</div>
                        <div style="font-weight: bold;">{badge['name']}</div>
                        <div style="font-size: 12px; color: #666;">{badge['description']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; opacity: 0.6;">
                        <div style="font-size: 48px;">{badge['icon']}</div>
                        <div style="font-weight: bold;">{badge['name']}</div>
                        <div style="font-size: 12px; color: #666;">{badge['description']}</div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("Complete more sessions to unlock improvement badges!")
    
    st.markdown("---")
    
    # Discipline Badges
    st.subheader("💪 Discipline Badges")
    st.markdown("*Reward session volume*")
    
    cols = st.columns(3)
    for idx, badge in enumerate(achievements.get('discipline', [])):
        with cols[idx % 3]:
            if badge['unlocked']:
                st.markdown(f"""
                <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 48px;">{badge['icon']}</div>
                    <div style="font-weight: bold;">{badge['name']}</div>
                    <div style="font-size: 12px; color: #666;">{badge['description']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; opacity: 0.6;">
                    <div style="font-size: 48px;">{badge['icon']}</div>
                    <div style="font-weight: bold;">{badge['name']}</div>
                    <div style="font-size: 12px; color: #666;">{badge['description']}</div>
                </div>
                """, unsafe_allow_html=True)


def render_reference_comparison(session_data):
    """Render Reference Style Comparison screen."""
    st.title("🎯 Reference Style Comparison")
    
    st.markdown("Compare your technique to professional reference styles.")
    
    # Reference selector (currently only Djokovic)
    reference = st.selectbox(
        "Select Professional Reference",
        ["Novak Djokovic (Two-Handed Backhand)"]
    )
    
    st.markdown("---")
    
    # Technique score
    technique = session_data.get('technique_score', 0)
    
    st.subheader("📊 Overall Similarity")
    st.progress(technique / 100)
    st.markdown(f"**{technique:.1f}% Similar to {reference.split('(')[0].strip()}**")
    
    st.markdown("---")
    
    # Style gap explanation
    st.subheader("🔍 Style Gap Analysis")
    
    gap = 100 - technique
    
    if gap < 10:
        st.success(f"🌟 Excellent match! Only {gap:.1f}% gap remaining.")
    elif gap < 20:
        st.info(f"👍 Strong similarity with {gap:.1f}% gap to close.")
    elif gap < 30:
        st.warning(f"📝 Good foundation with {gap:.1f}% to refine.")
    else:
        st.info(f"🎯 Building toward reference style. {gap:.1f}% gap represents significant room for growth.")
    
    st.markdown("---")
    
    # Key differences
    st.subheader("📋 Key Differences")
    
    st.info("""
    **Style gaps typically reflect:**
    - Joint angle differences at key phases
    - Timing variations in preparation/contact
    - Body rotation differences
    - Stance width and weight transfer patterns
    
    **Note:** Full metric-by-metric comparison is available in the detailed report.
    """)
    
    st.markdown("---")
    
    # Pro tip
    st.success("💡 **Remember:** The goal isn't to perfectly mimic a pro, but to learn from their efficient movement patterns that suit YOUR body and style.")


def render_training_drills(session_data):
    """Render Training & Drills screen."""
    st.title("💪 Training & Drills")
    
    st.markdown("Personalized drill recommendations based on your current needs.")
    
    # Training plan summary
    session_type = session_data.get('session_type', 'Not available')
    intensity = session_data.get('intensity', 'Not available')
    focus_areas = session_data.get('focus_areas', [])
    avoid_areas = session_data.get('avoid_areas', [])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Today's Plan")
        intensity_emoji = {'Low': '🟢', 'Moderate': '🟡', 'High': '🔴'}.get(intensity, '⚪')
        st.markdown(f"**Type:** {session_type}")
        st.markdown(f"**Intensity:** {intensity_emoji} {intensity}")
    
    with col2:
        st.subheader("🎯 Focus Areas")
        if focus_areas:
            for area in focus_areas:
                st.markdown(f"- {area}")
        else:
            st.markdown("*Check full report for details*")
    
    st.markdown("---")
    
    # Avoid areas (fatigue-aware warnings)
    if avoid_areas:
        st.subheader("⚠️ Areas to Avoid Today")
        for area in avoid_areas:
            st.warning(f"⚠️ {area}")
        st.markdown("---")
    
    # Display suggested drills if available
    drills = session_data.get('drills', [])
    if drills:
        st.subheader("🎾 Suggested Drills")
        st.markdown("**Specific drills for your current needs:**")
        
        for i, drill in enumerate(drills, 1):
            with st.expander(f"**Drill {i}: {drill['title']}**", expanded=True):
                st.markdown(drill['description'])
        
        st.markdown("---")
    
    # Drill categories
    st.subheader("🎾 Drill Categories")
    
    st.markdown("""
    Drills are grouped by focus area and intensity-adjusted based on your current state:
    
    - **Technique Drills**: Form, mechanics, consistency
    - **Movement Drills**: Footwork, balance, agility
    - **Conditioning Drills**: Fitness, endurance, power
    - **Recovery Drills**: Mobility, stretching, light movement
    
    **Full drill prescriptions** with sets, reps, and intensity details are available in your coaching report.
    """)
    
    st.markdown("---")
    
    # Drill confidence
    st.subheader("📊 Drill Effectiveness")
    
    if compute_drill_confidence_scores:
        try:
            scores = compute_drill_confidence_scores()
            
            if scores:
                st.markdown("**Top Effective Drills** (based on your history):")
                
                # Sort by confidence and show top 5
                sorted_drills = sorted(scores.items(), key=lambda x: x[1]['confidence_score'], reverse=True)[:5]
                
                for rank, (drill_name, data) in enumerate(sorted_drills, 1):
                    confidence_level = data['confidence_level']
                    confidence_score = data['confidence_score']
                    
                    # Color-code by confidence
                    if confidence_level == 'High':
                        color = "#d4edda"
                    elif confidence_level == 'Medium':
                        color = "#fff3cd"
                    else:
                        color = "#f8d7da"
                    
                    st.markdown(f"""
                    <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <strong>#{rank}. {drill_name}</strong> - {confidence_level} Confidence ({confidence_score:.2f})
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Complete more sessions to build drill effectiveness data!")
        except:
            st.info("Drill effectiveness tracking not yet available.")
    else:
        st.info("Drill effectiveness tracking not yet available.")


@st.cache_data(show_spinner=False)
def get_cached_answer(
    question: str,
    session_id: str,
    mode: str,
    depth: str,
    strict_grounding: bool,
    base_dir: str = "outputs"
):
    """
    Cached wrapper for retrieval + LLM answer generation.
    
    Caches by: (question, session_id, mode, depth, strict_grounding)
    Returns complete answer object to avoid duplicate Ollama calls.
    Session memory handled outside cache to avoid hashing issues.
    """
    from rag import retrieve_context, ask_coach, extract_session_summary
    import os
    
    # Retrieve relevant context (with embeddings if available)
    # Note: session_memory handled outside cache in render_ask_coach
    retrieval_result = retrieve_context(
        question, 
        top_k=5, 
        use_embeddings=True,
        session_memory=None  # Don't use session_memory in cached function
    )
    retrieved_chunks = retrieval_result['results']
    confidence = retrieval_result['confidence']
    confidence_explanation = retrieval_result['confidence_explanation']
    retrieval_method = retrieval_result.get('method_used', 'tfidf')
    retrieval_stats = retrieval_result.get('retrieval_stats', {})
    
    # Extract session summary
    if session_id:
        report_path = f"{base_dir}/{session_id}/report.md"
        if not os.path.exists(report_path):
            report_path = f"{base_dir}/report.md"
    else:
        sessions = get_recent_sessions(base_dir, n=1)
        report_path = f"{base_dir}/report.md" if sessions else None
    
    session_summary = extract_session_summary(report_path) if report_path and os.path.exists(report_path) else "No recent session data available"
    
    # Get LLM answer with grounding policy
    result = ask_coach(
        question=question,
        retrieved_chunks=retrieved_chunks,
        retrieval_confidence=confidence,
        session_summary=session_summary,
        report_path=report_path,
        mode=mode,
        depth=depth,
        strict_grounding=strict_grounding
    )
    
    # Return complete answer object
    return {
        'answer': result['answer'],
        'used_llm': result.get('used_llm', False),
        'grounding_policy_applied': result.get('grounding_policy_applied', False),
        'policy_reason': result.get('policy_reason', None),
        'retrieved_chunks': retrieved_chunks,
        'confidence': confidence,
        'confidence_explanation': confidence_explanation,
        'retrieval_method': retrieval_method,
        'retrieval_stats': retrieval_stats,
        'session_summary': session_summary,
        'cached': False  # Will be set to True on subsequent calls
    }


def render_ball_rally_analytics(session_id):
    """Render Ball & Rally Analytics screen with tracking data."""
    st.title("📊 Ball & Rally Analytics")
    
    st.markdown("""
    Advanced ball tracking and rally analysis powered by YOLOv8.
    This feature requires a trained YOLO model (`models/best.pt`).
    """)
    
    # Check if session has ball tracking data
    session_dir = Path("outputs") / session_id
    heatmap_dir = session_dir / "heatmaps"
    broadcast_video = session_dir / "overlay_broadcast.mp4"
    
    # Load report data to extract ball stats
    report_path = session_dir / "report.md"
    
    if not report_path.exists():
        st.error("❌ Session report not found")
        return
    
    with open(report_path, 'r', encoding='utf-8') as f:
        report_content = f.read()
    
    # Check if ball tracking data exists
    has_ball_tracking = "Ball & Rally Intelligence" in report_content
    
    if not has_ball_tracking:
        st.info("""
        ℹ️ **Ball tracking not available for this session**
        
        Ball tracking requires:
        - A trained YOLO model at `models/best.pt`
        - See `models/README.md` for setup instructions
        
        This session only contains pose-based analysis.
        Run analysis again after setting up YOLO to see ball tracking data.
        """)
        return
    
    st.success("✅ Ball tracking data available for this session")
    
    # Extract ball statistics from report
    ball_detections = re.search(r'\*\*Total Ball Detections\*\*:\s*(\d+)', report_content)
    avg_speed = re.search(r'\*\*Average Ball Speed\*\*:\s*([\d.]+)\s*px/frame', report_content)
    max_speed = re.search(r'\*\*Maximum Ball Speed\*\*:\s*([\d.]+)\s*px/frame', report_content)
    total_rallies = re.search(r'\*\*Total Rallies Detected\*\*:\s*(\d+)', report_content)
    avg_rally_length = re.search(r'\*\*Average Rally Length\*\*:\s*([\d.]+)\s*shots', report_content)
    
    # Display key metrics
    st.markdown("### 📈 Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if ball_detections:
            st.metric("Total Detections", ball_detections.group(1))
        else:
            st.metric("Total Detections", "N/A")
    
    with col2:
        if avg_speed:
            st.metric("Avg Speed", f"{float(avg_speed.group(1)):.1f} px/f")
        else:
            st.metric("Avg Speed", "N/A")
    
    with col3:
        if max_speed:
            st.metric("Max Speed", f"{float(max_speed.group(1)):.1f} px/f")
        else:
            st.metric("Max Speed", "N/A")
    
    with col4:
        if total_rallies:
            st.metric("Total Rallies", total_rallies.group(1))
        else:
            st.metric("Total Rallies", "N/A")
    
    st.markdown("---")
    
    # Speed Distribution
    st.markdown("### ⚡ Speed Distribution")
    
    speed_dist = {}
    for category in ['SLOW', 'MEDIUM', 'FAST', 'BULLET']:
        match = re.search(rf'\*\*.*?{category}\*\*:\s*([\d.]+)%', report_content)
        if match:
            speed_dist[category] = float(match.group(1))
    
    if speed_dist:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Create bar chart
            import plotly.graph_objects as go
            
            colors = {'SLOW': '#00FF64', 'MEDIUM': '#00FFFF', 'FAST': '#00A5FF', 'BULLET': '#FF0000'}
            
            fig = go.Figure(data=[
                go.Bar(
                    x=list(speed_dist.keys()),
                    y=list(speed_dist.values()),
                    marker_color=[colors.get(k, '#888888') for k in speed_dist.keys()],
                    text=[f"{v:.1f}%" for v in speed_dist.values()],
                    textposition='auto',
                )
            ])
            
            fig.update_layout(
                title="Ball Speed Distribution",
                xaxis_title="Speed Category",
                yaxis_title="Percentage (%)",
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("**Interpretation:**")
            for category, pct in speed_dist.items():
                emoji = {'SLOW': '🟢', 'MEDIUM': '🟡', 'FAST': '🟠', 'BULLET': '🔴'}
                st.markdown(f"{emoji.get(category, '⚪')} **{category}**: {pct:.1f}%")
            
            # Add interpretation
            st.markdown("")
            if speed_dist.get('SLOW', 0) > 50:
                st.info("🎯 Mostly slow shots - good for control, but consider adding pace variety")
            elif speed_dist.get('BULLET', 0) > 30:
                st.warning("⚡ High percentage of fast shots - ensure consistency isn't sacrificed")
            else:
                st.success("✅ Good speed distribution - shows tactical variety")
    
    st.markdown("---")
    
    # Rally Analysis
    if total_rallies and avg_rally_length:
        st.markdown("### 🏓 Rally Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Average Rally Length", f"{float(avg_rally_length.group(1)):.1f} shots")
            
            longest_rally = re.search(r'\*\*Longest Rally\*\*:\s*(\d+)\s*shots', report_content)
            if longest_rally:
                st.metric("Longest Rally", f"{longest_rally.group(1)} shots")
        
        with col2:
            shortest_rally = re.search(r'\*\*Shortest Rally\*\*:\s*(\d+)\s*shots', report_content)
            if shortest_rally:
                st.metric("Shortest Rally", f"{shortest_rally.group(1)} shots")
            
            avg_duration = re.search(r'\*\*Average Rally Duration\*\*:\s*([\d.]+)\s*seconds', report_content)
            if avg_duration:
                st.metric("Avg Duration", f"{float(avg_duration.group(1)):.1f}s")
        
        st.markdown("---")
    
    # Heatmaps
    st.markdown("### 🗺️ Visual Analytics")
    
    tabs = st.tabs(["Court Zones", "Speed Distribution", "Broadcast Video"])
    
    with tabs[0]:
        if (heatmap_dir / "court_zones.png").exists():
            st.markdown("**Shot Placement Heatmap**")
            st.image(str(heatmap_dir / "court_zones.png"), use_container_width=True)
            st.caption("Heatmap showing where your shots landed on the court")
        else:
            st.info("Court zones heatmap not available")
    
    with tabs[1]:
        if (heatmap_dir / "speed_distribution.png").exists():
            st.markdown("**Speed Distribution Chart**")
            st.image(str(heatmap_dir / "speed_distribution.png"), use_container_width=True)
            st.caption("Detailed breakdown of ball speed categories")
        else:
            st.info("Speed distribution chart not available")
    
    with tabs[2]:
        if broadcast_video.exists():
            st.markdown("**Broadcast-Style Overlay**")
            st.video(str(broadcast_video))
            st.caption("Video with real-time ball tracking, speed indicators, and analytics overlay")
        else:
            st.info("Broadcast overlay video not available")
    
    st.markdown("---")
    
    # Technical details
    with st.expander("🔧 Technical Details"):
        st.markdown("""
        **Ball Tracking Technology:**
        - **Model**: YOLOv8 (You Only Look Once)
        - **Detection**: Real-time ball position tracking
        - **Speed Calculation**: Frame-to-frame displacement
        - **Rally Segmentation**: Temporal gap analysis
        
        **Metrics Explained:**
        - **px/frame**: Pixels per frame - measures ball movement between frames
        - **Court Zones**: 3x3 grid (left/center/right × net/mid/baseline)
        - **Speed Categories**: Slow (<8), Medium (8-20), Fast (20-35), Bullet (>35 px/f)
        """)


def render_ask_coach(base_dir="outputs", selected_session=None):
    """Render Ask Coach AI screen with RAG-powered Q&A, UI controls, and Q&A history."""
    st.title("🤖 Ask Coach AI")
    
    st.markdown("Get AI-generated explanations with strict grounding in your data and knowledge base.")
    
    # Import RAG modules
    try:
        from rag import retrieve_context, ask_coach, extract_session_summary, log_qa_interaction, get_recent_questions, load_qa_log
        from rag.session_memory import get_or_create_session_memory
        rag_available = True
    except ImportError:
        st.error("⚠️ RAG system not available. Please ensure the `rag` module is installed.")
        rag_available = False
        return
    
    # Initialize session memory (session-only, no persistence)
    session_memory = get_or_create_session_memory(st.session_state)
    
    # Check if index exists
    import os
    if not os.path.exists("rag/index_meta.json"):
        st.warning("⚠️ Knowledge base index not found.")
        st.markdown("**One-click setup:**")
        st.code("python rag/index_kb.py", language="bash")
        if st.button("📖 Show Setup Instructions"):
            st.info("""
            1. Open a terminal in the project directory
            2. Run: `python rag/index_kb.py`
            3. Wait ~2 seconds for indexing to complete
            4. Refresh this page
            """)
        return
    
    # Initialize session state for question input (SINGLE SOURCE OF TRUTH)
    if "user_question" not in st.session_state:
        st.session_state.user_question = ""
    
    # Initialize session state for answer display
    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False
    
    if "current_answer" not in st.session_state:
        st.session_state.current_answer = None
    
    # Two-column layout: Main Q&A | Recent Questions sidebar
    col_main, col_history = st.columns([2, 1])
    
    with col_history:
        st.subheader("📜 Recent Questions")
        
        if selected_session:
            recent_qa = get_recent_questions(selected_session, n=5, output_dir=base_dir)
            
            if recent_qa:
                for i, qa in enumerate(recent_qa):
                    # Create button for each past question
                    if st.button(f"Q: {qa['question'][:40]}...", key=f"past_q_{i}", use_container_width=True):
                        # Load saved answer WITHOUT calling retrieval or LLM
                        st.session_state.user_question = qa['question']
                        st.session_state.show_answer = True
                        st.session_state.current_answer = {
                            'answer': qa['answer'],
                            'used_llm': True,  # Assume was LLM generated
                            'grounding_policy_applied': qa.get('strict_grounding', True),
                            'policy_reason': None,
                            'retrieved_chunks': qa.get('sources', []),
                            'confidence': qa.get('retrieval_confidence', 'Unknown'),
                            'confidence_explanation': f"Loaded from saved answer (asked {qa['timestamp'][:19]})",
                            'session_summary': "From saved Q&A log",
                            'cached': True,
                            'from_history': True
                        }
                        st.rerun()
                    
                    # Show preview in expander
                    with st.expander(f"Preview", expanded=False):
                        st.caption(f"**Asked:** {qa['timestamp'][:19]}")
                        st.caption(f"**Confidence:** {qa['retrieval_confidence']}")
                        st.caption(f"**Mode:** {qa['mode']}")
                        if qa.get('sources'):
                            st.caption(f"**Sources:** {len(qa['sources'])}")
            else:
                st.info("No questions asked yet for this session.")
        else:
            st.info("Select a session to view Q&A history.")
    
    with col_main:
        # UI Controls
        st.subheader("⚙️ Answer Controls")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            mode = st.selectbox(
                "Mode",
                ["Explain my session", "Teach the concept", "Drill how-to"],
                help="Choose the focus of the answer"
            )
        
        with col2:
            depth = st.selectbox(
                "Depth",
                ["Quick", "Detailed"],
                help="Quick: 2-3 paragraphs, Detailed: comprehensive explanation"
            )
        
        with col3:
            strict_grounding = st.checkbox(
                "Strict grounding",
                value=True,
                help="Recommended: Prevents LLM hallucination by enforcing source citations"
            )
        
        if strict_grounding:
            st.info("🛡️ **Strict Grounding ON**: Low-confidence retrievals won't call LLM (prevents hallucination)")
        
        st.markdown("---")
        
        # Question input
        st.subheader("💬 Ask Your Question")
        
        # Example questions as buttons
        example_questions = [
            "How do I improve my hip rotation?",
            "What causes balance drift?",
            "Why is my recovery time important?",
            "How should I film my strokes?",
            "What does my match readiness score mean?",
            "When should I do recovery sessions vs full training?"
        ]
        
        st.markdown("**Quick Examples:**")
        cols = st.columns(3)
        
        # Handle example button clicks - set session_state directly
        for i, q in enumerate(example_questions):
            with cols[i % 3]:
                if st.button(f"💡 {q[:30]}...", key=f"example_{i}"):
                    st.session_state.user_question = q
                    st.session_state.show_answer = False  # Reset answer display
                    st.rerun()
        
        # Text input - SINGLE SOURCE OF TRUTH using session_state
        question = st.text_input(
            "Or type your own question:",
            value=st.session_state.user_question,
            placeholder="e.g., Why is my hip rotation score low?",
            key="question_input_widget",
            on_change=lambda: setattr(st.session_state, 'user_question', st.session_state.question_input_widget)
        )
        
        # Get answer button
        if st.button("🔍 Get Answer", type="primary", key="get_answer_btn"):
            # Read question from session state (SINGLE SOURCE OF TRUTH)
            current_question = st.session_state.user_question.strip()
            
            if not current_question:
                st.warning("Please enter a question.")
            else:
                # Call cached answer function
                with st.spinner("🤔 Thinking..."):
                    # Get cached answer (will only call LLM once per unique combination)
                    result = get_cached_answer(
                        question=current_question,
                        session_id=selected_session or "",
                        mode=mode,
                        depth=depth,
                        strict_grounding=strict_grounding,
                        base_dir=base_dir
                    )
                    
                    # Mark as cached if this is not first call
                    # (Streamlit cache will make subsequent calls instant)
                    result['cached'] = True
                    
                    # Update session memory AFTER getting cached result
                    if session_memory and result.get('retrieval_stats'):
                        session_memory.add_query(
                            query=current_question,
                            intent=result['retrieval_stats'].get('intent', 'UNKNOWN'),
                            kb_sources=[c.get('filename', '') for c in result.get('retrieved_chunks', []) if isinstance(c, dict)],
                            confidence=result.get('confidence', 'Low'),
                            top_score=result['retrieval_stats'].get('top1_score', 0.0)
                        )
                    
                    # Log Q&A interaction
                    if selected_session:
                        log_qa_interaction(
                            session_id=selected_session,
                            question=current_question,
                            answer=result['answer'],
                            retrieved_sources=result['retrieved_chunks'],
                            retrieval_confidence=result['confidence'],
                            mode=mode,
                            depth=depth,
                            strict_grounding=strict_grounding,
                            output_dir=base_dir
                        )
                    
                    # Store answer in session state
                    st.session_state.show_answer = True
                    st.session_state.current_answer = result
        
        # Display answer if available (outside button click to persist across reruns)
        if st.session_state.show_answer and st.session_state.current_answer:
            result = st.session_state.current_answer
            
            st.markdown("---")
            st.subheader("💡 Coach AI Answer")
            
            # Show grounding policy notice if applied
            if result.get('grounding_policy_applied') and not result.get('used_llm'):
                st.warning(f"🛡️ **Grounding Policy Applied**: {result.get('policy_reason')}")
            
            st.markdown(result['answer'])
            
            # Developer visibility caption
            llm_status = "Yes" if result.get('used_llm') else "No"
            confidence_status = result.get('confidence', 'Unknown')
            cached_status = "Yes (from history)" if result.get('from_history') else ("Yes" if result.get('cached') else "No")
            retrieval_method = result.get('retrieval_method', 'tfidf').upper()
            st.caption(f"🔧 LLM used: {llm_status} | Source confidence: {confidence_status} | Cached: {cached_status} | Retrieval: {retrieval_method}")
            
            st.markdown("---")
            
            # Sources display (always visible)
            st.subheader("📚 Sources Used")
            
            # Show intent classification
            retrieval_stats = result.get('retrieval_stats', {})
            intent = retrieval_stats.get('intent', 'UNKNOWN')
            intent_desc = retrieval_stats.get('intent_description', 'General inquiry')
            
            # Check for recurring issues (session memory)
            has_recurring_issue = retrieval_stats.get('recurring_issue', False)
            issue_topics = retrieval_stats.get('issue_topics', [])
            
            if has_recurring_issue and issue_topics:
                # Display recurring issue notice
                topics_str = ', '.join(issue_topics)
                st.info(f"🔄 **Recurring Topic:** This question relates to **{topics_str}**, which you've asked about earlier in this session.")
            
            if intent != 'UNKNOWN':
                # Show intent badge with color coding
                intent_colors = {
                    'WHY': '🔍',
                    'HOW': '🛠️',
                    'WHAT': '📖',
                    'DIAGNOSE': '🔬',
                    'COMPARE': '⚖️',
                }
                intent_icon = intent_colors.get(intent, '❓')
                st.info(f"{intent_icon} **Detected Intent:** {intent} — {intent_desc}")
            
            # Show retrieval method and stats
            if retrieval_stats:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Method", result.get('retrieval_method', 'tfidf').upper())
                with col2:
                    st.metric("Intent", intent)
                with col3:
                    st.metric("Top1 Score", f"{retrieval_stats.get('top1_score', 0.0):.3f}")
                with col4:
                    st.metric("Avg Top3", f"{retrieval_stats.get('avg_top3', 0.0):.3f}")
            
            st.markdown(f"**Retrieval Confidence:** {result['confidence']}")
            st.caption(result['confidence_explanation'])
            
            # Suggest rephrasings for low confidence
            if result['confidence'] == 'Low' and not result.get('from_history'):
                st.warning("💡 **Try Rephrasing Your Question:**")
                
                # Detect topic and suggest rephrasings
                question_lower = st.session_state.user_question.lower()
                suggestions = []
                
                if any(word in question_lower for word in ['balance', 'drift', 'sway', 'lean']):
                    suggestions = [
                        "Why do I sway sideways when hitting?",
                        "What causes me to lose balance during strokes?",
                        "How do I stop leaning sideways?"
                    ]
                elif any(word in question_lower for word in ['recovery', 'recover', 'slow', 'back']):
                    suggestions = [
                        "Why is recovery time important?",
                        "How do I get back to ready position faster?",
                        "What slows down my recovery?"
                    ]
                elif any(word in question_lower for word in ['split', 'step', 'footwork', 'move']):
                    suggestions = [
                        "How do I improve my split step?",
                        "When should I split step?",
                        "What is good footwork in tennis?"
                    ]
                else:
                    suggestions = [
                        "Try being more specific about what you want to know",
                        "Ask about a specific metric or technique",
                        "Rephrase using terms from your analysis report"
                    ]
                
                for suggestion in suggestions:
                    st.caption(f"• {suggestion}")
            
            retrieved_chunks = result.get('retrieved_chunks', [])
            if retrieved_chunks:
                for i, chunk in enumerate(retrieved_chunks, 1):
                    # Handle both dict chunks and source records from history
                    if isinstance(chunk, dict):
                        title = chunk.get('title', 'Unknown')
                        score = chunk.get('score', 0.0)
                        filename = chunk.get('filename', 'unknown.md')
                        st.markdown(f"{i}. **{title}** (relevance: {score:.2f}) - *{filename}*")
            else:
                st.info("No specific KB sources found.")
            
            # Context used expander
            with st.expander("🔍 Full Context Details", expanded=False):
                st.markdown("**Your Current Session:**")
                st.text(result.get('session_summary', 'No session data'))
                
                if retrieved_chunks and not result.get('from_history'):
                    st.markdown("---")
                    st.markdown("**Retrieved Knowledge Base Excerpts:**")
                    for i, chunk in enumerate(retrieved_chunks, 1):
                        if isinstance(chunk, dict) and 'text' in chunk:
                            st.markdown(f"### Source {i}: {chunk['title']}")
                            st.markdown(f"*From: {chunk['filename']}*")
                            st.markdown(chunk['text'][:500] + "...")
                            st.markdown("---")
        
        st.markdown("---")
        
        # Rebuild KB Index section
        with st.expander("🔧 Rebuild Knowledge Base Index", expanded=False):
            st.markdown("""
            Rebuild the retrieval index after:
            - Adding new KB files
            - Editing existing KB content
            - Installing sentence-transformers
            
            This will regenerate both TF-IDF and embedding indices.
            """)
            
            col_confirm, col_rebuild = st.columns([3, 1])
            
            with col_confirm:
                rebuild_confirmed = st.checkbox(
                    "I understand this will take 30-60 seconds",
                    key="rebuild_confirm"
                )
            
            with col_rebuild:
                if st.button("🔨 Rebuild", type="secondary", disabled=not rebuild_confirmed):
                    with st.spinner("Rebuilding indices..."):
                        import subprocess
                        import sys
                        
                        try:
                            # Rebuild TF-IDF index
                            st.info("Step 1/2: Rebuilding TF-IDF index...")
                            result1 = subprocess.run(
                                [sys.executable, "rag/index_kb.py"],
                                capture_output=True,
                                text=True,
                                timeout=60
                            )
                            
                            if result1.returncode == 0:
                                st.success("✓ TF-IDF index rebuilt")
                            else:
                                st.error(f"TF-IDF indexing failed: {result1.stderr}")
                            
                            # Rebuild embedding index
                            st.info("Step 2/2: Rebuilding embedding index...")
                            result2 = subprocess.run(
                                [sys.executable, "rag/embedding_index.py"],
                                capture_output=True,
                                text=True,
                                timeout=60
                            )
                            
                            if result2.returncode == 0:
                                st.success("✓ Embedding index rebuilt")
                            else:
                                st.warning(f"Embedding indexing not available (sentence-transformers may not be installed)")
                            
                            st.success("🎉 Index rebuild complete! Refresh the page to use the new index.")
                            
                            # Clear cache to force reload
                            st.cache_data.clear()
                            
                        except subprocess.TimeoutExpired:
                            st.error("⏱️ Indexing timed out (>60s). Try running manually.")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
        
        st.markdown("---")
        
        # Guidelines
        st.subheader("📋 Guidelines")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **✅ What Coach AI CAN do:**
            - Explain biomechanical metrics
            - Clarify training recommendations
            - Provide tennis technique fundamentals
            - Help interpret your data
            """)
        
        with col2:
            st.markdown("""
            **❌ What Coach AI CANNOT do:**
            - Modify your training plans
            - Override analysis decisions
            - Provide medical/injury advice
            - Make performance predictions
            """)


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main Streamlit application."""
    
    # Page config
    st.set_page_config(
        page_title="Coach AI",
        page_icon="🎾",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
        .stMetric {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
        }
        .stProgress > div > div > div {
            background-color: #4CAF50;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    st.sidebar.title("🎾 Coach AI")
    st.sidebar.markdown("---")
    
    # Page list; upload page is first so it's the landing page. "navigate_to" lets
    # the upload page jump to the dashboard after an analysis completes.
    PAGES = [
        "🎥 New Analysis", "🏠 Dashboard", "📈 Progress & Trends", "🏆 Achievements",
        "🎯 Reference Comparison", "💪 Training & Drills", "📊 Ball & Rally", "🤖 Ask Coach",
    ]
    default_page = st.session_state.pop("navigate_to", "🎥 New Analysis")

    page = st.sidebar.radio(
        "Navigation",
        PAGES,
        index=PAGES.index(default_page) if default_page in PAGES else 0,
    )

    st.sidebar.markdown("---")

    # The New Analysis page must work even with zero existing sessions,
    # so handle it before the "load a session" guard below.
    if page == "🎥 New Analysis":
        if UPLOAD_AVAILABLE:
            render_upload_page()
        else:
            st.error(
                "Upload page could not be loaded. Ensure upload_page.py is in the "
                "project root and dependencies are installed."
            )
        return

    # Load data
    latest_session = get_latest_session()

    if not latest_session:
        st.warning("⚠️ No session data found. Go to **🎥 New Analysis** in the sidebar to upload your first video.")
        st.sidebar.warning("No data available")
        return
    
    # Session selector
    recent_sessions = get_recent_sessions(n=10)
    
    if recent_sessions:
        # Create display names for sessions
        def format_session_name(session_id):
            # Parse date from session ID (e.g., "2025-12-25_13-12-31")
            try:
                parts = session_id.split('_')
                date_str = parts[0]  # "2025-12-25"
                time_str = parts[1][:5] if len(parts) > 1 else ""  # "13-12" -> "13:12"
                time_str = time_str.replace('-', ':')
                
                # Load session data to get score
                session_info = load_report_data(session_id)
                if session_info and 'technique_score' in session_info:
                    score = session_info['technique_score']
                    return f"{date_str} {time_str} - Score: {score:.1f}/100"
                else:
                    return f"{date_str} {time_str}"
            except:
                return session_id
        
        selected_session = st.sidebar.selectbox(
            "Select Session",
            options=recent_sessions,
            index=0,
            format_func=format_session_name
        )
    else:
        selected_session = latest_session
    
    st.sidebar.success(f"✅ Loaded: {selected_session.split('_')[0]}")
    
    # Load session data
    session_data = load_report_data(selected_session)
    
    if not session_data:
        st.error(f"❌ Could not load data for session: {selected_session}")
        return
    
    # Calculate streak and achievements
    streak = calculate_streak()
    achievements = calculate_achievements()
    
    # Display info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.metric("Training Streak", f"{streak} days")
    
    unlocked = sum(
        sum(1 for badge in category if badge['unlocked'])
        for category in achievements.values()
    )
    total = sum(len(category) for category in achievements.values())
    st.sidebar.metric("Badges Unlocked", f"{unlocked}/{total}")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("*Product-Grade UI*")
    st.sidebar.markdown("*Version 2.0*")
    
    # Render selected page
    if page == "🏠 Dashboard":
        render_dashboard(session_data, streak)
    elif page == "📈 Progress & Trends":
        render_progress_trends()
    elif page == "🏆 Achievements":
        render_achievements(achievements)
    elif page == "🎯 Reference Comparison":
        render_reference_comparison(session_data)
    elif page == "💪 Training & Drills":
        render_training_drills(session_data)
    elif page == "📊 Ball & Rally":
        render_ball_rally_analytics(selected_session)
    elif page == "🤖 Ask Coach":
        render_ask_coach("outputs", selected_session)


if __name__ == "__main__":
    main()
