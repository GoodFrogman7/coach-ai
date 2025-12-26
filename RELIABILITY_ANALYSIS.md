# System Reliability & Confidence Analysis

## Overview

This module adds evaluation and validation metrics to assess the robustness and reliability of Coach AI's biomechanical measurements and technique analysis.

## What Was Added

### 1. Confidence Statistics (`compute_confidence_statistics`)

Computes statistical measures (mean, std, min, max, range, coefficient of variation) for each key biomechanical metric across all frames.

**Purpose**: Quantify measurement stability and identify potentially noisy metrics.

**Metrics Analyzed**:
- Shoulder angles (left/right)
- Elbow angles (left/right)
- Knee angles (left/right)
- Hip rotation
- Spine lean
- Stance width (normalized)

**Output**: Dictionary containing statistics for each metric:
```python
{
    'left_shoulder_angle': {
        'mean': 145.2,
        'std': 36.2,
        'min': 98.4,
        'max': 178.9,
        'range': 80.5,
        'cv': 0.249  # Coefficient of variation
    },
    ...
}
```

### 2. Measurement Reliability Assessment (`assess_measurement_reliability`)

Classifies each metric's reliability level based on variance thresholds.

**Classification Criteria**:

**For Joint Angles**:
- **High Reliability**: std < 10° (very stable)
- **Medium Reliability**: std 10-20° (moderate variation)
- **Low Reliability**: std > 20° (high variation)

**For Other Metrics** (rotation, lean, width):
- **High Reliability**: CV < 15% (very stable)
- **Medium Reliability**: CV 15-30% (moderate variation)
- **Low Reliability**: CV > 30% (high variation)

**What This Means**:
- **High**: Measurement is trustworthy for analysis
- **Medium**: Acceptable with natural variation
- **Low**: Use with caution - may indicate noise or dynamic movement

### 3. Intra-Phase Stability (`compute_intra_phase_stability`)

Measures consistency of biomechanical metrics within each movement phase.

**Purpose**: Assess technique repeatability and identify phases with inconsistent execution.

**Computation**:
- For each phase (Preparation, Load, Contact, Follow-through)
- Compute standard deviation of each metric within that phase
- Calculate coefficient of variation (CV)
- Convert to stability score (0-100, higher = more stable)

**Scoring**:
- CV < 0.1 → 100 (excellent)
- CV < 0.2 → 90 (very good)
- CV < 0.3 → 75 (good)
- CV < 0.5 → 60 (fair)
- CV ≥ 0.5 → 50 (variable)

**Output**: Dictionary per phase:
```python
{
    'preparation': {
        'metrics': {
            'left_shoulder_angle': {'std': 3.2, 'cv': 0.022},
            ...
        },
        'overall_score': 94.2
    },
    ...
}
```

### 4. New Report Section

Added **"System Reliability & Confidence Analysis"** section to `report.md`.

**Location**: After "Suggested Drills", before "Final Thoughts"

**Contents**:
1. **Explanation** of what reliability and stability mean
2. **Measurement Reliability** grouped by level (High/Medium/Low)
3. **Technique Stability by Phase** with 0-100 scores
4. **Interpretation Guide** for understanding the metrics

**Example Output**:
```markdown
## System Reliability & Confidence Analysis

### Measurement Reliability

✓ High Reliability - Very stable measurements:
- Left Knee Angle: 6.1° std dev
- Spine Lean: 2.9° std dev

~ Medium Reliability - Moderate variation:
- Right Shoulder Angle: 15.7° std dev
- Right Knee Angle: 12.8° std dev

✗ Lower Reliability - Higher variation:
- Left Elbow Angle: 41.0° std dev
- Hip Rotation: 88.3° std dev

### Technique Stability by Phase

- Preparation: 94.2/100 ✓ Excellent
- Load: 81.7/100 ✓ Good
- Contact: 53.3/100 ○ Variable
- Follow-through: 96.7/100 ✓ Excellent
```

## Implementation Details

### Files Modified

**`vision/compare.py`** (~180 lines added):

1. **New Functions** (added after ML similarity functions):
   - `compute_confidence_statistics()` - Statistical analysis
   - `assess_measurement_reliability()` - Reliability classification
   - `compute_intra_phase_stability()` - Phase consistency metrics
   - `interpret_reliability_level()` - Human-readable interpretations

2. **Updated Functions**:
   - `generate_report()` - Added 3 new parameters, new report section
   - `run_pipeline()` - Added Step 4.9 for reliability computation

### Pipeline Integration

**New Step 4.9**: "Computing reliability and confidence metrics"

**Execution Flow**:
1. Compute confidence statistics from features DataFrame
2. Assess measurement reliability based on variance
3. Compute intra-phase stability scores
4. Pass metrics to report generator
5. Graceful fallback if computation fails

**Console Output Example**:
```
[4.9/5] Computing reliability and confidence metrics...
  -> Reliability: 2 high, 2 medium, 5 low
  -> Average phase stability: 81.5/100
```

## Use Cases

### 1. Quality Assurance

Identify when measurements are unreliable due to:
- Poor lighting or camera angle
- Occlusion of body landmarks
- Video quality issues
- Rapid dynamic movements

**Example**: High variation in elbow angles may indicate tracking difficulties.

### 2. Technique Consistency Analysis

Assess how repeatable the user's technique is within each phase.

**Example**: Low stability in Contact phase (53.3/100) suggests inconsistent ball contact mechanics.

### 3. System Debugging

Compare reliability across different:
- Users
- Videos
- Camera setups
- Reference athletes

**Example**: If all metrics show low reliability, review video quality or camera placement.

### 4. Coaching Insights

Identify which aspects of technique are consistent vs. variable.

**Example**: 
- High preparation stability (94.2) → setup is consistent
- Low contact stability (53.3) → impact timing varies
- **Focus**: Work on contact phase consistency

## Backward Compatibility

The reliability analysis is **completely optional** and additive:

✅ **Graceful Fallback**: If computation fails, pipeline continues without reliability section
✅ **No Breaking Changes**: All existing outputs remain identical
✅ **Optional Section**: Report section only appears if metrics are computed
✅ **No Configuration Required**: Works automatically with default setup

**If Reliability Computation Fails**:
- Warning message printed: "[WARNING] Could not compute reliability metrics: {error}"
- Pipeline continues normally
- Report generated without reliability section
- All other analysis remains intact

## Interpretation Guide for Users

### High Reliability Metrics

**What it means**: The system tracked this metric accurately throughout your stroke.

**Action**: Trust these measurements for technique improvements.

**Example**: "Spine Lean: 2.9° std dev" → Very stable measurement, coaching cues based on this are trustworthy.

### Medium Reliability Metrics

**What it means**: Some natural variation present, but measurements are acceptable.

**Action**: Consider general trends rather than exact values.

**Example**: "Right Shoulder Angle: 15.7° std dev" → Reasonable variation for dynamic movement.

### Low Reliability Metrics

**What it means**: High variation may be due to:
- Rapid dynamic movement (natural)
- Tracking difficulties
- Actual technique inconsistency

**Action**: Use with caution. Consider:
- Is this metric naturally variable in this sport?
- Were there tracking/video issues?
- Is my technique actually inconsistent here?

**Example**: "Hip Rotation: 88.3° std dev" → Large variation, investigate cause (technique vs. tracking).

### Phase Stability Scores

**90-100 (Excellent)**: Highly repeatable technique in this phase. Biomechanics are consistent.

**75-89 (Good)**: Generally consistent with minor variations. Technique is solid.

**60-74 (Fair)**: Moderate consistency. Some room for improvement in repeatability.

**<60 (Variable)**: Inconsistent execution. Focus on consistency in this phase.

## Technical Notes

### Why Coefficient of Variation?

CV = std / mean allows comparison across metrics with different scales:
- Joint angles (degrees)
- Rotation (degrees)
- Normalized distances (unitless)

CV is scale-independent and better for cross-metric comparison.

### Why Different Thresholds for Angles vs. Other Metrics?

**Angles**: Use absolute std (degrees) because:
- Physical meaning is clear (10° is objectively small)
- Consistent scale across all joint angles
- Direct interpretation for coaches

**Other metrics**: Use CV (%) because:
- Different units/scales
- Relative variation more meaningful
- Better for normalized values

### Stability Score Mapping

CV → Stability Score conversion is non-linear to reflect coaching importance:
- Small CV differences at low values (high consistency) → large score differences
- Large CV differences at high values (low consistency) → smaller score differences

This emphasizes the importance of achieving high consistency.

## Future Enhancements

Possible extensions (not yet implemented):

1. **Temporal Reliability**: Track reliability changes across session timeline
2. **Metric Weighting**: Weight reliability by metric importance for overall quality score
3. **Reference Comparison**: Compare user reliability to reference athlete reliability
4. **Longitudinal Tracking**: Track reliability improvements across sessions
5. **Anomaly Detection**: Flag frames with outlier measurements
6. **Camera Angle Recommendations**: Suggest optimal camera placement based on reliability

## Summary

The reliability analysis adds crucial quality assurance to Coach AI:

✅ **Quantifies measurement confidence** with statistical rigor
✅ **Identifies unreliable metrics** for cautious interpretation
✅ **Assesses technique consistency** within movement phases
✅ **Provides actionable insights** for coaches and athletes
✅ **Maintains backward compatibility** with optional, additive implementation
✅ **No configuration required** - works automatically

This enhancement makes Coach AI more robust, trustworthy, and useful for serious technique analysis.

