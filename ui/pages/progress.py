"""
Progress & Trends page: technique and readiness across sessions.
"""
import streamlit as st
import pandas as pd
import numpy as np

from ui.data import get_recent_sessions, load_report_data


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
