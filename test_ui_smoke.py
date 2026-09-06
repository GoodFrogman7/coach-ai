"""
Smoke test for the Streamlit dashboard using streamlit.testing.AppTest.

Renders every page of streamlit_app.py headlessly against a throwaway
outputs/ + users/ tree and asserts no page raises. This guards the router and
the ui/ package split; it does not check visual output.
"""
import os
import shutil
from pathlib import Path

import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

ROOT = Path(__file__).parent
APP = ROOT / "streamlit_app.py"

SAMPLE_REPORT = """---
session_id: 2026-01-01_10-00-00
---
# Coach AI Report

## 🎯 Similarity Score

Overall Technique Score: 71.5/100

## Today's Focus

Your Top Priorities:

1. **[Contact]** Keep the hitting arm extended through contact.
2. **[Load]** Coil the hips further before the forward swing.

## 🎯 Match Readiness Assessment

**Readiness Score**: 68.0/100
Overall Readiness: Good
Confidence: 72%

## Suggested Drills

### Drill 1

**Shadow swings**: Ten slow swings focusing on hip rotation.

---
"""


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Run the app from a temp cwd that has one fake session and no users."""
    work = tmp_path / "work"
    for sub in ("outputs/2026-01-01_10-00-00", "users", "kb"):
        (work / sub).mkdir(parents=True)
    (work / "outputs/2026-01-01_10-00-00/report.md").write_text(SAMPLE_REPORT, encoding="utf-8")
    for kb_file in (ROOT / "kb").glob("*.md"):
        shutil.copy(kb_file, work / "kb" / kb_file.name)
    monkeypatch.chdir(work)
    return work


def _run(page: str, sandbox: Path) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.session_state["navigate_to"] = page
    at.run()
    return at


PAGES = [
    "🎥 New Analysis", "🏠 Dashboard", "📅 Sessions", "📈 Progress & Trends",
    "🏆 Achievements", "🎯 Reference Comparison", "💪 Training & Drills",
    "📊 Ball & Rally", "🤖 Ask Coach",
]


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing not available")
@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page, sandbox):
    at = _run(page, sandbox)
    assert not at.exception, f"{page} raised: {[e.value for e in at.exception]}"
    # The router only reads sessions after the sidebar is drawn; every page
    # must at least produce the sidebar title.
    assert any("Coach AI" in t.value for t in at.sidebar.title)


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing not available")
def test_unlinked_session_is_adopted_by_default_user(sandbox):
    _run("🏠 Dashboard", sandbox)
    profile = sandbox / "users" / "default_user.json"
    assert profile.exists()
    assert "2026-01-01_10-00-00" in profile.read_text(encoding="utf-8")


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing not available")
def test_no_sessions_shows_warning(tmp_path, monkeypatch):
    work = tmp_path / "empty"
    (work / "users").mkdir(parents=True)
    monkeypatch.chdir(work)
    at = _run("🏠 Dashboard", work)
    assert not at.exception
    assert any("No sessions yet" in w.value for w in at.warning)


def test_legacy_entry_points_are_gone():
    assert not (ROOT / "streamlit_app_v2.py").exists()
    assert not (ROOT / "upload_page.py").exists()
    assert os.path.exists(ROOT / "ui" / "pages" / "upload.py")
