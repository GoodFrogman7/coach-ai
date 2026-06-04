"""
upload_page.py
Upload → Analyze → Result loop for Coach AI.
Drop this next to streamlit_app.py and import render_upload_page from it.
"""

import streamlit as st
import tempfile
import shutil
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))


# ── helpers ──────────────────────────────────────────────────────────────────

def _save_upload(uploaded_file, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(uploaded_file.read())


def _run_pipeline_for_upload(user_video_path: str, result_holder: dict) -> None:
    """
    Run the full analysis pipeline in a background thread.
    Writes the session_id or error into result_holder when done.
    """
    try:
        import vision.compare as vc

        # Temporarily override the module-level USER_VIDEO global
        original = vc.USER_VIDEO
        vc.USER_VIDEO = user_video_path

        success = vc.run_pipeline()

        vc.USER_VIDEO = original  # restore

        if success:
            # Find the session that was just created (newest outputs/ subdir)
            outputs = Path("outputs")
            sessions = sorted(
                [d.name for d in outputs.iterdir() if d.is_dir() and len(d.name) == 19],
                reverse=True,
            )
            result_holder["session_id"] = sessions[0] if sessions else None
            result_holder["status"] = "done"
        else:
            result_holder["status"] = "error"
            result_holder["error"] = "Pipeline returned False. Check video quality."

    except Exception as exc:
        import traceback
        result_holder["status"] = "error"
        result_holder["error"] = str(exc)
        result_holder["traceback"] = traceback.format_exc()


# ── main render function ──────────────────────────────────────────────────────

def render_upload_page():
    st.title("🎾 Analyze Your Stroke")
    st.markdown(
        "Upload a video of your tennis backhand and get a personalized AI coaching report "
        "in ~2 minutes."
    )

    # ── filming tips ─────────────────────────────────────────────────────────
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

    # ── uploader ─────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload your video",
        type=["mp4", "mov", "avi", "mkv"],
        help="MP4 (H.264) recommended. Max ~500 MB.",
    )

    if uploaded is None:
        st.info("Upload a video above to get started.")
        _show_sample_result()
        return

    # Show file info
    file_mb = len(uploaded.getvalue()) / (1024 * 1024)
    st.success(f"✅ Received: **{uploaded.name}** ({file_mb:.1f} MB)")

    # Quick video validation via OpenCV
    try:
        import cv2, numpy as np
        tmp_check = Path(tempfile.mktemp(suffix=Path(uploaded.name).suffix))
        tmp_check.write_bytes(uploaded.getvalue())
        cap = cv2.VideoCapture(str(tmp_check))
        ok = cap.isOpened()
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        tmp_check.unlink(missing_ok=True)

        if not ok or frames < 30:
            st.error(
                "❌ Could not read video or video is too short (need ≥ 30 frames / ~1 second)."
            )
            return

        st.caption(f"Video: {w}×{h} @ {fps:.0f} fps — {frames} frames ({frames/fps:.1f}s)")

        if fps < 24:
            st.warning("⚠️ Frame rate is below 24 fps — pose detection may be less accurate.")
        if w < 640:
            st.warning("⚠️ Resolution is below 640px wide — consider a higher quality recording.")

    except Exception as e:
        st.warning(f"Could not validate video metadata: {e}. Proceeding anyway.")

    st.markdown("---")

    # ── analyze button ────────────────────────────────────────────────────────
    if "analysis_state" not in st.session_state:
        st.session_state.analysis_state = "idle"  # idle | running | done | error

    if st.session_state.analysis_state == "idle":
        if st.button("🔍 Analyze My Stroke", type="primary", use_container_width=True):
            # Save upload to data/user/input.mp4 (the hardcoded pipeline path)
            dest = Path("data/user/input.mp4")
            _save_upload(uploaded, dest)

            # Store result in session_state dict (mutable, thread-safe for reads)
            st.session_state.result_holder = {"status": "running"}
            st.session_state.analysis_state = "running"

            # Launch background thread
            t = threading.Thread(
                target=_run_pipeline_for_upload,
                args=(str(dest), st.session_state.result_holder),
                daemon=True,
            )
            t.start()
            st.session_state.analysis_thread = t
            st.rerun()

    if st.session_state.analysis_state == "running":
        _show_progress_ui()

        # Poll for completion
        result = st.session_state.get("result_holder", {})
        if result.get("status") == "done":
            st.session_state.analysis_state = "done"
            st.session_state.last_session_id = result.get("session_id")
            st.rerun()
        elif result.get("status") == "error":
            st.session_state.analysis_state = "error"
            st.session_state.analysis_error = result.get("error", "Unknown error")
            st.rerun()
        else:
            time.sleep(3)
            st.rerun()

    if st.session_state.analysis_state == "done":
        session_id = st.session_state.get("last_session_id")
        _show_results(session_id)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Open Full Dashboard", use_container_width=True):
                st.session_state.analysis_state = "idle"
                st.session_state.navigate_to = "🏠 Dashboard"
                st.rerun()
        with col2:
            if st.button("🔄 Analyze Another Video", use_container_width=True):
                st.session_state.analysis_state = "idle"
                st.rerun()

    if st.session_state.analysis_state == "error":
        err = st.session_state.get("analysis_error", "Unknown error")
        st.error(f"❌ Analysis failed: {err}")
        st.markdown("**Common causes:**")
        st.markdown(
            "- The person is not clearly visible throughout the video\n"
            "- The video is too short (need the full stroke motion)\n"
            "- Poor lighting or very blurry footage\n"
            "- Unsupported codec (use MP4 H.264)"
        )
        if st.button("Try Again", use_container_width=True):
            st.session_state.analysis_state = "idle"
            st.rerun()


# ── sub-components ────────────────────────────────────────────────────────────

def _show_progress_ui():
    st.markdown("### ⏳ Analyzing your stroke…")

    steps = [
        ("🦾", "Extracting pose landmarks", "MediaPipe tracks 33 body points per frame"),
        ("📐", "Computing biomechanical features", "Joint angles, hip rotation, spine lean"),
        ("🔍", "Detecting contact frame", "Finding the moment of impact"),
        ("📊", "Segmenting movement phases", "Prep → Load → Contact → Follow-through"),
        ("🤖", "ML similarity scoring", "Comparing your pattern to Djokovic"),
        ("📝", "Generating coaching report", "Building your personalized feedback"),
    ]

    progress_bar = st.progress(0)
    status_box = st.empty()

    # Animate through steps (approximate — real time is unknown)
    for i, (icon, title, detail) in enumerate(steps):
        frac = (i + 1) / len(steps)
        progress_bar.progress(frac)
        status_box.markdown(
            f"**{icon} {title}**  \n<span style='color:gray;font-size:13px'>{detail}</span>",
            unsafe_allow_html=True,
        )
        time.sleep(0.5)

    st.info(
        "⏱️ Full analysis takes **1–3 minutes** depending on video length. "
        "This page auto-refreshes every few seconds."
    )


def _show_results(session_id: str | None):
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
        st.metric("Technique Score", f"{tech:.1f}/100", "vs Djokovic reference")
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
    # Pull the "Today's Focus" section from the report markdown
    import re
    focus_match = re.search(
        r"## 🎓 Today's Focus\n\n(.*?)\n\n---",
        raw,
        re.DOTALL,
    )
    if focus_match:
        st.info(focus_match.group(1).strip())
    else:
        st.info("See the full report for detailed coaching feedback.")

    # ── download report ───────────────────────────────────────────────────────
    report_path = Path("outputs") / session_id / "report.md"
    if report_path.exists():
        st.markdown("### 📄 Full Coaching Report")
        with open(report_path, "r") as f:
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
    if conf < 60:
        st.warning(
            f"⚠️ Measurement confidence is {conf}% — some metrics had low reliability. "
            "This usually means the camera angle wasn't fully side-on, or parts of the body "
            "were occluded. Film from the side with your full body in frame for more accurate scores."
        )


def _show_sample_result():
    """Show a teaser/example so first-time users know what to expect."""
    st.markdown("---")
    st.markdown("### 📋 What you'll get")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
<div style='background:var(--color-background-secondary);padding:16px;border-radius:8px;text-align:center'>
<div style='font-size:28px;font-weight:500'>62.4</div>
<div style='font-size:12px;color:var(--color-text-secondary)'>Technique score /100</div>
</div>""",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
<div style='background:var(--color-background-secondary);padding:16px;border-radius:8px;text-align:center'>
<div style='font-size:28px;font-weight:500'>4</div>
<div style='font-size:12px;color:var(--color-text-secondary)'>Movement phases analyzed</div>
</div>""",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
<div style='background:var(--color-background-secondary);padding:16px;border-radius:8px;text-align:center'>
<div style='font-size:28px;font-weight:500'>6+</div>
<div style='font-size:12px;color:var(--color-text-secondary)'>Drills & coaching cues</div>
</div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        """
- Phase-by-phase breakdown (Preparation, Load, Contact, Follow-through)
- Hip rotation, elbow angle, knee bend, stance width vs professional reference
- Match readiness signal + recommended training intensity
- Downloadable coaching report with specific drills
- "Ask Coach AI" to explain any metric
"""
    )

