# Coach AI - Streamlit Dashboard (Phase 1)

## Overview

The Coach AI Streamlit Dashboard is a **read-only visualization application** that provides an interactive interface for exploring Coach AI analysis outputs. This is Phase 1: a pure viewer with no modifications to backend logic or analysis.

## Key Principles

**Read-Only Viewer**:
- ✅ Visualizes existing outputs
- ✅ No modifications to backend
- ✅ No writes to disk
- ✅ No additional intelligence
- ✅ Graceful handling of missing data

**Purpose**: Interactive visualization of Coach AI results

## Features

### Tab 1: Performance Overview 📈

**Displays**:
- Overall Technique Score (0-100)
- Performance Level (Excellent/Good/Solid/Developing)
- Session information
- Quick metrics summary

**Data Source**: Latest session report

### Tab 2: Coaching Priorities 🎯

**Displays**:
- Explanation of adaptive coaching prioritization
- Classification levels (CRITICAL/PRIORITY/MONITOR/SUPPRESS)
- Factors considered in prioritization
- Link to full report

**Data Source**: Documentation (read-only text)

### Tab 3: Drill Recommendations 💪

**Displays**:
- Intensity level explanations:
  - 🚨 Intensive (daily, high volume, for CRITICAL issues)
  - ⭐ Moderate (3-5x/week, for PRIORITY issues)
  - 📊 Light (2-3x/week, for improving areas)
- Link to full drill prescriptions in report

**Data Source**: Documentation (read-only text)

### Tab 4: Drill Effectiveness 📊

**Displays**:
- Historical drill outcomes table
- Drill confidence scores (0-1 scale)
- Confidence levels (High/Medium/Low)
- Top effective drills ranking
- Usage count, average improvement, reliability, consistency

**Data Source**:
- `outputs/drill_outcomes.json` (read-only)
- Computed via `compute_drill_confidence_scores()` (read-only function)

**Key Metrics Shown**:
- **Confidence**: Overall confidence score (0-1)
- **Level**: High/Medium/Low classification
- **Usage Count**: Times drill was prescribed
- **Avg Improvement**: Mean delta (negative = improvement)
- **Reliability**: % outcomes with high-confidence measurements
- **Consistency**: Inverse of coefficient of variation

### Tab 5: Progress Tracking 📉

**Displays**:
- Session summary (unique sessions, drills, avg delta)
- Recent drill outcomes table
- Delta trends line chart (by drill or all drills)
- Historical data across sessions

**Data Source**: `outputs/drill_outcomes.json` (read-only)

## Installation

### Prerequisites

```bash
pip install streamlit>=1.28
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

## Usage

### Running the Dashboard

```bash
streamlit run streamlit_app.py
```

The dashboard will open in your browser at `http://localhost:8501`

### Data Requirements

**Minimum**: One completed Coach AI analysis session
- Run: `python vision/compare.py`
- This creates outputs in `outputs/<session_id>/`

**Optional** (for full features):
- Multiple sessions for progress tracking
- `drill_outcomes.json` for effectiveness analysis (accumulates automatically)

### Navigation

1. **Session Selector** (Sidebar):
   - Select from recent sessions
   - Dashboard updates to show selected session data

2. **Tabs**:
   - Click tabs to switch between views
   - All data loads on-demand

3. **Interactive Elements**:
   - Expandable sections in Drill Effectiveness
   - Drill selector for progress trends
   - Sortable/filterable tables

## Technical Implementation

### Files

**`streamlit_app.py`** (~400 lines):
- Main application file
- Read-only data loading helpers
- 5 tab implementations
- Graceful error handling

**`requirements.txt`**:
- Added `streamlit>=1.28,<2.0`

**`README.md`**:
- Updated with dashboard instructions

### Architecture

```
streamlit_app.py
├── Data Loading (read-only)
│   ├── get_latest_session()
│   ├── load_session_report()
│   ├── load_drill_outcomes()
│   └── get_recent_sessions()
│
├── Import Read-Only Functions
│   ├── compute_drill_confidence_scores()
│   └── get_top_effective_drills()
│
└── UI Tabs
    ├── Tab 1: Performance Overview
    ├── Tab 2: Coaching Priorities
    ├── Tab 3: Drill Recommendations
    ├── Tab 4: Drill Effectiveness
    └── Tab 5: Progress Tracking
```

### Data Flow

```
Inputs (read-only):
├── outputs/<session_id>/report.md
├── outputs/drill_outcomes.json
└── vision/compare.py (helper functions)

Dashboard:
├── Load data
├── Parse/process (no writes)
├── Visualize
└── Display

No outputs, no writes, no side effects
```

## Graceful Handling

### Missing Data Scenarios

**No Sessions**:
```
⚠️ No session data found. Run the analysis first: `python vision/compare.py`
```

**No Drill Outcomes**:
```
⚠️ No drill outcome data available yet. Data accumulates across multiple sessions.
```

**Missing Report Data**:
```
📊 Overall score not available in report
```

**Import Errors**:
```
⚠️ Confidence scoring functions not available.
```

All errors are **non-breaking** - the app continues to function with available data.

## UI Components

### Streamlit Elements Used

- `st.title()` - Page title
- `st.tabs()` - Tab navigation
- `st.metric()` - Key metrics display
- `st.dataframe()` - Tabular data
- `st.line_chart()` - Trend visualization
- `st.expander()` - Collapsible sections
- `st.selectbox()` - Dropdown selectors
- `st.info()` / `st.warning()` / `st.success()` - Status messages
- `st.markdown()` - Formatted text

**No custom CSS** - uses Streamlit defaults

## Limitations (By Design)

### Phase 1 Constraints

**Read-Only**:
- ❌ Cannot run analysis from dashboard
- ❌ Cannot modify drill recommendations
- ❌ Cannot edit or save data
- ❌ Cannot trigger new sessions

**Visualization Only**:
- ❌ No video playback
- ❌ No pose visualization
- ❌ No interactive drill selection
- ❌ No coaching feedback generation

**Current Data**:
- Shows data from completed sessions
- No real-time analysis
- No live video processing

## Future Enhancements (Not Implemented)

### Phase 2: Interactive Features

- Video playback within dashboard
- Side-by-side user vs. reference comparison
- Pose overlay visualization
- Interactive metric selection

### Phase 3: Analysis Integration

- Run analysis from dashboard
- Upload videos via UI
- Configure parameters
- Select reference videos

### Phase 4: Advanced Analytics

- Multi-session comparison
- Trend analysis and forecasting
- Drill effectiveness prediction
- Personalized recommendations

### Phase 5: Multi-User

- User authentication
- Multi-athlete tracking
- Coach dashboard
- Team analytics

## Troubleshooting

### Dashboard Won't Start

**Issue**: `ModuleNotFoundError: No module named 'streamlit'`

**Solution**:
```bash
pip install streamlit
# or
pip install -r requirements.txt
```

### No Data Showing

**Issue**: "No session data found"

**Solution**:
1. Run analysis first: `python vision/compare.py`
2. Check `outputs/` directory exists
3. Verify session folders present

### Confidence Scores Not Showing

**Issue**: "Confidence scoring functions not available"

**Solution**:
- Check `vision/compare.py` exists
- Verify functions `compute_drill_confidence_scores` and `get_top_effective_drills` present
- Ensure path imports working

### Progress Chart Empty

**Issue**: No data in progress tracking

**Solution**:
- Run multiple sessions to accumulate data
- `drill_outcomes.json` requires 2+ sessions
- First session establishes baseline

## Development Notes

### Code Quality

- **Clean**: ~400 lines, well-structured
- **Readable**: Clear function names, documented
- **Minimal**: No unnecessary complexity
- **Safe**: Graceful error handling throughout

### Testing

```bash
# Start dashboard
streamlit run streamlit_app.py

# Test scenarios:
1. Fresh install (no data) - should show warnings
2. One session - Performance tab works
3. Multiple sessions - Progress tracking works
4. With drill_outcomes.json - Effectiveness tab works
```

### Extending

To add new visualizations:

1. Add new tab in `st.tabs()` list
2. Implement tab content with `with tabN:`
3. Load data using existing helpers
4. Use Streamlit components for display
5. Handle missing data gracefully

## Summary

The Coach AI Streamlit Dashboard (Phase 1) is a **minimal, read-only visualization layer** that:

📊 **Visualizes** - Existing analysis outputs  
🔍 **Explores** - Historical drill effectiveness  
📈 **Tracks** - Progress across sessions  
🎯 **Displays** - Coaching priorities and metrics  
✅ **Safe** - Zero modifications to backend  

**Implementation**: ~400 lines of clean visualization code, zero backend changes, graceful error handling, ready for future interactive features!

This dashboard provides an **interactive window** into Coach AI's intelligence layers, making complex analysis accessible and insights easy to explore! 🎾📊🚀

