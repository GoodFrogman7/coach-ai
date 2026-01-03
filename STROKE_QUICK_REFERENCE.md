# Stroke Abstraction Layer - Quick Reference

## 🚀 Quick Start

### Import Functions
```python
from vision.compare import (
    get_stroke_aware_threshold,
    get_stroke_phase_weights,
    STROKE_PROFILES
)
```

### Get Stroke-Specific Thresholds
```python
# Get hip rotation range for forehand
forehand_hip = get_stroke_aware_threshold('hip_rotation', 'forehand')
# Returns: (180, 270)

# Get elbow angle range for serve
serve_elbow = get_stroke_aware_threshold('elbow_angle', 'serve')
# Returns: (140, 180)

# Get rationale for backhand hip rotation
rationale = get_stroke_aware_threshold('hip_rotation', 'backhand', 'rationale')
# Returns: "Hip coiling provides power generation"
```

### Get Phase Weights
```python
# Get phase weights for serve
serve_weights = get_stroke_phase_weights('serve')
# Returns: {'preparation': 0.20, 'load': 0.20, 'contact': 0.40, 'follow_through': 0.20}
```

---

## 🎾 Supported Strokes

| Stroke | Code | Description |
|--------|------|-------------|
| Backhand | `'backhand'` | Two-handed baseline backhand (default) |
| Forehand | `'forehand'` | Dominant-side groundstroke |
| Serve | `'serve'` | First or second serve |
| Volley | `'volley'` | Net volley |
| Overhead | `'overhead'` | Overhead smash |

---

## 📊 Metric Ranges by Stroke

### Hip Rotation
```
Backhand:  150-220°  (moderate, controlled)
Forehand:  180-270°  (larger for power)
Serve:     200-300°  (maximum rotation)
Volley:     30-90°   (minimal, compact)
Overhead:  150-250°  (serve-like)
```

### Elbow Angle
```
Backhand:   90-140°  (compact arm structure)
Forehand:  100-160°  (extended lever arm)
Serve:     140-180°  (near full extension)
Volley:     90-130°  (compact punching motion)
Overhead:  130-180°  (extended reach)
```

### Knee Flexion
```
Backhand:  150-170°  (athletic stance)
Forehand:  150-175°  (similar to backhand)
Serve:     120-160°  (deeper bend for leg drive)
Volley:    140-170°  (ready position)
Overhead:  140-175°  (balanced stance)
```

### Spine Lean
```
Backhand:   -10 to 15°  (upright to slightly forward)
Forehand:    -5 to 20°  (more forward lean)
Serve:      -20 to 10°  (backward arch in trophy)
Volley:       0 to 20°  (forward aggressive posture)
Overhead:   -15 to 5°   (backward lean for upward contact)
```

---

## 🎯 Phase Weights by Stroke

| Stroke | Preparation | Load | Contact | Follow-through |
|--------|-------------|------|---------|----------------|
| Backhand | 15% | 25% | **35%** | 25% |
| Forehand | 15% | 30% | **35%** | 20% |
| Serve | 20% | 20% | **40%** | 20% |
| Volley | 30% | 10% | **45%** | 15% |
| Overhead | 25% | 20% | **40%** | 15% |

---

## 🧪 Testing

### Run Test Suite
```bash
python test_stroke_abstraction.py
```

### Run Interactive Demo
```bash
python demo_stroke_abstraction.py
```

### Test in Python
```python
# Compare backhand vs forehand requirements
backhand_hip = get_stroke_aware_threshold('hip_rotation', 'backhand')
forehand_hip = get_stroke_aware_threshold('hip_rotation', 'forehand')

print(f"Backhand: {backhand_hip}")  # (150, 220)
print(f"Forehand: {forehand_hip}")  # (180, 270)
```

---

## 📝 Usage Examples

### Example 1: Evaluate Hip Rotation
```python
player_hip_rotation = 165  # degrees

# Check against backhand
backhand_range = get_stroke_aware_threshold('hip_rotation', 'backhand')
if backhand_range[0] <= player_hip_rotation <= backhand_range[1]:
    print("✅ Backhand technique is good")
else:
    print("⚠️ Backhand needs adjustment")

# Check against forehand
forehand_range = get_stroke_aware_threshold('hip_rotation', 'forehand')
if player_hip_rotation < forehand_range[0]:
    print(f"⚠️ Forehand needs +{forehand_range[0] - player_hip_rotation}° rotation")
```

### Example 2: Generate Coaching Cue
```python
def generate_stroke_cue(metric_name, user_value, stroke_type):
    expected_range = get_stroke_aware_threshold(metric_name, stroke_type)
    
    if user_value < expected_range[0]:
        rationale = get_stroke_aware_threshold(metric_name, stroke_type, 'rationale')
        deficit = expected_range[0] - user_value
        return f"Increase {metric_name} by ~{deficit}°. {rationale}"
    elif user_value > expected_range[1]:
        excess = user_value - expected_range[1]
        return f"Reduce {metric_name} by ~{excess}°. More compact motion needed"
    else:
        return "Technique looks good, maintain current form"

# Usage
cue = generate_stroke_cue('hip_rotation', 165, 'forehand')
print(cue)  # "Increase hip_rotation by ~15°. Greater hip rotation for power..."
```

### Example 3: Compare All Strokes
```python
player_hip = 165  # degrees

print("Hip Rotation Analysis (165°):\n")
for stroke in ['backhand', 'forehand', 'serve', 'volley', 'overhead']:
    range_min, range_max = get_stroke_aware_threshold('hip_rotation', stroke)
    
    if range_min <= player_hip <= range_max:
        status = "✅ GOOD"
    elif player_hip < range_min:
        status = f"⚠️ LOW (-{range_min - player_hip}°)"
    else:
        status = f"⚠️ HIGH (+{player_hip - range_max}°)"
    
    print(f"{stroke.capitalize():10} [{range_min:3d}-{range_max:3d}°] {status}")
```

---

## ⚠️ Important Notes

### Backward Compatibility
- **Default stroke type is `'backhand'`** - preserves all existing behavior
- Unknown stroke types automatically fall back to backhand
- No changes required to existing code

### Return Values
- `get_stroke_aware_threshold()` returns `None` if metric not found
- Always check for `None` before using the result
- Fallback to generic thresholds if needed

### Metric Name Flexibility
These all work for hip rotation:
- `'hip_rotation'`
- `'hip'`
- `'hip_angle'`

These all work for elbow:
- `'elbow_angle'`
- `'elbow'`
- `'left_elbow'`
- `'right_elbow'`

---

## 📚 Documentation

- **Full Technical Docs**: `STROKE_ABSTRACTION.md`
- **Implementation Summary**: `STROKE_ABSTRACTION_SUMMARY.md`
- **Quick Reference**: This file
- **Test Suite**: `test_stroke_abstraction.py`
- **Interactive Demo**: `demo_stroke_abstraction.py`

---

## 🔧 Troubleshooting

### Issue: Function not found
```python
# Wrong
from compare import get_stroke_aware_threshold  # ❌

# Correct
from vision.compare import get_stroke_aware_threshold  # ✅
```

### Issue: Metric returns None
```python
# Check if metric is supported
threshold = get_stroke_aware_threshold('unknown_metric', 'backhand')
if threshold is None:
    # Use fallback or skip
    print("Metric not in profile")
```

### Issue: Unknown stroke type
```python
# Automatically falls back to backhand
threshold = get_stroke_aware_threshold('hip_rotation', 'unknown_stroke')
# Returns backhand threshold: (150, 220)
```

---

## 🚀 Next Steps

1. ✅ **Implemented**: Stroke abstraction layer
2. 🔄 **Next**: Integrate into similarity scoring
3. 📋 **Then**: Add stroke-specific coaching cues
4. 🎯 **Future**: Multi-stroke video analysis

---

## 💡 Key Insights

1. **Same metric, different context**: 165° hip rotation is good for backhand, low for forehand
2. **Phase emphasis varies**: Serves emphasize contact (40%), volleys emphasize contact + prep (45% + 30%)
3. **Stroke-aware coaching**: More accurate, relevant, and actionable feedback

---

## ✅ Validation

```bash
# Run pipeline (should produce identical results)
python vision/compare.py

# Run tests (all should pass)
python test_stroke_abstraction.py

# Run demo (see intelligent coaching in action)
python demo_stroke_abstraction.py
```

---

*Quick Reference Guide - December 27, 2025*

