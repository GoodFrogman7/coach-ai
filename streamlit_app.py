"""
Coach AI dashboard entry point.

This file is the router only: sidebar (user, navigation, session picker) and
dispatch to one page module per screen under ui/pages/. Data helpers live in
ui/data.py, user profiles in ui/users.py. Run with:

    streamlit run streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.data import calculate_achievements, calculate_streak, load_report_data  # noqa: E402
from ui.users import (  # noqa: E402
    DEFAULT_USER,
    create_user,
    get_all_users,
    get_user_sessions,
    session_label,
)
from ui.pages.achievements import render_achievements  # noqa: E402
from ui.pages.ask_coach import render_ask_coach  # noqa: E402
from ui.pages.ball_rally import render_ball_rally_analytics  # noqa: E402
from ui.pages.dashboard import render_dashboard  # noqa: E402
from ui.pages.drills import render_training_drills  # noqa: E402
from ui.pages.progress import render_progress_trends  # noqa: E402
from ui.pages.reference import render_reference_comparison  # noqa: E402
from ui.pages.sessions import render_sessions  # noqa: E402
from ui.pages.upload import render_upload_page  # noqa: E402

PAGE_NEW = "🎥 New Analysis"
PAGE_DASHBOARD = "🏠 Dashboard"
PAGE_SESSIONS = "📅 Sessions"
PAGE_PROGRESS = "📈 Progress & Trends"
PAGE_ACHIEVEMENTS = "🏆 Achievements"
PAGE_REFERENCE = "🎯 Reference Comparison"
PAGE_DRILLS = "💪 Training & Drills"
PAGE_BALL = "📊 Ball & Rally"
PAGE_ASK = "🤖 Ask Coach"

# Upload page is first so it is the landing page. "navigate_to" lets the upload
# page jump to the dashboard after an analysis completes.
PAGES = [
    PAGE_NEW, PAGE_DASHBOARD, PAGE_SESSIONS, PAGE_PROGRESS, PAGE_ACHIEVEMENTS,
    PAGE_REFERENCE, PAGE_DRILLS, PAGE_BALL, PAGE_ASK,
]

CSS = """
<style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; }
    .stProgress > div > div > div { background-color: #4CAF50; }
</style>
"""


def _sidebar_user() -> str:
    """User selector plus an inline 'add user' form. Returns the active user id."""
    users = get_all_users()
    current = st.session_state.get("current_user", DEFAULT_USER)
    if current not in users:
        current = users[0]

    selected = st.sidebar.selectbox("👤 Player", users, index=users.index(current))
    if selected != st.session_state.get("current_user"):
        st.session_state.current_user = selected
        st.session_state.pop("selected_session", None)

    with st.sidebar.expander("➕ Add player", expanded=False):
        new_id = st.text_input("Player id (letters, digits, _ or -)", key="new_user_id").strip()
        if st.button("Create", key="create_user_btn") and new_id:
            safe = "".join(ch for ch in new_id if ch.isalnum() or ch in "_-")
            if safe and safe not in users:
                create_user(safe)
                st.session_state.current_user = safe
                st.session_state.pop("selected_session", None)
                st.rerun()
            else:
                st.warning("Pick a different id.")
    return selected


def _sidebar_session(user_id: str):
    """Session picker with names and scores. Returns (session_id, sessions)."""
    sessions = get_user_sessions(user_id)
    if not sessions:
        return None, sessions

    ids = list(sessions.keys())
    wanted = st.session_state.get("selected_session")
    index = ids.index(wanted) if wanted in ids else 0

    def fmt(session_id):
        data = load_report_data(session_id)
        score = data.get("technique_score") if data else None
        return session_label(session_id, sessions[session_id], score)

    chosen = st.sidebar.selectbox("Session", ids, index=index, format_func=fmt)
    st.session_state.selected_session = chosen
    return chosen, sessions


def main():
    st.set_page_config(page_title="Coach AI", page_icon="🎾", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)

    st.sidebar.title("🎾 Coach AI")
    user_id = _sidebar_user()
    st.sidebar.markdown("---")

    default_page = st.session_state.pop("navigate_to", PAGE_NEW)
    page = st.sidebar.radio("Navigation", PAGES,
                            index=PAGES.index(default_page) if default_page in PAGES else 0)
    st.sidebar.markdown("---")

    # The upload page must work with zero existing sessions.
    if page == PAGE_NEW:
        render_upload_page()
        return

    selected_session, sessions = _sidebar_session(user_id)
    if not selected_session:
        st.warning("⚠️ No sessions yet for this player. Go to **🎥 New Analysis** to upload a video.")
        return

    if page == PAGE_SESSIONS:
        render_sessions(user_id, selected_session)
        return

    session_data = load_report_data(selected_session)
    if not session_data:
        st.error(f"❌ Could not load data for session: {selected_session}")
        return

    streak = calculate_streak()
    achievements = calculate_achievements()
    unlocked = sum(sum(1 for b in cat if b["unlocked"]) for cat in achievements.values())
    total = sum(len(cat) for cat in achievements.values())
    st.sidebar.metric("Training streak", f"{streak} days")
    st.sidebar.metric("Badges unlocked", f"{unlocked}/{total}")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Player: {user_id} · {len(sessions)} sessions")

    if page == PAGE_DASHBOARD:
        render_dashboard(session_data, streak)
    elif page == PAGE_PROGRESS:
        render_progress_trends()
    elif page == PAGE_ACHIEVEMENTS:
        render_achievements(achievements)
    elif page == PAGE_REFERENCE:
        render_reference_comparison(session_data)
    elif page == PAGE_DRILLS:
        render_training_drills(session_data)
    elif page == PAGE_BALL:
        render_ball_rally_analytics(selected_session)
    elif page == PAGE_ASK:
        render_ask_coach("outputs", selected_session)


if __name__ == "__main__":
    main()
