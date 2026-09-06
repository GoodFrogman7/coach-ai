# Stroke Abstraction Layer

## Overview

The **Stroke Abstraction Layer** is a foundational intelligence system that enables Coach AI to analyze multiple tennis strokes with stroke-specific biomechanical context.

**Status**: ✅ Implemented (Phase 2 Foundation)  
**Backward Compatibility**: ✅ 100% preserved (default = backhand)

---

## Why This Exists

Different tennis strokes have fundamentally different biomechanical requirements:

| Stroke | Hip Rotation | Elbow Extension | Contact Height | Body Posture |
|--------|--------------|-----------------|----------------|--------------|
| **Backhand** | Moderate (150-220°) | Compact (90-140°) | Waist level | Upright |
| **Forehand** | Large (180-270°) | Extended (100-160°) | Waist-shoulder | Forward lean |
| **Serve** | Maximum (200-300°) | Full (140-180°) | Above head | Backward arch |
| **Volley** | Minimal (30-90°) | Compact (90-130°) | Variable | Forward lean |
| **Overhead** | Large (150-250°) | Extended (130-180°) | Above head | Backward arch |

**Problem**: Using universal thresholds would misclassify stroke-specific technique.

**Solution**: Stroke-aware thresholds that understand biomechanical intent.

---

## Architecture

### Stroke Profile Definition

Each stroke profile contains:

```python
STROKE_PROFILES = {
    'stroke_name': {
        'name': 'Display Name',
        'description': 'Brief description',
        'biomechanical_intent': {
            'metric_name': {
                'expected_range': (min, max),  # degrees or normalized units
                'rationale': 'Why this range is optimal'
            },
            # ... more metrics
        },
        'phase_emphasis': {
            'preparation': 0.15,
            'load': 0.25,
            'contact': 0.35,
            'follow_through': 0.25
        }
    }
}
```

### Supported Strokes

1. **Backhand** (default)
   - Two-handed backhand
   - Baseline groundstroke
   - Focus: Contact phase (35%)

2. **Forehand**
   - Single-handed dominant-side stroke
   - Greater rotation and extension
   - Focus: Load (30%) + Contact (35%)

3. **Serve**
   - First or second serve
   - Maximum power generation
   - Focus: Contact (40%) + Preparation (20%)

4. **Volley**
   - Net volley (forehand or backhand)
   - Compact, reactive motion
   - Focus: Contact (45%) + Preparation (30%)

5. **Overhead**
   - Overhead smash
   - Serve-like mechanics
   - Focus: Contact (40%)

---

## API Reference

### `get_stroke_aware_threshold(metric_name, stroke_type='backhand', threshold_type='expected_range')`

Get stroke-specific biomechanical thresholds for intelligent metric evaluation.

**Parameters**:
- `metric_name` (str): Name of biomechanical metric (e.g., 'hip_rotation', 'elbow_angle')
- `stroke_type` (str, optional): Type of stroke. Default: 'backhand'
- `threshold_type` (str, optional): 'expected_range' or 'rationale'. Default: 'expected_range'

**Returns**:
- `tuple` or `str` or `None`: Threshold value (type depends on threshold_type)

**Backward Compatibility**:
- Default `stroke_type='backhand'` preserves all existing behavior
- Falls back to backhand if stroke not found
- Returns `None` if metric not in profile (caller handles fallback)

**Examples**:

```python
# Get forehand hip rotation range
>>> get_stroke_aware_threshold('hip_rotation', 'forehand')
(180, 270)  # Larger than backhand (150, 220)

# Get backhand elbow range (default)
>>> get_stroke_aware_threshold('elbow_angle')
(90, 140)

# Get serve knee flexion rationale
>>> get_stroke_aware_threshold('knee_flexion', 'serve', 'rationale')
'Leg drive from trophy position'

# Unknown stroke falls back to backhand
>>> get_stroke_aware_threshold('hip_rotation', 'unknown_stroke')
(150, 220)  # Backhand default
```

---

### `get_stroke_phase_weights(stroke_type='backhand')`

Get stroke-specific phase importance weights.

**Parameters**:
- `stroke_type` (str, optional): Type of stroke. Default: 'backhand'

**Returns**:
- `dict`: Phase weights (sum = 1.0)

**Backward Compatibility**:
- Default `stroke_type='backhand'` preserves existing phase weights
- Falls back to backhand if stroke not found

**Examples**:

```python
# Get backhand phase weights (default)
>>> get_stroke_phase_weights()
{'preparation': 0.15, 'load': 0.25, 'contact': 0.35, 'follow_through': 0.25}

# Get serve phase weights (different emphasis)
>>> get_stroke_phase_weights('serve')
{'preparation': 0.20, 'load': 0.20, 'contact': 0.40, 'follow_through': 0.20}

# Get volley phase weights (preparation + contact critical)
>>> get_stroke_phase_weights('volley')
{'preparation': 0.30, 'load': 0.10, 'contact': 0.45, 'follow_through': 0.15}
```

---

## Integration Points (Future)

The Stroke Abstraction Layer is designed for seamless integration with existing systems:

### 1. Similarity Scoring
```python
# Current (stroke-agnostic)
deviation = abs(user_metric - ref_metric)
score = max(0, 100 - deviation)

# Future (stroke-aware)
expected_range = get_stroke_aware_threshold(metric_name, stroke_type)
deviation = compute_stroke_aware_deviation(user_metric, expected_range)
score = max(0, 100 - deviation)
```

### 2. Coaching Cues
```python
# Current (generic thresholds)
if abs(user_hip - ref_hip) > 20:
    cues.append("Increase hip rotation")

# Future (stroke-aware)
expected_min, expected_max = get_stroke_aware_threshold('hip_rotation', stroke_type)
if user_hip < expected_min:
    rationale = get_stroke_aware_threshold('hip_rotation', stroke_type, 'rationale')
    cues.append(f"Increase hip rotation. {rationale}")
```

### 3. Drill Selection
```python
# Current (stroke-agnostic drills)
if issue == 'hip_rotation_low':
    recommend_drill('medicine_ball_rotations')

# Future (stroke-specific drills)
if issue == 'hip_rotation_low':
    if stroke_type == 'forehand':
        recommend_drill('open_stance_forehand_drill')
    elif stroke_type == 'serve':
        recommend_drill('trophy_position_holds')
```

### 4. Progress Tracking
```python
# Track progress per stroke type
progress_history[session_id][stroke_type] = metrics
```

---

## Implementation Notes

### Location
- **File**: `vision/compare.py`
- **Section**: Lines 39-320 (after imports, before Session Management)

### Design Principles

1. **Additive Only**: No changes to existing analysis, scoring, or drill logic
2. **Backward Compatible**: Default `stroke_type='backhand'` preserves 100% of existing behavior
3. **Graceful Fallback**: Unknown strokes default to backhand (never crash)
4. **Clear Documentation**: Inline comments explain rationale and future vision
5. **Type Safety**: Clear parameter types and return values

### Testing

**Validation**: ✅ Verified that existing backhand analysis produces identical results

```bash
# Before implementation: Overall score = 62.4, Phase-weighted = 59.9
# After implementation:  Overall score = 62.4, Phase-weighted = 59.9
# Result: PASS (100% backward compatibility)
```

---

## Future Vision

The Stroke Abstraction Layer enables:

### Phase 3: Multi-Stroke Video Analysis
- Automatic stroke detection from video
- Stroke-specific segmentation and analysis
- Cross-stroke comparison reports

### Phase 4: Full Tennis Game Intelligence
- Rally analysis (forehand/backhand patterns)
- Serve + return analysis
- Net play evaluation (volley technique)
- Overhead smash assessment

### Phase 5: Adaptive Coaching Per Stroke
- "Your forehand is strong, focus on backhand consistency"
- "Serve contact point needs adjustment"
- "Volley preparation (split-step) timing is improving"

### Phase 6: Stroke-Specific Drill Prescription
- Forehand-specific drills for forehand issues
- Serve-specific drills for serve mechanics
- Cross-stroke drills for general athleticism

---

## Usage Guidelines

### Current Usage (Explicit)

You can explicitly query stroke-specific thresholds:

```python
# Compare backhand vs forehand hip rotation requirements
backhand_range = get_stroke_aware_threshold('hip_rotation', 'backhand')
forehand_range = get_stroke_aware_threshold('hip_rotation', 'forehand')

print(f"Backhand hip rotation: {backhand_range}")  # (150, 220)
print(f"Forehand hip rotation: {forehand_range}")  # (180, 270)
```

### Future Usage (Integrated)

Once integrated into the pipeline:

```python
# Pipeline will accept stroke_type parameter
python vision/compare.py --stroke-type forehand

# Or automatic detection
python vision/compare.py --auto-detect-stroke
```

---

## Constraints

### What This Changes
- ✅ Adds new helper functions
- ✅ Defines stroke profile data structure
- ✅ Provides API for stroke-aware thresholds

### What This Does NOT Change
- ❌ Existing metric computation
- ❌ Existing scoring logic
- ❌ Existing coaching cue generation
- ❌ Existing drill recommendations
- ❌ Existing report output
- ❌ Default behavior (still backhand-only)

---

## Next Steps

### Immediate (Phase 2b)
- [x] Implement Stroke Abstraction Layer
- [ ] Add unit tests for stroke profile lookups
- [ ] Add validation for profile completeness

### Short-term (Phase 3)
- [ ] Integrate stroke awareness into similarity scoring
- [ ] Add stroke-specific coaching cue templates
- [ ] Update drill knowledge base with stroke tags

### Long-term (Phase 4+)
- [ ] Add stroke detection from video
- [ ] Implement multi-stroke session analysis
- [ ] Build cross-stroke comparison reports
- [ ] Add stroke-specific Streamlit visualizations

---

## Summary

The Stroke Abstraction Layer is a **foundational intelligence system** that:

1. ✅ Defines biomechanical profiles for 5 tennis strokes
2. ✅ Provides stroke-aware threshold lookup APIs
3. ✅ Maintains 100% backward compatibility
4. ✅ Enables future multi-stroke intelligence
5. ✅ Requires zero changes to existing pipeline

**Impact**: Unlocks the path to full tennis game analysis while preserving system stability.

**Philosophy**: Build the foundation first, integrate incrementally, never break existing behavior.

