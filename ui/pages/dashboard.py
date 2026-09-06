"""
Dashboard page: headline metrics, focus areas, streak.
"""
import streamlit as st


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
