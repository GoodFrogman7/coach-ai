"""
Pytest configuration shared across the Coach AI test suite.

- Puts the project root (and vision/) on sys.path so both `from vision.compare
  import ...` and the legacy `from compare import ...` styles resolve.
- Seeds NumPy's RNG before every test so synthetic-data tests are deterministic.
- Delegates the legacy script-style test files (which run their assertions at
  import time) to test_legacy_scripts.py, which executes them as subprocesses.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parent
for _p in (str(ROOT), str(ROOT / "vision")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Legacy files that assert at module import time. They are exercised as
# subprocesses by test_legacy_scripts.py, so don't also import them directly
# (that would double-run them and surface their sys.exit()/stdout during
# collection).
collect_ignore = [
    "test_cv_movement_extraction.py",
    "test_rally_fatigue.py",
    "test_trust_calibration.py",
    "test_intent_comprehensive.py",
    "test_movement_intelligence.py",
    "test_session_memory.py",
    "test_ball_tracking_integration.py",
]


@pytest.fixture(autouse=True)
def _deterministic_rng():
    """Seed RNG before each test so synthetic signals are reproducible."""
    np.random.seed(1234)
    yield
