"""
Run the legacy script-style test files as subprocesses and assert they exit 0.

Several test files predate this pytest harness: they run their assertions at
module import time instead of inside test_* functions. Rather than rewrite them,
we execute each as its own process and check the exit code. This gives real
pass/fail signal under pytest while isolating each script's stdout and any
sys.exit() calls.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent

LEGACY_SCRIPTS = [
    "test_cv_movement_extraction.py",
    "test_rally_fatigue.py",
    "test_trust_calibration.py",
    "test_intent_comprehensive.py",
    "test_movement_intelligence.py",
    "test_session_memory.py",
    "test_ball_tracking_integration.py",
]

# Scripts that require optional dependencies. When those aren't installed the
# test is skipped (not failed) -- the underlying features degrade gracefully.
OPTIONAL_DEPS = {
    "test_ball_tracking_integration.py": ["ultralytics", "seaborn"],
}


@pytest.mark.parametrize("script", LEGACY_SCRIPTS)
def test_legacy_script(script):
    path = ROOT / script
    if not path.exists():
        pytest.skip(f"{script} not present")

    for dep in OPTIONAL_DEPS.get(script, []):
        if importlib.util.find_spec(dep) is None:
            pytest.skip(f"{script} needs optional dependency '{dep}' (not installed)")

    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}

    # Write child output to a temp file rather than a PIPE. On Windows/Python 3.8,
    # subprocess.communicate(timeout=...) with pipes can raise a spurious
    # IndexError from its reader threads; a file-backed stream avoids that race.
    fd, tmp = tempfile.mkstemp(suffix=".log", prefix=f"{Path(script).stem}_")
    try:
        with os.fdopen(fd, "wb") as out:
            result = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(ROOT),
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=600,
            )
        with open(tmp, "r", encoding="utf-8", errors="replace") as fh:
            output = fh.read()
    finally:
        os.unlink(tmp)

    assert result.returncode == 0, (
        f"{script} exited with code {result.returncode}\n"
        f"--- output (tail) ---\n{output[-3000:]}"
    )
