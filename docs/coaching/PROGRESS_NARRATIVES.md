# Progress Narratives & Coach Summaries (Phase 5.2)

## Overview

Progress Narratives & Coach Summaries add **human-readable interpretive summaries** of multi-session trends to Coach AI. Instead of just seeing numbers, athletes get coach-style narratives like:

*"Great progress! Your technique is improving (+7%) and readiness is climbing (+6.8%). You're building momentum across the board."*

**IMPORTANT**: This is interpretive analysis based on observed patterns, NOT predictive modeling or performance guarantees. Trends can change - use this as feedback, not forecast.

---

## What Are Progress Narratives?

Progress narratives transform raw historical data into coach-style summaries:

### Before (Numbers Only)
```
Session 1: Technique 70%
Session 2: Technique 72%
Session 3: Technique 74%
Session 4: Technique 76%
Session 5: Technique 78%
```

### After (Narrative Context)
```
Great progress! Your technique is improving (+7%) over the last 5 sessions.

Coach's Take: You're building momentum. Keep up the consistent work 
and trust the process.
```

---

## Key Features

### 1. **Trend Detection**

Analyzes last N sessions (default: 5) to detect trends in:
- Technique score
- Readiness score
- Other metrics (future expansion)

**Classification**:
- **Improving**: >5% increase from earlier to recent sessions
- **Stable**: Within ±5% (normal variation)
- **Declining**: >5% decrease from earlier to recent sessions

**Conservative Thresholds**: Uses ±5% to avoid over-reacting to normal day-to-day variation.

### 2. **Human-Readable Summaries**

Generates coach-style narratives that:
- ✅ Highlight positive trends first (encouragement)
- ✅ Flag concerns gently (supportive feedback)
- ✅ Avoid absolutes ("always", "never")
- ✅ Avoid predictions ("will improve")
- ✅ Use encouraging language

### 3. **Coach's Take**

Short coaching insight (1-2 sentences) that provides:
- Context for the trends
- Actionable guidance
- Encouragement or course correction

---

## Implementation

### 1. Trend Detection

**Function**: `detect_trend(values, min_sessions=3, threshold_percent=5.0)`

**What It Does**:
- Splits values into earlier/recent halves
- Computes average for each half
- Calculates percent change
- Classifies as improving/stable/declining
- Assesses confidence based on sample size and variance

**Example**:
```python
values = [70.0, 72.0, 74.0, 76.0, 78.0]  # Oldest to newest

trend = detect_trend(values)

# Returns:
{
    'has_trend': True,
    'trend': 'improving',
    'confidence': 'high',
    'earlier_avg': 71.0,  # Average of [70, 72]
    'recent_avg': 76.0,   # Average of [74, 76, 78]
    'percent_change': 7.0
}
```

### 2. Narrative Generation

**Function**: `generate_progress_narrative(historical_sessions, num_sessions=5, min_sessions=3)`

**What It Does**:
- Extracts technique and readiness scores from recent sessions
- Detects trends for each metric
- Generates human-readable summary
- Prioritizes positive trends, then stable, then concerns
- Generates coach's take

**Example**:
```python
narrative = generate_progress_narrative(historical_sessions, num_sessions=5)

# Returns:
{
    'has_narrative': True,
    'session_count': 5,
    'trends': {
        'technique': {
            'trend': 'improving',
            'percent_change': 7.0,
            ...
        },
        'readiness': {
            'trend': 'improving',
            'percent_change': 6.8,
            ...
        }
    },
    'narrative_summary': "Great progress! Your technique is improving...",
    'coach_take': "You're building momentum across the board..."
}
```

### 3. Coach's Take Generation

**Function**: `_generate_coach_take(trends, session_count)`

**Logic**:
| Scenario | Coach's Take |
|----------|-------------|
| 2+ improving | "You're building momentum across the board..." |
| 1 improving, 0 declining | "You're making progress in key areas..." |
| 2+ declining | "Recent sessions show some dips. Consider reviewing..." |
| 1 declining | "One area has dipped slightly. This is normal..." |
| All stable | "Solid consistency over N sessions..." |

---

## Pipeline Integration

### Step 4.12 Extension

After computing player baseline, the narrative is generated:

```python
# Compute player baseline
player_baseline = compute_player_baseline(historical_sessions, min_sessions=3)

# Generate progress narrative (uses same historical data)
progress_narrative = generate_progress_narrative(
    historical_sessions=historical_sessions,
    num_sessions=5,
    min_sessions=3
)
```

---

## Report Integration

The Progress Narrative section appears in `report.md` after Personal Baseline:

```markdown
## 📈 Progress & Coach Summary

### Progress Summary (last 5 sessions)

Great progress! Your technique is improving (+7.0%) and readiness is 
climbing (+6.8%).

### Trend Details

**📈 Technique**: Improving (from 71.0% to 76.0%, +7.0%)
**📈 Readiness**: Improving (from 71.7/100 to 76.6/100, +6.8%)

### 🎓 Coach's Take

You're building momentum across the board. Keep up the consistent work 
and trust the process.

### How to Interpret Trends

**Improving**: Recent sessions show upward trend. Keep doing what you're doing!
**Stable**: Consistent performance across sessions. Consistency is valuable.
**Declining**: Recent sessions show downward trend. Review fundamentals.
```

---

## Graceful Degradation

### Insufficient Historical Data

**Scenario**: Fewer than 3 sessions available

**Behavior**:
- `has_narrative` = False
- Reason provided
- Report section skipped
- No errors

### Missing Metric Data

**Scenario**: Some sessions lack technique or readiness scores

**Behavior**:
- Generate trends only for metrics with sufficient data
- If technique has 5 sessions but readiness has 2: only technique trend
- Narrative adapts automatically

### First 1-2 Sessions

**Behavior**:
- Progress narrative section does not appear
- No errors or warnings
- System operates normally

---

## Narrative Examples

### Scenario 1: Both Improving
```
Great progress! Your technique is improving (+7.0%) and readiness is 
climbing (+6.8%).

Coach's Take: You're building momentum across the board. Keep up the 
consistent work and trust the process.
```

### Scenario 2: Mixed (One Improving, One Declining)
```
Great progress! Your technique is improving (+7.0%). Worth noting: 
readiness has dropped (-6.5%). This could be normal variation or may 
need attention.

Coach's Take: One area has dipped slightly. This is normal - use it 
as feedback to refine your approach.
```

### Scenario 3: Both Stable
```
Technique is holding steady around 75.5%. Readiness is consistent 
around 75.0/100.

Coach's Take: Solid consistency over 5 sessions. Consistency is the 
foundation of improvement.
```

### Scenario 4: Both Declining
```
Worth noting: technique has dipped (-8.2%) and readiness has dropped 
(-7.5%). This could be normal variation or may need attention.

Coach's Take: Recent sessions show some dips. Consider reviewing 
fundamentals, checking for fatigue, or adjusting training load.
```

---

## Conservative Design Principles

### 1. **Supportive Language**
- Positive trends highlighted first
- Concerns presented gently ("worth noting")
- No harsh language or absolutes

### 2. **No Predictions**
- ❌ "You will improve"
- ✅ "Your technique is improving"
- Describes what IS, not what WILL BE

### 3. **Context Provided**
- "This could be normal variation"
- "Use as feedback, not forecast"
- Acknowledges uncertainty

### 4. **Conservative Thresholds**
- ±5% threshold avoids false alarms
- Short-term noise filtered out
- Only significant trends reported

### 5. **Graceful Degradation**
- Works with partial data
- Never crashes or errors
- Adapts narrative to available data

---

## Confidence Scoring

Trend confidence is assessed based on:

| Confidence | Criteria |
|------------|----------|
| **High** | ≥5 sessions AND low variance (CV < 0.15) |
| **Medium** | ≥4 sessions OR moderate variance (CV < 0.25) |
| **Low** | <4 sessions OR high variance (CV ≥ 0.25) |

**Note**: Confidence affects internal assessment but is not currently shown in report (could be future enhancement).

---

## Limitations & Important Notes

### What Narratives ARE
✅ Interpretive summaries of recent trends  
✅ Coach-style feedback  
✅ Pattern recognition from history  
✅ Contextual guidance

### What Narratives ARE NOT
❌ Predictive models  
❌ Performance guarantees  
❌ Medical or injury assessments  
❌ Absolute truth (trends can reverse)

### Technical Constraints

**Time Window**:
- Default: Last 5 sessions
- Minimum: 3 sessions required
- Does not analyze beyond recent window

**Metrics Analyzed**:
- Currently: Technique and readiness only
- Future: Could expand to movement, fatigue, etc.

**Statistical Simplicity**:
- Uses simple earlier/recent split
- No regression analysis or time-series modeling
- Conservative by design

---

## Testing

Comprehensive test suite validates:

1. ✅ Trend detection - improving
2. ✅ Trend detection - declining
3. ✅ Trend detection - stable
4. ✅ Insufficient data (graceful degradation)
5. ✅ Narrative with positive trends
6. ✅ Narrative with mixed trends
7. ✅ Narrative with stable performance
8. ✅ Insufficient sessions for narrative
9. ✅ Coach's take variations
10. ✅ Narrative with missing data

Run tests:
```bash
python test_progress_narrative.py
```

---

## Future Enhancements (Not in Phase 5.2)

Potential directions:

- **More Metrics**: Expand beyond technique/readiness
- **Longer Trends**: Analyze 10+ sessions for long-term patterns
- **Trend Strength**: Show confidence in report
- **Visual Trends**: Add simple ASCII charts
- **Personalized Thresholds**: Adjust ±5% based on athlete variance
- **Seasonal Patterns**: Detect training cycles

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────┐
│       Historical Sessions (from Phase 5.1)          │
│  • Session 1: technique=70, readiness=72           │
│  • Session 2: technique=72, readiness=74           │
│  • Session 3: technique=74, readiness=76           │
│  • ...                                              │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│              detect_trend()                         │
│  For each metric: classify as improving/stable/    │
│  declining using ±5% threshold                      │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│          generate_progress_narrative()              │
│  • Extract trends                                   │
│  • Build human-readable summary                     │
│  • Generate coach's take                            │
└─────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────┐
│       Report Section Added                          │
│  "📈 Progress & Coach Summary"                      │
└─────────────────────────────────────────────────────┘
```

---

## Summary

Progress Narratives & Coach Summaries transform Coach AI from a **data provider** to a **coaching companion**. Instead of interpreting trends yourself, you get coach-style feedback that:

1. **Encourages**: Highlights progress first
2. **Guides**: Points out areas needing attention
3. **Contextualizes**: Explains what trends mean
4. **Motivates**: Uses supportive language

This interpretive layer makes Coach AI more **human-friendly** and **actionable** without adding new measurements or complexity. It simply communicates what's already there in a way that resonates with athletes.

