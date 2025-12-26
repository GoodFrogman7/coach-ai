"""
Coach AI - Adaptive Coaching Dashboard (Streamlit Phase 1)

READ-ONLY visualization app for Coach AI outputs.
No modifications to backend logic, analysis, or drill recommendations.
"""

import streamlit as st
import json
import pandas as pd
from pathlib import Path
import sys

# Add vision directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import read-only helper functions
try:
    from vision.compare import compute_drill_confidence_scores, get_top_effective_drills
except ImportError:
    compute_drill_confidence_scores = None
    get_top_effective_drills = None


# ============================================================================
# Data Loading Helpers (Read-Only)
# ============================================================================

def get_latest_session(base_dir: str = "outputs") -> str:
    """Get the most recent session directory."""
    try:
        outputs_path = Path(base_dir)
        if not outputs_path.exists():
            return None
        
        # Get all session directories (format: YYYY-MM-DD_HH-MM-SS)
        sessions = [d for d in outputs_path.iterdir() if d.is_dir() and len(d.name) == 19]
        
        if not sessions:
            return None
        
        # Sort by name (timestamp format sorts chronologically)
        latest = sorted(sessions, reverse=True)[0]
        return latest.name
    
    except Exception:
        return None


def load_session_report(session_id: str, base_dir: str = "outputs") -> dict:
    """Load key data from session report markdown (read-only)."""
    try:
        report_path = Path(base_dir) / session_id / "report.md"
        
        if not report_path.exists():
            return None
        
        # Read report file
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract key information (simple parsing)
        data = {
            'session_id': session_id,
            'has_content': True
        }
        
        # Extract overall score if present
        if "Overall Technique Score:" in content:
            lines = content.split('\n')
            for line in lines:
                if "Overall Technique Score:" in line:
                    # Extract score (format: **Overall Technique Score: 62.4/100**)
                    if '/100' in line:
                        score_part = line.split('/100')[0]
                        score = score_part.split(':')[-1].strip().replace('*', '')
                        try:
                            data['overall_score'] = float(score)
                        except:
                            pass
        
        return data
    
    except Exception:
        return None


def load_drill_outcomes(base_dir: str = "outputs") -> list:
    """Load drill outcomes from JSON (read-only)."""
    try:
        outcomes_path = Path(base_dir) / "drill_outcomes.json"
        
        if not outcomes_path.exists():
            return []
        
        with open(outcomes_path, 'r') as f:
            outcomes = json.load(f)
        
        return outcomes if outcomes else []
    
    except Exception:
        return []


def get_recent_sessions(base_dir: str = "outputs", n: int = 10) -> list:
    """Get N most recent session IDs."""
    try:
        outputs_path = Path(base_dir)
        if not outputs_path.exists():
            return []
        
        # Get all session directories
        sessions = [d.name for d in outputs_path.iterdir() if d.is_dir() and len(d.name) == 19]
        
        # Sort by name (timestamp) and return most recent N
        return sorted(sessions, reverse=True)[:n]
    
    except Exception:
        return []


# ============================================================================
# Streamlit UI
# ============================================================================

def main():
    """Main Streamlit application."""
    
    # Page config
    st.set_page_config(
        page_title="Coach AI Dashboard",
        page_icon="🎾",
        layout="wide"
    )
    
    # Title
    st.title("🎾 Coach AI — Adaptive Coaching Dashboard")
    st.markdown("*Read-only visualization of Coach AI analysis outputs*")
    st.markdown("---")
    
    # Load latest session
    latest_session = get_latest_session()
    
    if not latest_session:
        st.warning("⚠️ No session data found. Run the analysis first: `python vision/compare.py`")
        return
    
    # Session selector in sidebar
    st.sidebar.header("📊 Session Selection")
    recent_sessions = get_recent_sessions(n=10)
    
    if recent_sessions:
        selected_session = st.sidebar.selectbox(
            "Select Session",
            options=recent_sessions,
            index=0
        )
    else:
        selected_session = latest_session
    
    st.sidebar.markdown(f"**Current:** `{selected_session}`")
    st.sidebar.markdown("---")
    
    # Load session data
    session_data = load_session_report(selected_session)
    
    if not session_data:
        st.error(f"❌ Could not load data for session: {selected_session}")
        return
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Performance Overview",
        "🎯 Coaching Priorities",
        "💪 Drill Recommendations",
        "📊 Drill Effectiveness",
        "📉 Progress Tracking"
    ])
    
    # ========================================================================
    # Tab 1: Performance Overview
    # ========================================================================
    with tab1:
        st.header("Performance Overview")
        
        if 'overall_score' in session_data:
            # Display overall score
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label="Overall Technique Score",
                    value=f"{session_data['overall_score']:.1f}/100"
                )
            
            with col2:
                # Performance level
                score = session_data['overall_score']
                if score >= 80:
                    level = "🟢 Excellent"
                elif score >= 70:
                    level = "🟡 Good"
                elif score >= 60:
                    level = "🟡 Solid"
                else:
                    level = "🟠 Developing"
                
                st.metric(
                    label="Performance Level",
                    value=level
                )
            
            with col3:
                st.metric(
                    label="Session ID",
                    value=selected_session.split('_')[0]  # Date only
                )
        else:
            st.info("📊 Overall score not available in report")
        
        st.markdown("---")
        
        # Session info
        st.subheader("Session Information")
        st.markdown(f"**Session ID:** `{selected_session}`")
        st.markdown(f"**Report Location:** `outputs/{selected_session}/report.md`")
        
        st.info("💡 **Tip:** Open the full report for detailed analysis, coaching cues, and drill prescriptions.")
    
    # ========================================================================
    # Tab 2: Coaching Priorities
    # ========================================================================
    with tab2:
        st.header("Coaching Priorities")
        
        st.markdown("""
        The adaptive coaching engine prioritizes issues based on:
        - **Severity**: Deviation magnitude
        - **Reliability**: Measurement confidence
        - **Phase Importance**: Critical phases weighted higher
        - **Consistency**: Stable patterns vs. random noise
        - **Progress**: Worsening issues escalated, improving issues deprioritized
        """)
        
        st.markdown("---")
        
        # Placeholder for priority visualization
        st.info("📋 **Priority classifications are available in the full report.**")
        
        st.markdown("""
        **Classification Levels:**
        - 🚨 **CRITICAL**: Severe + reliable + persistent → Address immediately
        - ⭐ **PRIORITY**: Significant + reliable → Focus on these
        - 📊 **MONITOR**: Improving or needs verification → Track progress
        - 🔇 **SUPPRESS**: Low reliability or minor → Deprioritized
        """)
        
        st.markdown("---")
        st.markdown("*Full priority details available in: `outputs/{}/report.md`*".format(selected_session))
    
    # ========================================================================
    # Tab 3: Drill Recommendations
    # ========================================================================
    with tab3:
        st.header("Drill Recommendations")
        
        st.markdown("""
        Drills are prescribed based on adaptive coaching priorities with intensity
        adjusted according to issue classification and progress tracking.
        """)
        
        st.markdown("---")
        
        # Intensity levels
        st.subheader("Intensity Levels")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🚨 Intensive**")
            st.markdown("- Daily practice")
            st.markdown("- High volume")
            st.markdown("- Resistance training")
            st.markdown("- For CRITICAL issues")
        
        with col2:
            st.markdown("**⭐ Moderate**")
            st.markdown("- 3-5x per week")
            st.markdown("- Standard volume")
            st.markdown("- Focused repetition")
            st.markdown("- For PRIORITY issues")
        
        with col3:
            st.markdown("**📊 Light**")
            st.markdown("- 2-3x per week")
            st.markdown("- Lower volume")
            st.markdown("- Maintain progress")
            st.markdown("- For improving areas")
        
        st.markdown("---")
        st.info("💪 **Full drill prescriptions with specific sets/reps are in the report.**")
        st.markdown("*See: `outputs/{}/report.md` → Recommended Training Interventions*".format(selected_session))
    
    # ========================================================================
    # Tab 4: Drill Effectiveness
    # ========================================================================
    with tab4:
        st.header("Drill Effectiveness Analysis")
        
        st.markdown("""
        Historical analysis of drill outcomes based on measurement data.
        Confidence scores indicate which drills have proven most effective.
        """)
        
        st.markdown("---")
        
        # Load drill outcomes
        outcomes = load_drill_outcomes()
        
        if not outcomes:
            st.warning("⚠️ No drill outcome data available yet. Data accumulates across multiple sessions.")
            st.info("💡 Drill outcomes are tracked automatically when you run subsequent analysis sessions.")
        else:
            st.success(f"✅ Found {len(outcomes)} historical drill outcome(s)")
            
            # Compute confidence scores (read-only)
            if compute_drill_confidence_scores:
                confidence_scores = compute_drill_confidence_scores()
                
                if confidence_scores:
                    st.subheader("Drill Confidence Scores")
                    
                    # Convert to DataFrame for display
                    df_data = []
                    for drill_name, data in confidence_scores.items():
                        df_data.append({
                            'Drill Name': drill_name,
                            'Confidence': f"{data['confidence_score']:.2f}",
                            'Level': data['confidence_level'],
                            'Usage Count': data['usage_count'],
                            'Avg Improvement': f"{data['avg_delta']:.1f}°",
                            'Reliability': f"{data['high_reliability_ratio']:.0%}",
                            'Consistency': f"{data['consistency']:.2f}"
                        })
                    
                    df = pd.DataFrame(df_data)
                    
                    # Display table
                    st.dataframe(df, use_container_width=True)
                    
                    st.markdown("---")
                    
                    # Top drills
                    if get_top_effective_drills:
                        st.subheader("Top Effective Drills")
                        top_drills = get_top_effective_drills(n=5)
                        
                        if top_drills:
                            for rank, (drill_name, data) in enumerate(top_drills, 1):
                                with st.expander(f"#{rank}: {drill_name} (Score: {data['confidence_score']:.2f})"):
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        st.metric("Confidence Level", data['confidence_level'])
                                        st.metric("Usage Count", data['usage_count'])
                                    
                                    with col2:
                                        st.metric("Avg Improvement", f"{data['avg_delta']:.1f}°")
                                        st.metric("Consistency", f"{data['consistency']:.2f}")
                else:
                    st.info("📊 Not enough data yet to compute confidence scores.")
            else:
                st.warning("⚠️ Confidence scoring functions not available.")
        
        st.markdown("---")
        
        # Explanation
        st.subheader("How Confidence Scores Work")
        st.markdown("""
        Confidence scores (0-1) integrate multiple factors:
        - **Improvement (40%)**: How much the drill improves metrics
        - **Reliability (25%)**: Fraction with high-confidence measurements
        - **Consistency (25%)**: Low variance = predictable results
        - **Sample Size (10%)**: More data = higher confidence
        
        **Confidence Levels:**
        - **High (≥0.75)**: Proven effective, reliable, consistent
        - **Medium (0.50-0.74)**: Moderately effective, needs more data
        - **Low (<0.50)**: Insufficient evidence or inconsistent
        """)
    
    # ========================================================================
    # Tab 5: Progress Tracking
    # ========================================================================
    with tab5:
        st.header("Progress Tracking")
        
        st.markdown("Visualization of metric changes across sessions.")
        
        st.markdown("---")
        
        # Load outcomes for progress visualization
        outcomes = load_drill_outcomes()
        
        if not outcomes:
            st.warning("⚠️ No historical data available yet. Progress tracking requires multiple sessions.")
        else:
            st.success(f"✅ Found {len(outcomes)} outcome record(s) across sessions")
            
            # Convert to DataFrame
            df = pd.DataFrame(outcomes)
            
            if not df.empty:
                # Show summary statistics
                st.subheader("Session Summary")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    unique_sessions = df['current_session_id'].nunique()
                    st.metric("Unique Sessions", unique_sessions)
                
                with col2:
                    unique_drills = df['drill_name'].nunique()
                    st.metric("Unique Drills", unique_drills)
                
                with col3:
                    avg_delta = df['delta'].mean()
                    st.metric("Avg Delta", f"{avg_delta:.1f}°")
                
                st.markdown("---")
                
                # Drill outcomes table
                st.subheader("Recent Drill Outcomes")
                
                # Select columns to display
                display_df = df[[
                    'current_session_id',
                    'drill_name',
                    'metric_name',
                    'phase',
                    'intensity',
                    'pre_value',
                    'post_value',
                    'delta',
                    'reliability'
                ]].copy()
                
                # Rename for clarity
                display_df.columns = [
                    'Session',
                    'Drill',
                    'Metric',
                    'Phase',
                    'Intensity',
                    'Pre-Value',
                    'Post-Value',
                    'Delta',
                    'Reliability'
                ]
                
                # Show most recent first
                display_df = display_df.sort_values('Session', ascending=False)
                
                st.dataframe(display_df, use_container_width=True)
                
                st.markdown("---")
                
                # Simple line chart of deltas over time
                st.subheader("Delta Trends")
                
                if 'timestamp' in df.columns and not df.empty:
                    # Group by drill and show trends
                    drill_options = ['All Drills'] + sorted(df['drill_name'].unique().tolist())
                    selected_drill = st.selectbox("Select Drill", drill_options)
                    
                    if selected_drill == 'All Drills':
                        plot_df = df[['timestamp', 'delta']].copy()
                    else:
                        plot_df = df[df['drill_name'] == selected_drill][['timestamp', 'delta']].copy()
                    
                    if not plot_df.empty:
                        # Convert timestamp to datetime for sorting
                        plot_df['timestamp'] = pd.to_datetime(plot_df['timestamp'])
                        plot_df = plot_df.sort_values('timestamp')
                        plot_df = plot_df.set_index('timestamp')
                        
                        st.line_chart(plot_df['delta'])
                        
                        st.caption("💡 Negative delta = improvement for most metrics")
                    else:
                        st.info("No data available for selected drill")
            else:
                st.warning("⚠️ Could not parse outcome data.")
        
        st.markdown("---")
        st.info("📈 **Longitudinal progress tracking** shows how your technique evolves over time.")
    
    # Sidebar info
    st.sidebar.markdown("---")
    st.sidebar.header("📖 About")
    st.sidebar.markdown("""
    **Coach AI Dashboard**
    
    Read-only visualization of:
    - Performance metrics
    - Adaptive coaching priorities
    - Drill recommendations
    - Historical drill effectiveness
    - Progress tracking
    
    **Data Source:**
    `outputs/` directory
    
    **Version:** Phase 1 (Viewer)
    """)


if __name__ == "__main__":
    main()

