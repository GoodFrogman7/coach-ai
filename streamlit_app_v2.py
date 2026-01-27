"""
Coach AI - Improved User-Centric Dashboard
Version 2.0 with User Profiles, Session Naming, and Simplified Navigation
"""

import streamlit as st
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import re
import sys
from collections import defaultdict

# Add vision directory to path
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================================
# USER PROFILE MANAGEMENT
# ============================================================================

def get_users_dir():
    """Get or create users directory."""
    users_dir = Path("users")
    users_dir.mkdir(exist_ok=True)
    return users_dir

def get_user_profile(user_id):
    """Load user profile."""
    profile_path = get_users_dir() / f"{user_id}.json"
    if profile_path.exists():
        with open(profile_path, 'r') as f:
            return json.load(f)
    return {"user_id": user_id, "name": user_id, "sessions": {}}

def save_user_profile(user_id, profile):
    """Save user profile."""
    profile_path = get_users_dir() / f"{user_id}.json"
    with open(profile_path, 'w') as f:
        json.dump(profile, f, indent=2)

def get_all_users():
    """Get list of all users."""
    users_dir = get_users_dir()
    users = [f.stem for f in users_dir.glob("*.json")]
    return users if users else ["default_user"]

def link_session_to_user(user_id, session_id, session_name=None):
    """Link a session to a user profile."""
    profile = get_user_profile(user_id)
    if "sessions" not in profile:
        profile["sessions"] = {}
    
    profile["sessions"][session_id] = {
        "name": session_name or f"Session {len(profile['sessions']) + 1}",
        "date": session_id,
        "timestamp": datetime.now().isoformat()
    }
    save_user_profile(user_id, profile)

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def get_user_sessions(user_id):
    """Get all sessions for a user."""
    profile = get_user_profile(user_id)
    sessions = profile.get("sessions", {})
    
    # Also check outputs folder for any unlinked sessions
    outputs_path = Path("outputs")
    if outputs_path.exists():
        for session_dir in outputs_path.iterdir():
            if session_dir.is_dir() and len(session_dir.name) == 19:
                if session_dir.name not in sessions:
                    # Auto-link unlinked sessions
                    link_session_to_user(user_id, session_dir.name)
                    sessions = get_user_profile(user_id).get("sessions", {})
    
    return sessions

def group_sessions_by_month(sessions):
    """Group sessions by month."""
    grouped = defaultdict(list)
    
    for session_id, session_info in sessions.items():
        try:
            # Parse date from session ID (YYYY-MM-DD_HH-MM-SS)
            date_str = session_id.split('_')[0]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            month_key = date_obj.strftime("%B %Y")
            grouped[month_key].append((session_id, session_info))
        except:
            grouped["Unknown"].append((session_id, session_info))
    
    # Sort months (newest first)
    sorted_months = sorted(grouped.keys(), 
                          key=lambda x: datetime.strptime(x, "%B %Y") if x != "Unknown" else datetime.min,
                          reverse=True)
    
    return {month: sorted(sessions, key=lambda x: x[0], reverse=True) 
            for month in sorted_months 
            for sessions in [grouped[month]]}

def rename_session(user_id, session_id, new_name):
    """Rename a session."""
    profile = get_user_profile(user_id)
    if session_id in profile.get("sessions", {}):
        profile["sessions"][session_id]["name"] = new_name
        save_user_profile(user_id, profile)
        return True
    return False

# ============================================================================
# DATA LOADING
# ============================================================================

def load_session_data(session_id):
    """Load session data from outputs folder."""
    session_path = Path("outputs") / session_id
    if not session_path.exists():
        return None
    
    data = {"session_id": session_id, "path": session_path}
    
    # Load report
    report_path = session_path / "report.md"
    if report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            data['report'] = f.read()
        
        # Extract technique score
        match = re.search(r'Overall Technique Score:\s*(\d+\.?\d*)/100', data['report'])
        if match:
            data['technique_score'] = float(match.group(1))
    
    # Check for ball tracking data
    data['has_ball_tracking'] = (session_path / "heatmaps").exists()
    
    # List available videos
    data['videos'] = {
        'user': session_path / "overlay_user.mp4" if (session_path / "overlay_user.mp4").exists() else None,
        'ref': session_path / "overlay_ref.mp4" if (session_path / "overlay_ref.mp4").exists() else None,
        'broadcast': session_path / "overlay_broadcast.mp4" if (session_path / "overlay_broadcast.mp4").exists() else None,
    }
    
    # List heatmaps
    heatmap_dir = session_path / "heatmaps"
    if heatmap_dir.exists():
        data['heatmaps'] = {
            'court_zones': heatmap_dir / "court_zones.png" if (heatmap_dir / "court_zones.png").exists() else None,
            'speed_dist': heatmap_dir / "speed_distribution.png" if (heatmap_dir / "speed_distribution.png").exists() else None,
        }
    
    return data

# ============================================================================
# UI PAGES
# ============================================================================

def render_dashboard(user_id, session_data):
    """Main dashboard with key metrics."""
    st.title("🏠 Dashboard")
    
    if not session_data or 'report' not in session_data:
        st.warning("⚠️ No complete session data available")
        return
    
    # Key metrics at top
    col1, col2, col3 = st.columns(3)
    
    with col1:
        score = session_data.get('technique_score', 0)
        st.metric("Technique Score", f"{score:.1f}/100", 
                 delta="+5.2" if score > 70 else "-2.1")
    
    with col2:
        if session_data.get('has_ball_tracking'):
            st.metric("Ball Tracking", "✅ Enabled", delta="Active")
        else:
            st.metric("Ball Tracking", "❌ Disabled", delta="Inactive")
    
    with col3:
        profile = get_user_profile(user_id)
        total_sessions = len(profile.get("sessions", {}))
        st.metric("Total Sessions", total_sessions)
    
    st.markdown("---")
    
    # Quick insights
    st.subheader("📊 Session Summary")
    
    report = session_data.get('report', '')
    
    # Extract key points from report
    if "Today's Focus" in report:
        focus_match = re.search(r"Today's Focus.*?:\s*\n(.*?)\n##", report, re.DOTALL)
        if focus_match:
            st.markdown("**Focus Areas:**")
            st.info(focus_match.group(1).strip())
    
    # Show ball tracking summary if available
    if session_data.get('has_ball_tracking'):
        st.markdown("**🎾 Ball Tracking Active:**")
        detections = re.search(r'\*\*Total Ball Detections\*\*:\s*(\d+)', report)
        avg_speed = re.search(r'\*\*Average Ball Speed\*\*:\s*([\d.]+)', report)
        
        if detections and avg_speed:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Ball Detections", detections.group(1))
            with col2:
                st.metric("Avg Speed", f"{float(avg_speed.group(1)):.1f} px/f")


def render_session_history(user_id):
    """Session history grouped by month with rename capability."""
    st.title("📅 Session History")
    
    sessions = get_user_sessions(user_id)
    
    if not sessions:
        st.info("No sessions found. Run an analysis to create your first session!")
        return
    
    grouped = group_sessions_by_month(sessions)
    
    for month, month_sessions in grouped.items():
        with st.expander(f"📆 {month} ({len(month_sessions)} sessions)", expanded=(month == list(grouped.keys())[0])):
            for session_id, session_info in month_sessions:
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    session_name = session_info.get('name', session_id)
                    if st.button(f"📊 {session_name}", key=f"view_{session_id}"):
                        st.session_state.selected_session = session_id
                        st.rerun()
                
                with col2:
                    date_str = session_id.split('_')[0]
                    st.caption(date_str)
                
                with col3:
                    if st.button("✏️", key=f"rename_{session_id}"):
                        st.session_state.renaming_session = session_id


def render_analysis_viewer(user_id, session_data):
    """Side-by-side analysis viewer with video and heatmaps."""
    st.title("🎬 Analysis Viewer")
    
    if not session_data:
        st.warning("No session selected")
        return
    
    st.subheader(f"Session: {session_data['session_id']}")
    
    # Tabs for different views
    tabs = st.tabs(["📹 Video Analysis", "📊 Ball Tracking", "📄 Full Report"])
    
    with tabs[0]:
        st.markdown("### Video Comparison")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Your Performance**")
            if session_data['videos']['user'] and session_data['videos']['user'].exists():
                with open(session_data['videos']['user'], 'rb') as video_file:
                    video_bytes = video_file.read()
                
                vcol1, vcol2 = st.columns([5, 1])
                with vcol1:
                    st.video(video_bytes)
                with vcol2:
                    st.download_button(
                        label="⬇️ Download",
                        data=video_bytes,
                        file_name="your_performance.mp4",
                        mime="video/mp4"
                    )
            else:
                st.info("User video not available")
        
        with col2:
            st.markdown("**Reference (Pro)**")
            if session_data['videos']['ref'] and session_data['videos']['ref'].exists():
                with open(session_data['videos']['ref'], 'rb') as video_file:
                    video_bytes = video_file.read()
                
                vcol1, vcol2 = st.columns([5, 1])
                with vcol1:
                    st.video(video_bytes)
                with vcol2:
                    st.download_button(
                        label="⬇️ Download",
                        data=video_bytes,
                        file_name="reference_pro.mp4",
                        mime="video/mp4"
                    )
            else:
                st.info("Reference video not available")
    
    with tabs[1]:
        if session_data.get('has_ball_tracking'):
            st.markdown("### Ball Tracking Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📹 Broadcast Overlay**")
                if session_data['videos']['broadcast'] and session_data['videos']['broadcast'].exists():
                    with open(session_data['videos']['broadcast'], 'rb') as video_file:
                        video_bytes = video_file.read()
                    
                    vcol1, vcol2 = st.columns([5, 1])
                    with vcol1:
                        st.video(video_bytes)
                    with vcol2:
                        st.download_button(
                            label="⬇️ Download",
                            data=video_bytes,
                            file_name="ball_tracking.mp4",
                            mime="video/mp4"
                        )
                else:
                    st.info("Broadcast video not available")
            
            with col2:
                st.markdown("**📊 Heatmaps**")
                
                if 'heatmaps' in session_data:
                    if session_data['heatmaps']['court_zones']:
                        st.image(str(session_data['heatmaps']['court_zones']), 
                                caption="Shot Placement", use_column_width=True)
                    
                    if session_data['heatmaps']['speed_dist']:
                        st.image(str(session_data['heatmaps']['speed_dist']), 
                                caption="Speed Distribution", use_column_width=True)
        else:
            st.info("📊 Ball tracking not available for this session. Enable YOLO model and re-run analysis.")
    
    with tabs[2]:
        st.markdown("### Complete Report")
        if 'report' in session_data:
            st.markdown(session_data['report'])
        else:
            st.warning("Report not found")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(
        page_title="Coach AI",
        page_icon="🎾",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .big-font {
            font-size:20px !important;
            font-weight: bold;
        }
        .metric-card {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #4CAF50;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar: User selection and navigation
    st.sidebar.title("🎾 Coach AI")
    st.sidebar.markdown("---")
    
    # User selection
    users = get_all_users()
    
    if 'current_user' not in st.session_state:
        st.session_state.current_user = users[0]
    
    selected_user = st.sidebar.selectbox(
        "👤 User Profile",
        users,
        index=users.index(st.session_state.current_user) if st.session_state.current_user in users else 0
    )
    
    if selected_user != st.session_state.current_user:
        st.session_state.current_user = selected_user
        st.rerun()
    
    # Add new user button
    if st.sidebar.button("➕ Add New User"):
        st.session_state.show_add_user = True
    
    if st.session_state.get('show_add_user'):
        new_user_id = st.sidebar.text_input("New User ID:")
        if st.sidebar.button("Create") and new_user_id:
            profile = {"user_id": new_user_id, "name": new_user_id, "sessions": {}}
            save_user_profile(new_user_id, profile)
            st.session_state.current_user = new_user_id
            st.session_state.show_add_user = False
            st.rerun()
    
    st.sidebar.markdown("---")
    
    # Simplified Navigation (3 main pages instead of 7)
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Dashboard", "📅 Session History", "🎬 Analysis Viewer"]
    )
    
    st.sidebar.markdown("---")
    
    # Session selector
    user_sessions = get_user_sessions(selected_user)
    
    if user_sessions:
        if 'selected_session' not in st.session_state:
            st.session_state.selected_session = sorted(user_sessions.keys(), reverse=True)[0]
        
        session_options = {sid: sinfo.get('name', sid) for sid, sinfo in user_sessions.items()}
        selected_session_id = st.sidebar.selectbox(
            "Select Session",
            options=list(session_options.keys()),
            format_func=lambda x: session_options[x],
            index=list(session_options.keys()).index(st.session_state.selected_session) 
                  if st.session_state.selected_session in session_options else 0
        )
        
        st.session_state.selected_session = selected_session_id
        
        # Rename session feature
        if st.session_state.get('renaming_session'):
            new_name = st.sidebar.text_input("New session name:", 
                                            value=session_options[st.session_state.renaming_session])
            if st.sidebar.button("💾 Save Name"):
                rename_session(selected_user, st.session_state.renaming_session, new_name)
                del st.session_state.renaming_session
                st.rerun()
            if st.sidebar.button("❌ Cancel"):
                del st.session_state.renaming_session
                st.rerun()
    else:
        st.sidebar.info("No sessions yet")
        selected_session_id = None
    
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Coach AI v2.0 | User: {selected_user}")
    
    # Load session data
    session_data = load_session_data(selected_session_id) if selected_session_id else None
    
    # Render selected page
    if page == "🏠 Dashboard":
        render_dashboard(selected_user, session_data)
    elif page == "📅 Session History":
        render_session_history(selected_user)
    elif page == "🎬 Analysis Viewer":
        render_analysis_viewer(selected_user, session_data)


if __name__ == "__main__":
    main()
