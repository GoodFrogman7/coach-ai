# Player Baseline & Personalization (Phase 5.1)

## Overview

Player Baseline & Personalization adds **personal reference values** to Coach AI by aggregating historical session data. This enables **relative interpretation**: instead of only knowing your technique score is 75%, you can now see that it's "8% above your personal baseline."

**IMPORTANT**: Baselines represent YOUR typical performance, not absolute standards or professional benchmarks. They enable tracking YOUR improvement journey over time.

---

## What is a Player Baseline?

A player baseline is the **average of your recent performance** across multiple sessions. It establishes:

- Your typical technique score
- Your typical readiness score  
- Your typical biomechanical metrics (elbow angle, hip rotation, etc.)

This personal context makes coaching more meaningful:
- "Your recovery time is 15% faster than your baseline" (improvement!)
- "Your technique score is stable within 5% of baseline" (consistency)
- "Your readiness is 10% below baseline" (potential fatigue or off-day)

---

## Key Concepts

### Absolute vs Relative Scoring

| Type | What It Measures | Example |
|------|-----------------|---------|
| **Absolute** | Comparison to professional reference (Djokovic) | "Your technique is 75% similar to Djokovic" |
| **Relative** | Comparison to YOUR typical performance | "Your technique is 8% above YOUR baseline" |

**Both are valuable**:
- Absolute scores show technical quality against standards
- Relative scores show YOUR personal improvement trend

### Rolling Baseline

The baseline is computed from your **last N sessions** (default: 10). This means:
- ✅ Adapts as you improve
- ✅ Reflects recent form  
- ✅ Automatically updates
- ❌ Requires minimum 3 sessions

---

## Implementation

### 1. Historical Session Loading

**Function**: `load_historical_sessions(output_dir="outputs", max_sessions=10)`

**What It Does**:
- Scans `outputs/` directory for session subdirectories
- Extracts technique scores, readiness scores, and metrics
- Returns list of sessions (newest first)

**Data Sources**:
- `user_features.csv` for biomechanical metrics
- `report.md` for technique and readiness scores

**Example Output**:
```python
[
    {
        'session_id': '2025-12-29_13-12-31',
        'timestamp': '2025-12-29_13-12-31',
        'technique_score': 78.5,
        'readiness_score': 82.0,
        'metrics': {'elbow_angle': 152.5, 'hip_rotation': 45.2}
    },
    ...
]
```

### 2. Baseline Computation

**Function**: `compute_player_baseline(historical_sessions, min_sessions=3)`

**What It Does**:
- Aggregates historical data
- Computes mean and standard deviation
- Returns baseline summary

**Minimum Requirements**:
- At least 3 sessions needed
- Returns `has_baseline=False` if insufficient data

**Example Output**:
```python
{
    'has_baseline': True,
    'session_count': 8,
    'baseline_technique_score': 76.3,
    'baseline_readiness_score': 74.5,
    'baseline_metrics': {
        'elbow_angle': {'mean': 151.2, 'std': 2.8, 'sample_size': 8},
        'hip_rotation': {'mean': 44.5, 'std': 3.1, 'sample_size': 8}
    },
    'computed_at': '2025-12-29 14:30:00'
}
```

### 3. Relative Comparison

**Function**: `compare_to_baseline(current_value, baseline_value, metric_name)`

**What It Does**:
- Computes delta (absolute and percent)
- Classifies as above/below/stable (±5% threshold)
- Generates human-readable interpretation

**Example**:
```python
comparison = compare_to_baseline(
    current_value=82.5,
    baseline_value=76.3,
    metric_name='Technique score'
)

# Returns:
{
    'delta_absolute': 6.2,
    'delta_percent': 8.1,
    'delta_direction': 'above',
    'interpretation': 'Technique score is 8.1% above baseline'
}
```

---

## Pipeline Integration

### Step 4.12 in Pipeline

```python
# Load historical sessions
historical_sessions = load_historical_sessions(output_dir="outputs", max_sessions=10)

# Compute baseline
player_baseline = compute_player_baseline(historical_sessions, min_sessions=3)

# Compare current session to baseline
if player_baseline.get('has_baseline'):
    baseline_comparisons = {}
    
    # Compare technique
    if current_technique_score:
        baseline_comparisons['technique'] = compare_to_baseline(
            current_value=current_technique_score,
            baseline_value=player_baseline['baseline_technique_score'],
            metric_name='Technique score'
        )
    
    # Compare readiness
    if current_readiness_score:
        baseline_comparisons['readiness'] = compare_to_baseline(
            current_value=current_readiness_score,
            baseline_value=player_baseline['baseline_readiness_score'],
            metric_name='Readiness score'
        )
```

---

## Report Integration

The Player Baseline section appears in `report.md` after Training Load:

```markdown
## 📊 Personal Baseline & Progress Context

### Your Baseline (computed from 8 sessions)

**Typical Technique Score**: 76.3%
**Typical Readiness Score**: 74.5/100

### Today's Session vs Your Baseline

**📈 Technique score is 8.1% above baseline**

**📈 Readiness score is 10.1% above baseline**

### How to Interpret Baseline Comparisons

**Above Baseline**: You're performing better than your typical level. Good sign!

**Stable (within 5%)**: Consistent with your usual performance. Normal variation.

**Below Baseline**: You're performing below your typical level. Could indicate fatigue or regression.
```

---

## Graceful Degradation

### Insufficient Historical Data

**Scenario**: Fewer than 3 sessions available

**Behavior**:
- `has_baseline` = False
- Reason provided (e.g., "Insufficient data (need 3 sessions, have 2)")
- Report section skipped
- No errors or crashes

### Missing Data in Sessions

**Scenario**: Some sessions lack certain metrics

**Behavior**:
- Compute baseline from available data only
- `sample_size` tracks how many sessions contributed to each metric
- Baselines still computed if at least 3 sessions have the metric

**Example**:
```python
# Session 1: technique=75, readiness=70
# Session 2: technique=78, readiness=None
# Session 3: technique=None, readiness=72

# Result:
{
    'baseline_technique_score': 76.5,  # Average of 75, 78
    'baseline_readiness_score': 71.0,  # Average of 70, 72
}
```

### First 1-2 Sessions

**Behavior**:
- Baseline section does not appear in report
- No errors or warnings
- System operates normally with absolute scoring only

---

## Use Cases

### Use Case 1: Tracking Improvement

**Scenario**: Athlete works on technique for several weeks

**Before Baseline**:
- "Your technique is 72% similar to Djokovic"
- Hard to know if this is improvement or typical

**After Baseline**:
- "Your technique is 72% (15% above your baseline of 62.6%)"
- Clear improvement signal!

### Use Case 2: Detecting Regression

**Scenario**: Athlete has off-day or fatigue

**Baseline Comparison**:
- "Your technique is 65% (12% below your baseline of 73.8%)"
- Signals potential issue worth investigating

### Use Case 3: Consistency Validation

**Scenario**: Athlete maintains steady performance

**Baseline Comparison**:
- "Your technique is stable (within 5% of baseline)"
- Confirms consistency, which is valuable for competition

---

## Limitations & Important Notes

### What Baselines ARE
✅ Personal performance averages  
✅ Relative improvement tracking  
✅ Context for daily variation  
✅ Motivation through visible progress

### What Baselines ARE NOT
❌ Absolute standards or goals  
❌ Professional benchmarks  
❌ Predictors of future performance  
❌ Substitutes for absolute scoring

### Technical Constraints

**Minimum Data Requirements**:
- Need 3+ sessions for baseline
- More sessions = more reliable baseline (use 5-10 ideally)

**Adaptation Period**:
- Baselines update automatically with new sessions
- Rolling window means baseline adapts as you improve
- If you improve significantly, "above baseline" becomes the new baseline

**Statistical Accuracy**:
- Mean and std computed from available data
- No outlier filtering (future enhancement)
- No weighting by recency (future enhancement)

---

## Future Enhancements (Not in Phase 5.1)

Potential directions:

- **Weighted Rolling Average**: Recent sessions weighted more heavily
- **Outlier Filtering**: Ignore statistical outliers
- **Baseline Stability Score**: Track how stable the baseline is
- **Baseline Projection**: Estimate future baseline trajectory
- **Multi-Metric Dashboards**: Visualize all metrics vs baseline over time
- **Baseline Confidence Intervals**: Statistical uncertainty quantification

---

## Testing

Comprehensive test suite validates:

1. ✅ Baseline computation from historical sessions
2. ✅ Insufficient data (graceful degradation)
3. ✅ Comparison above baseline
4. ✅ Comparison below baseline
5. ✅ Comparison stable (within 5%)
6. ✅ Baseline with missing data
7. ✅ Statistical aggregation (mean, std)
8. ✅ Edge case: zero baseline

Run tests:
```bash
python test_player_baseline.py
```

---

## Example Workflow

### Session 1-2: Building History
- No baseline computed (need 3 sessions)
- Absolute scoring only
- Data stored for future baseline

### Session 3: First Baseline
- Baseline computed from sessions 1-3
- Technique baseline: 74.2%
- Current session compared to baseline
- "Technique is 3% above baseline"

### Session 4-10: Refining Baseline
- Baseline updated with each session
- More data = more reliable baseline
- Baseline adapts as athlete improves

### Session 11+: Stable Baseline
- Rolling window (last 10 sessions)
- Baseline represents recent form
- Old sessions drop out automatically

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────┐
│            Historical Sessions (outputs/)            │
│  • Session 1: technique=72, readiness=68           │
│  • Session 2: technique=75, readiness=70           │
│  • Session 3: technique=78, readiness=73           │
│  • ...                                              │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│          load_historical_sessions()                 │
│  Aggregates data from session directories           │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│          compute_player_baseline()                  │
│  Computes mean, std for each metric                 │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│          compare_to_baseline()                      │
│  Current session vs baseline comparison             │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│          Report Section Added                        │
│  "Personal Baseline & Progress Context"             │
└─────────────────────────────────────────────────────┘
```

---

## Summary

Player Baseline & Personalization transforms Coach AI from providing **absolute scores** to providing **relative context**. Athletes can now:

1. **Track improvement** clearly ("15% above baseline!")
2. **Detect regression** early ("12% below baseline - what changed?")
3. **Validate consistency** ("Stable within 5% - ready to compete")

This personalization layer is:
- ✅ **Additive only** - no changes to existing logic
- ✅ **Gracefully degrading** - works with 0, 1, 2, or 3+ sessions
- ✅ **Backward compatible** - report works without it
- ✅ **Fully automatic** - no configuration needed

Baselines make coaching more **personal, motivating, and actionable**.

