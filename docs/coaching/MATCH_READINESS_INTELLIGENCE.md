# Match Readiness Intelligence (Phase 4.1)

## Overview

Match Readiness Intelligence is a **synthesis layer** that combines existing intelligence systems into a single, explainable readiness signal. It helps coaches and athletes make informed decisions about competition timing and training intensity adjustments.

**IMPORTANT**: Match readiness is **NOT** a performance prediction or injury risk assessment. It is a training and competition guidance signal based on observable biomechanical state.

---

## What is Match Readiness?

Match readiness synthesizes four key dimensions:

1. **Technique Quality** (40% weight)
   - Overall stroke biomechanics similarity to reference
   - Phase-weighted scoring
   - Derived from existing technique analysis

2. **Movement Quality** (30% weight)
   - Split-step timing and quality
   - Recovery time
   - Balance stability
   - Derived from CV-based movement extraction

3. **Energy Level** (20% weight)
   - Inverse of fatigue score
   - Low fatigue = high readiness
   - Derived from rally & fatigue intelligence

4. **Signal Trust** (10% weight)
   - Measurement reliability
   - Signal quality assessment
   - Derived from trust & calibration layer

---

## Output Structure

The `compute_match_readiness()` function returns:

```python
{
    'readiness_score': float (0-100),
    'readiness_level': str ('Poor' | 'Fair' | 'Good' | 'Excellent'),
    'confidence': float (0-1),
    'contributors': {
        'technique': {
            'raw_score': float (0-100),
            'weight': float (0-1),
            'weighted_contribution': float (0-100)
        },
        # ... same structure for movement, fatigue, trust
    },
    'explanation': str (human-readable summary),
    'flags': list[str] (warning signals)
}
```

---

## Readiness Levels

| Level | Score Range | Interpretation |
|-------|------------|----------------|
| **Excellent** | 85-100 | Peak form. Ready for competition or high-intensity training. |
| **Good** | 70-84 | Solid condition. Can compete or train hard, but monitor for any warning signs. |
| **Fair** | 55-69 | Adequate for moderate training. Consider technical drills over high-intensity competition. |
| **Poor** | 0-54 | Focus on recovery, technique refinement, or addressing specific issues before competing. |

---

## Graceful Degradation

The system intelligently handles missing data:

### All Components Available
- Uses base weights: technique (40%), movement (30%), fatigue (20%), trust (10%)
- High confidence (0.9-1.0)

### Movement Data Missing
- Redistributes movement weight to technique (70%) and fatigue (30%)
- Medium confidence (0.6-0.8)

### Fatigue Data Missing
- Redistributes fatigue weight to technique and movement
- Slightly reduced confidence

### Trust Data Missing
- Redistributes trust weight proportionally
- Minimal confidence impact

### Only Technique Available
- Technique weight = 100%
- Low confidence (0.3-0.5)
- Still provides actionable guidance

---

## Example Usage

### In the Pipeline

```python
# Compute match readiness (synthesis layer)
match_readiness = compute_match_readiness(
    technique_score=phase_weighted_score,  # From existing analysis
    movement_metrics=movement_data,        # From CV extraction (optional)
    fatigue_analysis=fatigue_data,         # From rally/fatigue layer (optional)
    signal_quality=signal_quality_data     # From trust layer (optional)
)

# Pass to report generation
report = generate_report(
    ...,
    match_readiness=match_readiness
)
```

### Standalone

```python
from vision.compare import compute_match_readiness

readiness = compute_match_readiness(
    technique_score=85.0,
    movement_metrics={
        'split_step_timing': {'split_step_quality': 'on-time', 'confidence': 0.9},
        'recovery_time': {'recovery_time_seconds': 1.2, 'confidence': 0.85},
        'balance_drift': {'stability_score': 82, 'confidence': 0.88}
    },
    fatigue_analysis={'fatigue_score': 18, 'affected_metrics': []},
    signal_quality={'quality_score': 0.92, 'issues': []}
)

print(f"Readiness: {readiness['readiness_level']} ({readiness['readiness_score']:.1f}/100)")
print(f"Explanation: {readiness['explanation']}")
```

---

## Report Integration

The Match Readiness section appears in `report.md` before the Final Thoughts:

```markdown
## 🎯 Match Readiness Assessment

### Overall Readiness: 🟢 Excellent

**Score**: 88.3/100 (Confidence: 95%)

**Summary**: Excellent readiness, driven by strong technique quality.

### Contributing Factors

- **🎾 Technique Quality**: 92.5/100 (weight: 40%) → contributes 37.0 points
- **👟 Movement Quality**: 85.2/100 (weight: 30%) → contributes 25.6 points
- **⚡ Energy Level**: 88.0/100 (weight: 20%) → contributes 17.6 points
- **📊 Signal Quality**: 92.0/100 (weight: 10%) → contributes 9.2 points

### What This Means For You

**Excellent Readiness (85-100)**: You're in peak form. Ready for competition or high-intensity training.

**Confidence Score**: Reflects data availability and measurement quality. Higher confidence = more reliable assessment.
```

---

## Warning Flags

The system generates human-readable flags when concerns are detected:

| Condition | Flag |
|-----------|------|
| Split-step quality = 'late' | "Split-step timing needs improvement" |
| Recovery time > 2.0s | "Slow recovery time detected" |
| Balance stability < 60% | "Balance instability detected" |
| Fatigue score > 60 | "Moderate to high fatigue detected" |
| ≥3 metrics affected by fatigue | "X metrics show fatigue patterns" |
| Signal quality < 60% | "Measurement quality below optimal" |

---

## Key Design Principles

### 1. Read-Only Synthesis
- Does NOT introduce new measurements
- Does NOT change existing analysis
- Only combines existing intelligence

### 2. Explainability First
- Every score includes human-readable explanation
- Contributors are clearly weighted and displayed
- Flags provide actionable warnings

### 3. Graceful Degradation
- Never fails due to missing data
- Automatically rebalances weights
- Confidence score reflects data availability

### 4. No Medical Claims
- Does NOT predict injury risk
- Does NOT assess physiological readiness
- Only reflects observable biomechanical state

### 5. Backward Compatibility
- Fully optional (report works without it)
- No changes to existing logic
- Additive integration only

---

## Confidence Scoring

Confidence is computed based on:

1. **Data Availability** (70% weight)
   - 4 components available = 1.0
   - 3 components available = 0.775
   - 2 components available = 0.55
   - 1 component available = 0.325

2. **Trust Modulation** (30% weight)
   - If signal trust < 0.7, confidence is multiplied by trust score
   - This ensures low-quality measurements reduce overall confidence

**Example**:
- 3 components available: base confidence = 0.775
- Signal trust = 0.5: final confidence = 0.775 × 0.5 = 0.388

---

## Testing

Comprehensive test suite validates:

1. ✅ Excellent readiness with all components strong
2. ✅ Fair readiness with multiple concerns
3. ✅ Poor readiness driven by high fatigue
4. ✅ Graceful degradation with minimal data
5. ✅ Weight rebalancing when data is missing
6. ✅ Confidence modulation by trust

Run tests:
```bash
python test_match_readiness.py
```

---

## Future Enhancements (Not in Phase 4.1)

Potential future directions:

- **Adaptive weighting** based on sport/context
- **Historical readiness tracking** across sessions
- **Competition-specific readiness** (e.g., match vs. practice)
- **Recovery recommendations** when readiness is low
- **Integration with drill recommendations** (suppress high-intensity drills when readiness is poor)

---

## Constraints and Limitations

### What Readiness IS
✅ A synthesis of observable biomechanical state  
✅ A training and competition guidance signal  
✅ An explainable, actionable metric  

### What Readiness IS NOT
❌ A performance prediction  
❌ An injury risk assessment  
❌ A physiological readiness measure  
❌ A replacement for coach judgment  

### Technical Constraints
- Requires at least technique score (other components optional)
- Confidence degrades with missing data
- Weights are fixed (not adaptive)
- No historical trend analysis (single-session only)

---

## Summary

Match Readiness Intelligence provides a **single, explainable readiness signal** that synthesizes technique, movement, fatigue, and trust into actionable guidance. It is designed as a **read-only synthesis layer** that never alters existing analysis while providing valuable decision-making support for coaches and athletes.

The system gracefully degrades with missing data, provides human-readable explanations, and maintains strict boundaries around what it claims to measure. It is a foundational capability for intelligent, adaptive coaching systems.

