"""
Ball & Rally Analytics page: YOLO ball tracking outputs.
"""
import streamlit as st
import re
from pathlib import Path


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
