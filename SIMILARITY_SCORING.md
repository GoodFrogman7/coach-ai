# Similarity Scoring & Cue Prioritization Enhancement - Summary

## What Was Added

Enhanced Coach AI reporting with **similarity scoring** and **intelligent cue prioritization** based on deviation magnitude.

## New Functions in `compare.py`

### 1. `compute_similarity_score(user_metrics, ref_metrics, metric_weights=None)`
Computes technique similarity score (0-100) between user and reference.

**Algorithm**:
- Compares each metric with weighted importance
- Higher weights for critical metrics (hip rotation: 1.5x, stance: 1.2x)
- Uses tolerance ranges (e.g., ±30° for elbows, ±20° for hip rotation)
- Deviation scoring: 0 deviation = 100, tolerance = 50, 2×tolerance = 0
- Returns weighted average across all metrics

**Example Output**: 62.4/100 (Good foundation)

### 2. `compute_phase_similarity_scores(user_phase_metrics, ref_phase_metrics)`
Computes similarity scores for each movement phase.

**Returns**: Dictionary with scores per phase
- Preparation: 76.1/100
- Load: 62.7/100
- Contact: 60.4/100
- Follow-through: 46.7/100

### 3. `rank_cues_by_deviation(user_metrics, ref_metrics, user_phase_metrics, ref_phase_metrics)`
Ranks all potential coaching cues by deviation magnitude.

**Ranking System**:
- Each metric has deviation threshold and weight
- Priority score = |deviation| × weight
- Critical issues (hip rotation -88.5°) score highest
- Returns list of tuples: (priority_score, cue_text, metric_name, deviation, phase)

**Example Ranking**:
1. Hip rotation in load: 265.5 priority (88.5° × 3.0 weight)
2. Right elbow angle: 133.8 priority (66.9° × 2.0 weight)
3. Stance width in prep: 90.0 priority (3.6 × 25 weight)

### 4. `get_phase_cues_with_priority(user_phases, ref_phases)`
Extracts phase-specific cues with their priority scores.

**Phase-Specific Weights**:
- Load phase hip rotation: 3.0× (most critical)
- Stance width in prep: 25× (foundational)
- Follow-through balance: 1.3×

### 5. Enhanced `generate_coaching_cues(..., limit_primary=2)`
Now returns prioritized cues instead of arbitrary list.

**Returns**: Tuple of (primary_cues, all_cues, ranked_cues_data)
- Primary cues: Top 2 for "Today's Focus"
- All cues: Top 5 overall, ranked by priority
- Ranked data: Full analysis for report generation

## Enhanced Report Structure

### New Sections:

#### 1. **Similarity Score Section**
```markdown
## Similarity Score

**Overall Technique Score: 62.4/100**

**Phase-by-Phase Scores:**
- **Preparation**: 76.1/100 ~ Good
- **Load**: 62.7/100 ~ Good
- **Contact**: 60.4/100 ~ Good
- **Follow-through**: 46.7/100 ✗ Needs Work

*Good foundation! Focus on the priority areas below to reach the next level.*
```

**Visual Indicators**:
- ✓ Strong (80-100)
- ~ Good (60-79)
- ✗ Needs Work (0-59)

**Interpretations**:
- 80+: "Excellent! Very close to pro level"
- 60-79: "Good foundation! Focus on priority areas"
- <60: "Significant room for improvement"

#### 2. **Today's Focus Section**
```markdown
## Today's Focus

**Your Top 2 Priorities:**

1. [Load] Coil your hips more during the loading phase...
2. Keep your right elbow closer to your body...

*Primary issue: Hip Rotation (deviation: 88.5°) in load phase*
```

**Features**:
- Limits feedback to top 2 most impactful cues
- Prevents overwhelming the user
- Shows primary issue with quantified deviation
- Phase-tagged for context

#### 3. **All Coaching Cues** (Renamed)
Now explicitly shows priority ranking:
```markdown
## All Coaching Cues

Here's the complete list of areas to work on, ranked by priority:

1. [Load] Coil your hips more... (priority 265.5)
2. Keep your right elbow closer... (priority 133.8)
3. [Preparation] Set up with wider base... (priority 90.0)
4. Bend your left elbow more... (priority 53.4)
5. Rotate your hips more... (priority 26.1)
```

## Key Improvements

### Before Enhancement:
- No quantified similarity metric
- Arbitrary cue ordering
- All issues presented equally
- Difficult to prioritize focus areas

### After Enhancement:
- **Overall score**: 62.4/100 with interpretation
- **Phase scores**: Identifies weak phases (follow-through: 46.7)
- **Prioritized cues**: Top 2 highlighted
- **Quantified deviations**: "Hip Rotation (deviation: 88.5°)"
- **Ranked by impact**: Addresses biggest issues first

## Real-World Example from Latest Run

**Top Issues Identified**:
1. **Hip rotation in load phase**: -88.5° (Priority: 265.5)
   - User: 108.9° vs Pro: 197.5°
   - Critical for power generation
   
2. **Right elbow angle at contact**: +66.9° (Priority: 133.8)
   - User: 103.3° vs Pro: 36.4°
   - Affects control and stability

3. **Stance width in preparation**: -3.6 normalized (Priority: 90.0)
   - User: 1.88 vs Pro: 5.48
   - Foundational stability issue

**Phase-Specific Insights**:
- Preparation: 76.1/100 (relatively strong)
- Load: 62.7/100 (hip rotation deficit)
- Contact: 60.4/100 (elbow positioning)
- Follow-through: 46.7/100 (weakest phase - needs work)

## Technical Details

**Similarity Score Formula**:
```
similarity_per_metric = max(0, 100 × (1 - |deviation| / (2 × tolerance)))
overall_score = weighted_average(similarities, weights)
```

**Priority Score Formula**:
```
priority = |deviation| × metric_weight
```

**Weights by Metric**:
- Hip rotation: 2.5× (contact), 3.0× (load phase)
- Elbow angles: 2.0×
- Stance width: 2.2× (general), 25× (prep phase)
- Knee angles: 2.0×
- Spine lean: 1.5×

## Usage

No changes required - enhancements activate automatically:
```bash
python vision/compare.py
```

The report now includes similarity scores and prioritized feedback!

## Benefits

1. **Measurable Progress**: Track similarity score over time
2. **Clear Priorities**: Focus on top 2 issues, not everything at once
3. **Phase Insights**: Identify which stroke phases need work
4. **Data-Driven**: Rankings based on actual deviation magnitude
5. **Better UX**: Visual indicators (✓, ~, ✗) for quick scanning

