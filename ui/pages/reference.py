"""
Reference Comparison page: user vs professional metrics.
"""
import streamlit as st


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
