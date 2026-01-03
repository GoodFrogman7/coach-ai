# Movement & Footwork Intelligence (Phase 2.2)

## Overview

The **Movement & Footwork Intelligence** layer extends Coach AI with stroke-agnostic movement analysis. While stroke mechanics focus on arm/body positioning during the swing, movement intelligence evaluates court positioning, footwork, balance, and recovery.

**Status**: ✅ Implemented (Phase 2.2)  
**Backward Compatibility**: ✅ 100% preserved (movement metrics are optional)

---

## Why Movement Matters for Tennis

### The Foundation Principle

**"Good feet, good shots"** - Tennis professionals universally recognize that movement is foundational to stroke execution.

### Key Insights

1. **Poor footwork → Inconsistent stroke mechanics**
   - Late positioning forces rushed strokes
   - Imbalanced setup compromises contact point
   - Poor recovery limits next-shot preparation

2. **Recovery speed → Rally control**
   - Fast recovery enables better court positioning
   - Quick repositioning creates offensive opportunities
   - Slow recovery puts player in defensive mode

3. **Balance → Power generation**
   - Stable base enables complete weight transfer
   - Balance drift wastes kinetic energy
   - Grounded contact maximizes racket head speed

4. **Split-step timing → Reaction time**
   - Proper split-step timing reduces first-step latency
   - Pre-loading muscles enables explosive movement
   - Timing consistency improves court coverage

---

## How It Complements Stroke Abstraction

| Layer | Focus | Example Metrics |
|-------|-------|----------------|
| **Stroke Abstraction** | WHAT happens during the swing | Hip rotation, elbow angle, spine lean |
| **Movement Intelligence** | HOW you get into position | Split-step timing, recovery time, balance |
| **Together** | Complete tennis technique | Full game intelligence |

### Integration Example

**Scenario**: Player has inconsistent backhand contact point

**Stroke Analysis** (Phase 2):
- Elbow angle varies 20° between shots
- Hip rotation inconsistent
- **Root cause unclear from stroke data**

**Movement Analysis** (Phase 2.2):
- **Split-step timing is late by 0.15s**
- Stance transition speed is slow (0.6s vs optimal 0.3s)
- Balance drift is high (15cm)

**Integrated Insight**:
- Late split-step → Late first step → Rushed stance setup → Imbalanced position → Inconsistent stroke mechanics
- **Coaching Focus**: Fix split-step timing first, stroke mechanics will improve as a result

---

## Movement Metric Definitions

### 1. Split-Step Timing
- **Description**: Timing of split-step relative to opponent contact
- **Expected Range**: -0.1 to 0.1 seconds (±100ms)
- **Optimal**: 0.0s (perfect sync with opponent contact)
- **Rationale**: Pre-loads muscles for explosive first step
- **Importance**: HIGH
- **Phase Mapping**: Preparation

### 2. Lateral Push-Off Symmetry
- **Description**: Balance between left and right leg power
- **Expected Range**: 0.8 to 1.2 (ratio, 1.0 = perfect)
- **Optimal**: 1.0 (equal power)
- **Rationale**: Prevents injury, enables consistent positioning
- **Importance**: MEDIUM
- **Phase Mapping**: Preparation

### 3. Recovery Time
- **Description**: Time to return to ready position after shot
- **Expected Range**: 0.5 to 1.0 seconds
- **Optimal**: 0.7s
- **Rationale**: Fast recovery enables rally control
- **Importance**: HIGH
- **Phase Mapping**: Follow-through

### 4. Stance Transition Speed
- **Description**: Speed of transitioning from ready to stroke stance
- **Expected Range**: 0.2 to 0.5 seconds
- **Optimal**: 0.3s
- **Rationale**: Quick setup enables optimal stroke mechanics
- **Importance**: MEDIUM
- **Phase Mapping**: Preparation

### 5. Balance Drift
- **Description**: Center of mass lateral drift during shot
- **Expected Range**: 0 to 10 cm
- **Optimal**: 5cm (minimal controlled drift)
- **Rationale**: Stable balance enables consistent contact and power
- **Importance**: HIGH
- **Phase Mapping**: Contact

### 6. First Step Reaction Time
- **Description**: Time from opponent contact to first step initiation
- **Expected Range**: 0.2 to 0.4 seconds
- **Optimal**: 0.3s
- **Rationale**: Quick first step enables better court coverage
- **Importance**: MEDIUM
- **Phase Mapping**: Preparation

### 7. Footwork Efficiency
- **Description**: Ratio of steps taken to distance covered
- **Expected Range**: 1.5 to 2.5 steps per meter
- **Optimal**: 2.0 steps/m
- **Rationale**: Efficient footwork conserves energy
- **Importance**: MEDIUM
- **Phase Mapping**: Preparation

### 8. Weight Transfer Completeness
- **Description**: Percentage of body weight transferred forward
- **Expected Range**: 60 to 90%
- **Optimal**: 75%
- **Rationale**: Complete weight transfer maximizes power
- **Importance**: HIGH
- **Phase Mapping**: Contact

---

## API Reference

### `get_movement_metric_spec(metric_name: str) -> dict`

Get specification for a movement/footwork metric.

**Parameters**:
- `metric_name` (str): Name of movement metric (e.g., 'split_step_timing')

**Returns**:
- `dict`: Metric specification with expected ranges, rationale, importance
- `None`: If metric not found

**Example**:
```python
>>> spec = get_movement_metric_spec('split_step_timing')
>>> print(spec['expected_range'])
(-0.1, 0.1)  # seconds

>>> print(spec['rationale'])
'Split-step should occur at/just before opponent contact for optimal reaction'
```

---

### `assess_movement_quality(metric_name: str, measured_value: float) -> dict`

Assess the quality of a movement/footwork metric.

**Parameters**:
- `metric_name` (str): Name of movement metric
- `measured_value` (float): Player's measured value

**Returns**:
- `dict` with:
  - `classification`: 'excellent' / 'good' / 'needs_work' / 'unknown'
  - `deviation`: Distance from optimal
  - `feedback`: Human-readable coaching feedback
  - `importance`: 'HIGH' / 'MEDIUM' / 'LOW'
  - `stroke_phase`: Related phase ('preparation', 'contact', etc.)

**Example**:
```python
>>> result = assess_movement_quality('split_step_timing', 0.15)
>>> print(result['classification'])
'needs_work'

>>> print(result['feedback'])
'Split-Step Timing is too slow by 0.15s. Split-step should occur at/just before opponent contact for optimal reaction'
```

---

### `is_movement_metric(metric_name: str) -> bool`

Check if a metric belongs to the movement/footwork family.

**Parameters**:
- `metric_name` (str): Name of metric to check

**Returns**:
- `bool`: True if movement metric, False if stroke metric

**Example**:
```python
>>> is_movement_metric('split_step_timing')
True

>>> is_movement_metric('hip_rotation')
False
```

---

## Integration with Existing Systems

### 1. Reliability Analysis ✅

Movement metrics participate in the same reliability assessment as stroke metrics:

```python
# Movement metrics get reliability scores
reliability = assess_measurement_reliability(metric_name, std_dev, sample_size)
# Returns: 'High' / 'Medium' / 'Low'
```

**Impact**:
- Low-reliability movement metrics are flagged
- Unreliable measurements don't generate coaching cues
- Consistent with stroke metric treatment

---

### 2. Adaptive Prioritization ✅

Movement issues are eligible for CRITICAL/PRIORITY/MONITOR classification:

```python
# Movement issues participate in priority scoring
classification = classify_coaching_issue(
    metric_name='split_step_timing',
    current_deviation=0.15,
    reliability_level='High',
    phase_stability=85.0,
    progress_delta=None
)
# Returns: {'classification': 'PRIORITY', 'recommendation': '...'}
```

**Classification Logic**:
- **CRITICAL**: Severe movement issue with high reliability + getting worse
- **PRIORITY**: Significant deviation with reliable measurement
- **MONITOR**: Improving or minor issue
- **SUPPRESS**: Low reliability measurement

---

### 3. Drill Recommendation Engine ✅

Movement metrics map to footwork drills via existing drill system:

```python
# Movement metrics map to movement drills
category = map_metric_to_drill_category('split_step_timing')
# Returns: 'split_step_timing'

# Drill recommendations follow same adaptive logic
drills = generate_adaptive_drill_recommendations(adaptive_focus, drill_kb)
```

**Drill Categories Added**:
- `split_step_timing` - Partner split-step drill, shadow training
- `lateral_push_off_symmetry` - Single-leg bounds, side-to-side shuffles
- `recovery_time` - Touch-and-recover drill, recovery sprints
- `stance_transition_speed` - Quick-setup shadow, cone-touch drill
- `balance_drift` - Balance board strokes, single-leg holds
- `first_step_reaction_time` - Light reaction drill, ball drop drill
- `footwork_efficiency` - Minimalist footwork, ladder agility
- `weight_transfer_completeness` - Weight transfer shadow, medicine ball throws
- `general_movement` - Court coverage circuit, footwork & shot combination

---

### 4. Drill Outcome Tracking ✅

Movement drills participate in effectiveness tracking:

```python
# Track movement drill outcomes same as stroke drills
track_drill_outcomes(
    previous_session_metrics={'split_step_timing': -0.15},
    current_session_metrics={'split_step_timing': -0.08},
    drill_recommendations=[{'drill_name': 'Partner Split-Step Drill', ...}]
)
# Stores: session_id, metric, drill, delta, reliability, classification
```

---

### 5. Drill Confidence Scoring ✅

Movement drills get confidence scores based on historical effectiveness:

```python
# Compute confidence for movement drills
confidence_scores = compute_drill_confidence_scores(drill_outcomes)
# Returns: {'Partner Split-Step Drill': {'confidence_score': 0.78, ...}}
```

---

## Footwork Drills Knowledge Base

### Split-Step Timing Drills

**1. Partner Split-Step Drill**
- Partner drops ball, practice split-step at exact moment ball bounces
- Light: 2 sets × 10 reps
- Moderate: 4 sets × 15 reps
- Intensive: 6 sets × 20 reps with random timing

**2. Shadow Split-Step Training**
- Watch pro match video, split-step in sync with players
- Light: 5 minutes
- Moderate: 10 minutes
- Intensive: 15 minutes 2x daily

---

### Recovery Time Drills

**1. Touch-and-Recover Drill**
- Hit from wide position, touch center line, recover to ready
- Light: 10 reps per side
- Moderate: 20 reps per side
- Intensive: 30 reps per side, timed

**2. Recovery Sprint Intervals**
- Sprint to corner, hit imaginary shot, sprint back to center
- Light: 6 reps
- Moderate: 12 reps
- Intensive: 20 reps with stopwatch

---

### Balance Drift Drills

**1. Balance Board Strokes**
- Practice shadow strokes while standing on balance board
- Light: 2 sets × 10 strokes
- Moderate: 4 sets × 15 strokes
- Intensive: 6 sets × 20 strokes with eyes closed

**2. Single-Leg Balance Holds**
- Hold stroke finish position on one leg, measure stability
- Light: 3 sets × 15 seconds per leg
- Moderate: 4 sets × 30 seconds per leg
- Intensive: 5 sets × 45 seconds per leg with perturbations

---

*(See full drill list in code documentation)*

---

## Design Principles

### 1. Additive Only ✅
- No changes to existing stroke analysis
- No changes to existing similarity scoring
- No changes to existing coaching cue generation
- Movement metrics are optional layer

### 2. Stroke-Agnostic ✅
- Movement metrics apply to all strokes
- Split-step timing same for forehand/backhand/serve
- Recovery time universal across stroke types
- Balance principles consistent

### 3. Existing System Integration ✅
- Uses existing reliability assessment
- Uses existing adaptive prioritization
- Uses existing drill recommendation engine
- Uses existing outcome tracking

### 4. Graceful Degradation ✅
- System works perfectly without movement data
- Missing movement metrics don't cause errors
- Falls back to stroke-only analysis
- Backward compatibility 100% preserved

---

## Usage Example

### Scenario: Analyze Player's Movement Quality

```python
from vision.compare import (
    get_movement_metric_spec,
    assess_movement_quality,
    is_movement_metric
)

# Example measured values (would come from CV analysis)
measured_metrics = {
    'split_step_timing': 0.12,  # 120ms late
    'recovery_time': 0.9,  # 0.9 seconds
    'balance_drift': 7.5,  # 7.5 cm
    'weight_transfer_completeness': 68  # 68%
}

# Assess each movement metric
for metric_name, value in measured_metrics.items():
    # Get metric specification
    spec = get_movement_metric_spec(metric_name)
    print(f"\n{spec['name']}:")
    print(f"  Measured: {value}")
    print(f"  Expected: {spec['expected_range']}")
    print(f"  Optimal: {spec['optimal_value']}")
    
    # Assess quality
    assessment = assess_movement_quality(metric_name, value)
    print(f"  Classification: {assessment['classification']}")
    print(f"  Feedback: {assessment['feedback']}")
    print(f"  Importance: {assessment['importance']}")
```

**Output**:
```
Split-Step Timing:
  Measured: 0.12
  Expected: (-0.1, 0.1)
  Optimal: 0.0
  Classification: needs_work
  Feedback: Split-Step Timing is too slow by 0.12s. Split-step should occur...
  Importance: HIGH

Recovery Time:
  Measured: 0.9
  Expected: (0.5, 1.0)
  Optimal: 0.7
  Classification: good
  Feedback: Recovery Time is good but can improve. Fast recovery enables...
  Importance: HIGH
```

---

## Validation

### Backward Compatibility Test ✅

```bash
python vision/compare.py
# Overall score: 62.4/100 ✅ (unchanged)
# Phase-weighted: 59.9/100 ✅ (unchanged)
# No errors ✅
```

### Movement Metric Integration ✅

- ✅ Movement metrics defined and documented
- ✅ Assessment functions implemented
- ✅ Drill knowledge base extended
- ✅ Drill mapping updated
- ✅ Reliability system compatible
- ✅ Prioritization system compatible
- ✅ Outcome tracking compatible

---

## Future Vision

### Phase 3: CV-Based Movement Extraction
- Extract split-step timing from video
- Measure recovery time via pose tracking
- Compute balance drift from center of mass
- Calculate stance transition speed

### Phase 4: Integrated Movement + Stroke Analysis
- Correlate movement quality with stroke consistency
- Identify movement issues causing stroke problems
- Generate integrated coaching priorities

### Phase 5: Movement Progression Tracking
- Track movement improvements over time
- Compare movement patterns to pro players
- Personalized movement drill progression

---

## Summary

The **Movement & Footwork Intelligence** layer:

1. ✅ Defines 8 stroke-agnostic movement metrics
2. ✅ Provides assessment and feedback APIs
3. ✅ Extends drill knowledge base with footwork drills
4. ✅ Integrates with existing reliability/prioritization systems
5. ✅ Maintains 100% backward compatibility
6. ✅ Enables complete tennis technique analysis

**Philosophy**: Movement is foundational. Analyze HOW players get into position, not just WHAT they do with the shot.

**Status**: ✅ Complete and ready for CV integration

---

*Implementation completed: December 27, 2025*  
*Phase: 2.2 (Movement & Footwork Intelligence)*  
*Lines added: ~600 (code + drills)*  
*Breaking changes: 0*

