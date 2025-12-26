# Phase Segmentation Extension - Summary

## What Was Added

Extended the Coach AI pipeline with **movement phase segmentation** for detailed stroke analysis.

## New Functions in `features.py`

### 1. `segment_stroke_phases(features_df, impact_frame)`
Segments a backhand stroke into four phases:
- **Preparation**: Start → early hip rotation
- **Load**: Hip rotation peak → acceleration begins  
- **Contact**: Peak acceleration → impact frame
- **Follow-through**: Impact → end of stroke

**Detection Logic**:
- Uses **wrist speed** (combined left + right wrist velocity)
- Uses **hip rotation** (shoulder line vs hip line angle)
- Applies smoothing (5-frame rolling average) for robust transitions
- Dynamically adjusts boundaries based on impact frame location

### 2. `compute_phase_metrics(features_df, phases)`
Computes averaged biomechanical metrics for each phase:
- Shoulder angles (left/right)
- Elbow angles (left/right)
- Knee angles (left/right)
- Hip rotation
- Spine lean
- Stance width
- Phase duration (frames)

## Enhanced Functions in `compare.py`

### 1. `generate_phase_specific_cues(user_phases, ref_phases)`
Generates coaching cues specific to each movement phase:

**Preparation Phase**:
- Shoulder turn completeness
- Stance width setup

**Load Phase**:
- Hip coiling/rotation
- Knee bend depth

**Contact Phase**:
- Covered by existing impact analysis

**Follow-through Phase**:
- Arm extension
- Balance maintenance

### 2. `generate_report(...)` - Extended
Now includes optional phase analysis section with:
- Phase boundary frames for user vs reference
- Per-phase metric comparison tables
- Visual breakdown of all four phases

### 3. `run_pipeline()` - Extended
Added step 4.5 between impact detection and report generation:
- Segments both user and reference strokes into phases
- Computes phase-specific metrics
- Passes phase data to report generator

## Report Output Enhancement

The `outputs/report.md` now includes:

### Movement Phase Analysis Section
For each phase:
```
### [Phase Name] Phase
**Frames**: X-Y (you) | A-B (reference)

| Metric | Your Value | Pro Value | Difference |
|--------|-----------|-----------|------------|
| Hip Rotation | ... | ... | ... |
| Left Elbow Angle | ... | ... | ... |
...
```

### Phase-Specific Coaching Cues
Cues are now labeled by phase:
- `**[Preparation]** Set up with a wider base...`
- `**[Load]** Coil your hips more during the loading phase...`
- `**[Follow-through]** Extend your arms more through the finish...`

## Example Output

From the latest run:

**Phase Detection**:
- User phases: Prep(0-8), Load(9-70), Contact(215-225), Follow(226-256)
- Reference phases: Prep(0-59), Load(60-78), Contact(980-990), Follow(991-1056)

**Key Phase-Specific Findings**:
- **Load phase**: User hip rotation 108.9° vs pro 197.5° (-88.5° deficit)
- **Preparation**: Narrow stance from the start (affects entire stroke)
- **Follow-through**: Limited arm extension (163.4° vs 140.3°)

## Technical Details

**Phase Transition Detection**:
- Preparation → Load: Hip rotation change > 60th percentile
- Load → Contact: Wrist speed exceeds 20% of maximum
- Contact window: ±5 frames around impact
- Follow-through: Contact end → video end

**Robustness**:
- Handles missing/NaN data via forward/backward fill
- Smoothing prevents false transitions from noise
- Fallback percentages if heuristics fail

## No Breaking Changes

- Existing file structure unchanged
- All changes confined to `features.py` and `compare.py`
- Backward compatible (phase analysis is optional enhancement)
- Original impact-based analysis still runs

## Usage

Run exactly as before:
```bash
python vision/compare.py
```

Phase segmentation happens automatically and enhances the report with detailed phase-by-phase analysis.

