# Training Load & Session Planning Intelligence (Phase 4.2)

## Overview

Training Load & Session Planning Intelligence is a **synthesis layer** that converts match readiness and fatigue signals into actionable training guidance. It helps coaches and athletes make informed decisions about daily training load, session type, and intensity.

**IMPORTANT**: This is general training guidance, **NOT medical advice** or personalized workout prescription. Always consult with qualified coaches and medical professionals before adjusting your training load.

---

## What is Training Load Recommendation?

Training Load Recommendation answers three key questions:

1. **What type of session should I do today?**
   - Recovery, Technique, Movement, Conditioning, Full, or Match-sim

2. **What intensity is appropriate?**
   - Low, Moderate, or High

3. **What should I focus on or avoid?**
   - Specific focus areas and avoid areas based on current state

---

## Input Signals

The system synthesizes multiple intelligence layers:

| Input | Source | Weight in Decision |
|-------|--------|-------------------|
| **Match Readiness** | Phase 4.1 | Primary driver (score & level) |
| **Fatigue Analysis** | Phase 2.3 | Primary driver (overrides readiness) |
| **Signal Quality** | Phase 3.2 | Gating factor (low quality → low intensity) |
| **Adaptive Coaching** | Phase 2.2 | Secondary (adds specific focus areas) |

---

## Output Structure

The `compute_training_load_recommendation()` function returns:

```python
{
    'session_type': str,  # Recovery | Technique | Movement | Conditioning | Full | Match-sim
    'intensity': str,     # Low | Moderate | High
    'focus_areas': list[str],
    'avoid_areas': list[str],
    'rationale': str,     # Human-readable explanation
    'confidence': float,  # 0-1
    'warnings': list[str]
}
```

---

## Decision Logic

### Priority Order

1. **Signal Trust** (highest priority)
   - Low trust (< 0.6) → Low intensity + re-record recommendation
   - Overrides all other factors

2. **Fatigue Level** (second priority)
   - High fatigue (> 60) → Recovery or light technique
   - Overrides readiness score

3. **Readiness Score** (primary factor when fatigue is manageable)
   - Determines session type and intensity

### Decision Matrix

| Condition | Session Type | Intensity | Key Guidance |
|-----------|-------------|-----------|--------------|
| **Signal trust < 0.6** | Technique | Low | Re-record video with better quality |
| **Fatigue > 60** | Recovery | Low | Prioritize rest, avoid high-intensity |
| **Readiness < 55** | Technique | Low | Build fundamentals, avoid competition |
| **Readiness 55-69** | Technique | Moderate | Technical corrections, consistency drills |
| **Readiness 70-84 + Low fatigue** | Full | High | Substantial load, conditioning, point play |
| **Readiness 70-84 + Moderate fatigue** | Conditioning | Moderate | Maintain technique, avoid max-intensity |
| **Readiness ≥ 85** | Match-sim | High | Peak form, ready for competition prep |

---

## Session Type Guide

### Recovery
- **Purpose**: Active recovery, prevent overtraining
- **Activities**: Mobility, light movement, stretching
- **Intensity**: Low
- **When**: High fatigue (> 60), very low readiness

### Technique
- **Purpose**: Form and mechanics refinement
- **Activities**: Slow-motion practice, shadow swings, consistency drills
- **Intensity**: Low to Moderate
- **When**: Fair readiness, low readiness, post-recovery

### Movement
- **Purpose**: Footwork, balance, agility development
- **Activities**: Ladder drills, cone work, balance exercises
- **Intensity**: Moderate
- **When**: Good technique but movement concerns

### Conditioning
- **Purpose**: Fitness development with technique maintenance
- **Activities**: Interval training, endurance work, moderate rallies
- **Intensity**: Moderate
- **When**: Good readiness but moderate fatigue

### Full
- **Purpose**: Complete training session
- **Activities**: Technique + conditioning + point play
- **Intensity**: High
- **When**: Good readiness (70-84) with low fatigue

### Match-sim
- **Purpose**: Competition preparation
- **Activities**: Match simulation, tactical scenarios, mental toughness
- **Intensity**: High
- **When**: Excellent readiness (≥ 85) with low fatigue

---

## Example Usage

### In the Pipeline

```python
# Compute training load recommendation (synthesis layer)
training_load = compute_training_load_recommendation(
    match_readiness=match_readiness,   # From Phase 4.1
    fatigue_analysis=fatigue_data,     # From Phase 2.3 (optional)
    signal_quality=signal_quality_data,# From Phase 3.2 (optional)
    adaptive_coaching=adaptive_coaching_data  # From Phase 2.2 (optional)
)

# Pass to report generation
report = generate_report(
    ...,
    training_load=training_load
)
```

### Standalone

```python
from vision.compare import compute_training_load_recommendation

training_load = compute_training_load_recommendation(
    match_readiness={
        'readiness_score': 78.0,
        'readiness_level': 'Good',
        'confidence': 0.88
    },
    fatigue_analysis={
        'fatigue_score': 25.0,
        'affected_metrics': []
    },
    signal_quality={
        'quality_score': 0.85
    }
)

print(f"Session: {training_load['session_type']} ({training_load['intensity']} intensity)")
print(f"Rationale: {training_load['rationale']}")
```

---

## Report Integration

The Training Load section appears in `report.md` after Match Readiness:

```markdown
## 🎯 Training Load & Session Planning

### Recommended Session: Full

**Intensity**: 🔴 High
**Confidence**: 88%

### Why This Recommendation?

Good readiness (78.0/100). Ready for substantial training load. 
Can include conditioning and point play.

### 🎯 Focus Areas for This Session

- Technical refinement under pressure
- Conditioning drills
- Point play

### Session Type Guide

**Full**: Complete training session combining technique, movement, and conditioning.
```

---

## Graceful Degradation

The system intelligently handles missing data:

### All Components Available
- Full decision logic applied
- High confidence (0.85-0.95)

### Missing Fatigue Analysis
- Relies on readiness score alone
- Confidence reduced by 10%

### Missing Signal Quality
- Assumes good quality (0.8)
- Confidence reduced by 5%

### Only Match Readiness Available
- Still provides valid recommendation
- Confidence reduced to 0.3-0.5

---

## Warning Flags

The system generates warnings for critical conditions:

| Condition | Warning |
|-----------|---------|
| Signal quality < 0.6 | "Low measurement quality detected - consider re-recording with better lighting/angles" |
| Fatigue score > 75 | "Very high fatigue detected - prioritize rest and recovery" |
| Fatigue score 40-60 + Training load | "Moderate fatigue present - monitor closely and reduce volume if needed" |

---

## Key Design Principles

### 1. Safety First
- High fatigue always triggers recovery recommendation
- Low signal quality → low intensity
- Warnings for extreme conditions

### 2. Explainability
- Every recommendation includes human-readable rationale
- Clear focus areas and avoid areas
- Transparent decision logic

### 3. Graceful Degradation
- Never fails due to missing data
- Adjusts confidence appropriately
- Provides conservative defaults

### 4. No Medical Claims
- Positioned as "training guidance"
- Not injury prevention or medical advice
- Clear disclaimers in report

### 5. Backward Compatibility
- Fully optional feature
- Report works without it
- No changes to existing logic

---

## Confidence Scoring

Confidence reflects data availability:

**Base Confidence**: Inherited from match readiness (0.3-1.0)

**Adjustments**:
- Missing match readiness: × 0.7
- Missing fatigue analysis: × 0.9
- Missing signal quality: × 0.95

**Example**:
- Match readiness confidence = 0.95
- Fatigue missing: 0.95 × 0.9 = 0.855
- Final confidence: 86%

---

## Testing

Comprehensive test suite validates:

1. ✅ Excellent readiness → Match simulation
2. ✅ Good readiness + low fatigue → Full training
3. ✅ Fair readiness → Technique focus
4. ✅ High fatigue → Recovery session
5. ✅ Low readiness → Light technique
6. ✅ Low signal quality → Re-record recommendation
7. ✅ Graceful degradation with minimal data
8. ✅ Good readiness + moderate fatigue → Conditioning

Run tests:
```bash
python test_training_load.py
```

---

## Real-World Example Scenarios

### Scenario 1: Peak Performance Day
- **Readiness**: 92/100 (Excellent)
- **Fatigue**: 15/100 (Very low)
- **Recommendation**: Match-sim at High intensity
- **Focus**: Competition scenarios, mental toughness

### Scenario 2: Post-Tournament Fatigue
- **Readiness**: 72/100 (Good)
- **Fatigue**: 80/100 (Very high)
- **Recommendation**: Recovery at Low intensity
- **Focus**: Active recovery, mobility
- **Warning**: "Very high fatigue detected"

### Scenario 3: Building Back After Break
- **Readiness**: 48/100 (Poor)
- **Fatigue**: 20/100 (Low)
- **Recommendation**: Technique at Low intensity
- **Focus**: Fundamental refinement, slow-motion practice
- **Avoid**: Match simulation, high-speed rallies

### Scenario 4: Mid-Training Block
- **Readiness**: 77/100 (Good)
- **Fatigue**: 45/100 (Moderate)
- **Recommendation**: Conditioning at Moderate intensity
- **Focus**: Technique maintenance, movement conditioning
- **Avoid**: Max-intensity rallies

---

## Limitations

### What Training Load IS
✅ General training guidance based on biomechanical state  
✅ Session type and intensity recommendations  
✅ Focus areas and avoid areas

### What Training Load IS NOT
❌ Medical advice or injury prevention  
❌ Personalized workout prescription  
❌ Scheduling or periodization system  
❌ Volume/duration prescriptions (sets, reps, minutes)

### Technical Constraints
- Requires at least match readiness (other components optional)
- No historical periodization (single-session recommendations)
- No calendar integration
- No workout volume prescriptions

---

## Future Enhancements (Not in Phase 4.2)

Potential future directions:

- **Adaptive weighting** based on training phase (base/build/peak/taper)
- **Historical load tracking** to prevent spikes
- **Multi-day planning** with recovery cycles
- **Integration with drill difficulty** for automatic load adjustment
- **Personalization** based on athlete profile

---

## Summary

Training Load & Session Planning Intelligence provides **actionable training guidance** that converts complex biomechanical signals into simple daily recommendations. It is designed as a **read-only synthesis layer** that never alters existing analysis while providing valuable decision-making support for coaches and athletes.

The system prioritizes safety (fatigue → recovery), provides clear rationale, and gracefully degrades with missing data. It is a foundational capability for intelligent, adaptive training systems.

