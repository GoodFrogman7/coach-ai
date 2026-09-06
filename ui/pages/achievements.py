"""
Achievements page: badge grid.
"""
import streamlit as st


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
