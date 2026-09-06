"""
Training & Drills page: recommended drills with confidence.
"""
import streamlit as st

from ui.data import compute_drill_confidence_scores


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
