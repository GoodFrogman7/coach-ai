"""
upload_page.py
Upload -> Analyze -> Result loop for Coach AI.

Renders the "New Analysis" page: the user uploads a stroke video, picks the
stroke type and a reference, and the full analysis pipeline runs in-app. Kept as
a standalone module so streamlit_app.py stays focused on the read/dashboard side.

Uses the decomposed pipeline API: run_pipeline(user_video, ref_video, stroke).
"""

import re
import tempfile
from datetime import datetime
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# Import defensively so the app still loads (and can show a friendly error) even
# if the heavy pipeline dependencies (mediapipe, opencv, ...) aren't installed.
try:
    from vision.compare import run_pipeline, validate_video
except Exception:
    run_pipeline = None
    validate_video = None

# ── config ────────────────────────────────────────────────────────────────────
STROKE_OPTIONS = ["backhand", "forehand", "serve", "volley", "overhead"]
DEFAULT_REFERENCE = "data/reference/djokovic_backhand.mp4"
UPLOAD_DIR = Path("data/user/uploads")


# ── helpers ───────────────────────────────────────────────────────────────────

def _save_upload(uploaded_file, prefix: str) -> str:
    """Persist a Streamlit upload to a timestamped file under UPLOAD_DIR."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name).suffix or ".mp4"
    dest = UPLOAD_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dest)


def _probe_video(uploaded_file) -> dict:
    """Best-effort metadata probe (width, height, fps, frames) for warnings."""
    try:
        import cv2
        tmp = Path(tempfile.mktemp(suffix=Path(uploaded_file.name).suffix))
        tmp.write_bytes(uploaded_file.getvalue())
        cap = cv2.VideoCapture(str(tmp))
        ok = cap.isOpened()
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        tmp.unlink(missing_ok=True)
        return {"ok": ok, "frames": frames, "fps": fps, "w": w, "h": h}
    except Exception as exc:
        return {"ok": None, "error": str(exc)}


# ── main render function ───────────────────────────────────────────────────────

def render_upload_page():
    st.title("🎥 New Analysis")
    st.markdown(
        "Upload a stroke video and Coach AI analyzes your technique against a "
        "professional reference. Analysis runs locally and takes ~1-3 minutes."
    )

    if run_pipeline is None or validate_video is None:
        st.error(
            "The analysis pipeline could not be imported. Ensure dependencies are "
            "installed (`pip install -r requirements.txt`) and you're running from "
            "the project root."
        )
        return

    # If a run just finished, show its results (and a way back) instead of the form.
    finished = st.session_state.get("upload_last_session")
    if finished:
        _show_results(finished)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Open Full Dashboard", use_container_width=True):
                st.session_state.pop("upload_last_session", None)
                st.session_state.navigate_to = "🏠 Dashboard"
                st.rerun()
        with col2:
            if st.button("🔄 Analyze Another Video", use_container_width=True):
                st.session_state.pop("upload_last_session", None)
                st.rerun()
        return

    # ── filming tips ──────────────────────────────────────────────────────────
    with st.expander("📷 How to film for best results", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Do this:**")
            st.markdown(
                "- Film from the side (perpendicular to baseline)\n"
                "- Full body visible — head to feet\n"
                "- 720p or higher resolution\n"
                "- 30+ fps recommended\n"
                "- Well-lit (no backlit situations)\n"
                "- Capture the full stroke: prep → follow-through"
            )
        with col2:
            st.markdown("**Avoid:**")
            st.markdown(
                "- Filming from behind or in front\n"
                "- Cutting off feet or head\n"
                "- Loose or baggy clothing\n"
                "- Poor or uneven lighting\n"
                "- Videos shorter than 2 seconds"
            )

    st.markdown("---")

    # ── 1. user video ─────────────────────────────────────────────────────────
    st.subheader("1. Your video")
    st.caption("Side-on view (perpendicular to the baseline), full body in frame, 720p+ works best.")
    user_file = st.file_uploader(
        "Upload your stroke video",
        type=["mp4", "mov", "avi", "mkv", "m4v"],
        help="MP4 (H.264) recommended. Max ~500 MB.",
        key="user_video_upload",
    )

    if user_file is not None:
        file_mb = len(user_file.getvalue()) / (1024 * 1024)
        st.success(f"✅ Received: **{user_file.name}** ({file_mb:.1f} MB)")
        meta = _probe_video(user_file)
        if meta.get("ok") is False:
            st.error("❌ Could not read this video. Try re-exporting as MP4 (H.264).")
        elif meta.get("ok"):
            frames, fps, w, h = meta["frames"], meta["fps"], meta["w"], meta["h"]
            if fps > 0 and frames:
                st.caption(f"Video: {w}×{h} @ {fps:.0f} fps — {frames} frames ({frames / fps:.1f}s)")
            if frames and frames < 30:
                st.warning("⚠️ Video is very short (<30 frames / ~1s) — capture the full stroke.")
            if 0 < fps < 24:
                st.warning("⚠️ Frame rate below 24 fps — pose detection may be less accurate.")
            if 0 < w < 640:
                st.warning("⚠️ Resolution below 640px wide — consider a higher-quality recording.")

    # ── 2. stroke type ────────────────────────────────────────────────────────
    st.subheader("2. Stroke type")
    stroke = st.selectbox("Which stroke is this?", STROKE_OPTIONS, index=0)

    # ── 3. reference ──────────────────────────────────────────────────────────
    st.subheader("3. Reference")
    ref_choice = st.radio(
        "Compare against",
        ["Built-in professional reference", "Upload my own reference"],
        index=0,
    )
    ref_file = None
    if ref_choice == "Upload my own reference":
        ref_file = st.file_uploader(
            "Upload a reference video",
            type=["mp4", "mov", "avi", "mkv", "m4v"],
            key="ref_video_upload",
        )
    elif Path(DEFAULT_REFERENCE).exists():
        st.caption(f"Using built-in reference: {Path(DEFAULT_REFERENCE).name}")
    else:
        st.warning(
            f"Built-in reference not found at `{DEFAULT_REFERENCE}`. "
            "Upload your own reference video instead."
        )

    st.markdown("---")

    if user_file is None:
        st.info("Upload a video above to get started.")
        _show_sample_result()
        return

    # ── analyze ───────────────────────────────────────────────────────────────
    if not st.button("🔍 Analyze My Stroke", type="primary", use_container_width=True):
        return

    user_path = _save_upload(user_file, "user")

    if ref_choice == "Upload my own reference":
        if ref_file is None:
            st.error("Please upload a reference video, or switch to the built-in reference.")
            return
        ref_path = _save_upload(ref_file, "ref")
    else:
        ref_path = DEFAULT_REFERENCE

    # Validate both videos are readable before the (slow) pipeline runs.
    ok_u, msg_u = validate_video(user_path, role="user video")
    if not ok_u:
        st.error(f"Your video could not be read: {msg_u}")
        return
    ok_r, msg_r = validate_video(ref_path, role="reference video")
    if not ok_r:
        st.error(f"Reference video could not be read: {msg_r}")
        return

    with st.spinner("Analyzing your stroke — pose extraction + reference comparison (~1-3 min)…"):
        try:
            success = run_pipeline(user_video=user_path, ref_video=ref_path, stroke=stroke)
        except Exception as exc:
            st.error(f"❌ Analysis failed: {exc}")
            st.markdown(
                "**Common causes:** the person isn't clearly visible throughout, the "
                "video is too short, poor/blurry lighting, or an unsupported codec "
                "(use MP4 H.264)."
            )
            return

    if not success:
        st.error("Analysis did not complete. Check the terminal running Streamlit for details.")
        return

    from streamlit_app import get_latest_session
    st.session_state["upload_last_session"] = get_latest_session()
    st.balloons()
    st.rerun()


# ── sub-components ─────────────────────────────────────────────────────────────

def _show_results(session_id):
    from streamlit_app import load_report_data

    st.markdown("## ✅ Analysis Complete!")
    st.markdown("---")

    if not session_id:
        st.warning("Session ID not found — check the outputs/ folder manually.")
        return

    data = load_report_data(session_id)
    if not data:
        st.error("Could not load report data. Check outputs/ folder.")
        return

    # ── headline metrics ──────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        tech = data.get("technique_score", 0)
        st.metric("Technique Score", f"{tech:.1f}/100", "vs reference")
    with col2:
        ready = data.get("readiness_score", 0)
        level = data.get("readiness_level", "—")
        st.metric("Match Readiness", f"{ready:.1f}/100", level)
    with col3:
        stype = data.get("session_type", "Technique")
        intensity = data.get("intensity", "Moderate")
        st.metric("Today's Training", stype, f"{intensity} intensity")

    st.markdown("---")

    # ── coach insight ─────────────────────────────────────────────────────────
    st.markdown("### 💬 Coach's Top Feedback")
    raw = data.get("raw_content", "")
    focus_match = re.search(r"Today's Focus.*?\n+(.*?)\n\n(?:---|##)", raw, re.DOTALL)
    if focus_match:
        st.info(focus_match.group(1).strip())
    else:
        st.info("See the full report below for detailed coaching feedback.")

    # ── download report ───────────────────────────────────────────────────────
    report_path = Path("outputs") / session_id / "report.md"
    if report_path.exists():
        st.markdown("### 📄 Full Coaching Report")
        with open(report_path, "r", encoding="utf-8") as f:
            report_md = f.read()
        st.download_button(
            "⬇️ Download Full Report (.md)",
            data=report_md,
            file_name=f"coach_ai_report_{session_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        with st.expander("Preview full report", expanded=False):
            st.markdown(report_md)

    # ── reliability note ──────────────────────────────────────────────────────
    conf = data.get("readiness_confidence", 0)
    if conf and conf < 60:
        st.warning(
            f"⚠️ Measurement confidence is {conf}% — some metrics had low reliability. "
            "This usually means the camera angle wasn't fully side-on, or parts of the "
            "body were occluded. Film from the side with your full body in frame for "
            "more accurate scores."
        )


def _show_sample_result():
    """Show a teaser/example so first-time users know what to expect."""
    st.markdown("### 📋 What you'll get")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Technique score", "62.4 / 100")
    with col2:
        st.metric("Movement phases", "4")
    with col3:
        st.metric("Drills & cues", "6+")

    st.markdown(
        """
- Phase-by-phase breakdown (Preparation, Load, Contact, Follow-through)
- Hip rotation, elbow angle, knee bend, stance width vs professional reference
- Match readiness signal + recommended training intensity
- Downloadable coaching report with specific drills
- "Ask Coach AI" to explain any metric
"""
    )
