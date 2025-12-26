# Session Management Implementation Summary

## Overview

Extended Coach AI from a single-run analysis script into a **session-aware, persistent coaching system** while preserving all existing functionality and outputs.

## What Was Added

### 1. Session Management Functions

Added to `vision/compare.py`:

#### `generate_session_id() -> str`
Generates unique session ID using timestamp format: `YYYY-MM-DD_HH-MM-SS`

**Example**: `2025-12-25_11-58-07`

#### `create_session_directory(session_id, base_dir="outputs") -> Path`
Creates a session-specific output directory.

**Structure**:
```
outputs/
├── 2025-12-25_11-58-07/    # Session 1
│   ├── overlay_user.mp4
│   ├── overlay_ref.mp4
│   ├── user_features.csv
│   ├── ref_features.csv
│   └── report.md
├── 2025-12-25_12-00-35/    # Session 2
│   └── [same files]
└── [legacy files]           # Backward compatibility
```

#### `get_session_paths(session_id=None, base_dir="outputs") -> dict`
Returns dictionary of output file paths for a session.

**Parameters**:
- `session_id`: If provided, paths point to `outputs/<session_id>/`
- If `None`, paths point to `outputs/` (legacy mode)

**Returns**:
```python
{
    'output_dir': Path,
    'overlay_user': Path,
    'overlay_ref': Path,
    'features_user': Path,
    'features_ref': Path,
    'report': Path
}
```

### 2. Report Metadata Header

Enhanced `generate_report()` to include YAML-style metadata when `session_id` is provided.

**Added Parameters**:
- `session_id`: Optional session identifier
- `user_id`: User identifier (default: "default_user")

**Metadata Format**:
```yaml
---
session_id: 2025-12-25_11-58-07
user_id: default_user
reference_video: djokovic_backhand.mp4
generated_at: 2025-12-25T12:00:16.704625
---
```

### 3. Enhanced Pipeline Execution

Updated `run_pipeline()` with:

**Session Initialization**:
```python
try:
    session_id = generate_session_id()
    session_dir = create_session_directory(session_id)
    output_paths = get_session_paths(session_id)
except Exception as e:
    # Fallback to legacy mode
    session_id = None
    output_paths = get_session_paths(session_id=None)
```

**Backward Compatibility**:
- If session creation fails → falls back to `outputs/` directory
- Never crashes due to filesystem issues
- Legacy path constants preserved for compatibility

### 4. Future-Proofing TODO Comments

Added scaffolding comments for future features:

```python
# TODO: Multi-user support - Add user_id parameter to session management
# TODO: Progress tracking - Store session history in a sessions.json file
# TODO: Real-time inference - Stream processing for live video analysis
```

## Files Modified

### ✅ `vision/compare.py` - ONLY FILE MODIFIED

**Changes Made**:
1. Added `datetime` import
2. Added session management functions (3 new functions)
3. Added TODO comments for future features
4. Enhanced `generate_report()` signature with `session_id` and `user_id` parameters
5. Added metadata header generation logic
6. Updated `run_pipeline()` with session logic and fallback handling
7. Kept legacy path constants for backward compatibility

**Lines Added**: ~120 lines
**Lines Modified**: ~15 lines  
**Lines Removed**: 0 lines

## Validation Results

### Test 1: First Session
```
[SESSION] Session ID: 2025-12-25_11-58-07
[SESSION] Output directory: outputs\2025-12-25_11-58-07
[SESSION] All outputs saved to: outputs\2025-12-25_11-58-07
```

**Output Structure**:
```
outputs/2025-12-25_11-58-07/
├── overlay_user.mp4
├── overlay_ref.mp4
├── user_features.csv
├── ref_features.csv
└── report.md (with metadata header)
```

### Test 2: Second Session (No Overwrite)
```
[SESSION] Session ID: 2025-12-25_12-00-35
[SESSION] Output directory: outputs\2025-12-25_12-00-35
[SESSION] All outputs saved to: outputs\2025-12-25_12-00-35
```

**Verified**:
- ✅ New session directory created
- ✅ Previous session preserved intact
- ✅ Both sessions have complete outputs
- ✅ Metadata headers have unique session_id and timestamps

### Test 3: Report Metadata
```yaml
---
session_id: 2025-12-25_12-00-35
user_id: default_user
reference_video: djokovic_backhand.mp4
generated_at: 2025-12-25T12:02:38.169515
---

# Two-Handed Backhand Analysis Report
[rest of report unchanged]
```

## Backward Compatibility Verified

### Legacy Outputs Preserved
```
outputs/
├── overlay_user.mp4      # Still exists
├── overlay_ref.mp4       # Still exists
├── user_features.csv     # Still exists
├── ref_features.csv      # Still exists
└── report.md             # Still exists
```

### Fallback Mechanism
If session creation fails:
1. Warning printed: `[WARNING] Falling back to legacy output mode`
2. Pipeline continues using `outputs/` directory
3. No crashes or data loss
4. Analysis results identical

## Benefits

### For Users
- **Session History**: Every run is preserved automatically
- **Progress Tracking**: Can compare technique across sessions
- **No Data Loss**: Previous analyses never overwritten
- **Clear Organization**: Timestamped folders for easy retrieval

### For Developers
- **Extensible**: Ready for multi-user support
- **Traceable**: Metadata enables session tracking
- **Safe**: Fallback ensures reliability
- **Clean**: Session logic isolated in dedicated functions

## Usage

### Running Multiple Sessions

```bash
# Run 1
python vision/compare.py
# Creates: outputs/2025-12-25_11-58-07/

# Run 2 (5 minutes later)
python vision/compare.py
# Creates: outputs/2025-12-25_12-03-12/

# Run 3 (next day)
python vision/compare.py
# Creates: outputs/2025-12-26_09-15-03/
```

### Accessing Session Results

```python
# Example: Load previous session report
import pandas as pd
from pathlib import Path

session_id = "2025-12-25_11-58-07"
session_dir = Path(f"outputs/{session_id}")

# Read features
user_features = pd.read_csv(session_dir / "user_features.csv")

# Read report metadata
with open(session_dir / "report.md") as f:
    lines = f.readlines()
    # Parse YAML header (lines 1-5)
```

## Technical Details

### Session ID Format
- **Format**: `YYYY-MM-DD_HH-MM-SS`
- **Timezone**: Local system time
- **Uniqueness**: Second-level granularity ensures uniqueness for manual runs
- **Sortability**: Lexicographic ordering = chronological ordering

### Timestamp Format (ISO-8601)
- **Format**: `YYYY-MM-DDTHH:MM:SS.mmmmmm`
- **Example**: `2025-12-25T12:02:38.169515`
- **Standard**: ISO 8601 compliant
- **Precision**: Microsecond resolution

### Error Handling
```python
try:
    # Session creation
    session_id = generate_session_id()
    session_dir = create_session_directory(session_id)
except Exception as e:
    # Fallback to legacy mode
    print(f"[WARNING] Session creation failed: {e}")
    session_id = None
    # Use outputs/ directory
```

## Future Enhancements (TODOs)

### 1. Multi-User Support
```python
# Potential implementation:
def get_session_paths(session_id, user_id="default_user"):
    """outputs/<user_id>/<session_id>/"""
    pass
```

### 2. Progress Tracking
```python
# Store session metadata:
# outputs/sessions.json
{
  "2025-12-25_11-58-07": {
    "user_id": "default_user",
    "timestamp": "2025-12-25T11:58:07",
    "similarity_score": 62.4,
    "primary_issues": ["hip_rotation", "elbow_angle"]
  }
}
```

### 3. Real-Time Inference
```python
# Stream processing for live video:
def run_realtime_pipeline(camera_source=0):
    """Analyze live camera feed frame-by-frame"""
    pass
```

## Summary

✅ **Session management implemented**  
✅ **No existing code broken**  
✅ **Backward compatibility maintained**  
✅ **All outputs preserved across runs**  
✅ **Metadata headers added to reports**  
✅ **Future-proofing comments added**  
✅ **Production-ready error handling**  

**Result**: Coach AI is now a **persistent, session-aware coaching system** that tracks every analysis while maintaining 100% compatibility with existing functionality.

