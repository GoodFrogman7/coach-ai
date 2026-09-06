"""
Sessions page: history grouped by month, rename, and a per-session viewer with
the overlay videos and the full markdown report.
"""
import streamlit as st
from pathlib import Path

from ui.data import load_report_data
from ui.users import get_user_sessions, group_sessions_by_month, rename_session, session_label


def _video_with_download(path: Path, label: str, file_name: str):
    if not path or not path.exists():
        st.info(f"{label} not available")
        return
    video_bytes = path.read_bytes()
    st.video(video_bytes)
    st.download_button(
        f"⬇️ Download {label.lower()}",
        data=video_bytes,
        file_name=file_name,
        mime="video/mp4",
        key=f"dl_{file_name}_{path.parent.name}",
    )


def render_session_viewer(session_id: str, base_dir: str = "outputs"):
    session_dir = Path(base_dir) / session_id
    st.subheader(f"Session {session_id}")

    tabs = st.tabs(["📹 Videos", "📄 Full Report"])

    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Your stroke**")
            _video_with_download(session_dir / "overlay_user.mp4", "Your video", "your_stroke.mp4")
        with col2:
            st.markdown("**Reference (pro)**")
            _video_with_download(session_dir / "overlay_ref.mp4", "Reference video", "reference_pro.mp4")
        broadcast = session_dir / "overlay_broadcast.mp4"
        if broadcast.exists():
            st.markdown("**Ball tracking overlay**")
            _video_with_download(broadcast, "Broadcast overlay", "ball_tracking.mp4")

    with tabs[1]:
        data = load_report_data(session_id, base_dir)
        if data and data.get("raw_content"):
            st.download_button(
                "⬇️ Download report (.md)",
                data=data["raw_content"],
                file_name=f"coach_ai_report_{session_id}.md",
                mime="text/markdown",
                key=f"dl_report_{session_id}",
            )
            st.markdown(data["raw_content"])
        else:
            st.warning("Report not found for this session.")


def render_sessions(user_id: str, selected_session: str = None):
    st.title("📅 Sessions")

    sessions = get_user_sessions(user_id)
    if not sessions:
        st.info("No sessions yet. Go to **🎥 New Analysis** to upload your first video.")
        return

    grouped = group_sessions_by_month(sessions)
    first_month = next(iter(grouped))

    for month, month_sessions in grouped.items():
        with st.expander(f"📆 {month} ({len(month_sessions)} sessions)", expanded=(month == first_month)):
            for session_id, info in month_sessions:
                data = load_report_data(session_id)
                score = data.get("technique_score") if data else None
                col1, col2, col3 = st.columns([5, 2, 1])
                with col1:
                    if st.button(session_label(session_id, info, score), key=f"view_{session_id}",
                                 use_container_width=True):
                        st.session_state.selected_session = session_id
                        st.session_state.pop("renaming_session", None)
                        st.rerun()
                with col2:
                    st.caption(info.get("date", session_id).split("_")[0])
                with col3:
                    if st.button("✏️", key=f"rename_{session_id}", help="Rename session"):
                        st.session_state.renaming_session = session_id
                        st.rerun()

    renaming = st.session_state.get("renaming_session")
    if renaming and renaming in sessions:
        st.markdown("---")
        new_name = st.text_input("New session name", value=sessions[renaming].get("name", renaming),
                                 key="rename_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save name", use_container_width=True):
                rename_session(user_id, renaming, new_name.strip() or renaming)
                st.session_state.pop("renaming_session", None)
                st.rerun()
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pop("renaming_session", None)
                st.rerun()

    if selected_session and selected_session in sessions:
        st.markdown("---")
        render_session_viewer(selected_session)
