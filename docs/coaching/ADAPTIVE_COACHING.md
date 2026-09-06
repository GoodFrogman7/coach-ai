# Adaptive Coaching Decision Engine

## Overview

The Adaptive Coaching Decision Engine intelligently prioritizes coaching recommendations based on multiple factors including severity, measurement reliability, consistency, and progress tracking. This ensures users focus on issues that are real, significant, actionable, and persistent.

## What Was Added

### 1. Priority Scoring System (`compute_issue_priority_score`)

Computes a comprehensive priority score (0-100+) for each coaching issue based on multiple weighted factors.

**Priority Components**:

1. **Severity Score** (0-40 points) - Based on deviation magnitude
   - For angles:
     - ≥80° deviation: 40 points
     - ≥50° deviation: 35 points
     - ≥30° deviation: 30 points
     - ≥20° deviation: 20 points
     - ≥10° deviation: 10 points
     - <10° deviation: 5 points
   - For normalized metrics:
     - ≥4.0 deviation: 40 points
     - ≥3.0 deviation: 30 points
     - ≥2.0 deviation: 20 points
     - ≥1.0 deviation: 10 points
     - <1.0 deviation: 5 points

2. **Reliability Weight** (0-25 points) - Measurement confidence
   - High reliability: 25 points
   - Medium reliability: 15 points
   - Low reliability: 5 points

3. **Phase Importance** (0-20 points) - Critical phases weighted higher
   - Contact: 20 points (most critical)
   - Load: 15 points
   - Follow-through: 12 points
   - Preparation: 8 points

4. **Consistency Factor** (0-15 points) - Intra-phase stability
   - Higher phase stability = higher priority
   - Formula: (phase_stability / 100) × 15
   - Stable issues are more actionable than random noise

5. **Progress Modifier** (-10 to +10 points) - Session-to-session changes
   - Worsening (>+5 points): +10 points max (escalate)
   - Improving (<-5 points): -10 points max (deprioritize)
   - Stable (±5 points): 0 points (neutral)

**Example Priority Calculation**:
```
Hip Rotation Issue:
- Severity: 88.5° deviation → 40 points
- Reliability: Low → 5 points
- Phase: Load → 15 points
- Consistency: 81.7/100 stability → 12.3 points
- Progress: -19 points (regressed) → +10 points
Total Priority Score: 82.3/100
```

### 2. Issue Classification System (`classify_coaching_issue`)

Classifies each issue into one of four categories for adaptive recommendations.

**Classifications**:

#### 🚨 **CRITICAL** - Address immediately
**Criteria**: Severe + high reliability + consistent
- Large deviation (≥50° for angles, ≥3.0 for others)
- High reliability measurement
- High phase stability (≥70)
- Especially if worsening

**Action**: Top priority, must address immediately

#### ⭐ **PRIORITY** - Focus on these
**Criteria**: Significant + reliable + not improving
- Moderate to severe deviation
- Medium or high reliability
- Not actively improving

**Action**: Important focus areas for training

#### 📊 **MONITOR** - Track progress
**Criteria**: Improving OR needs verification
- Currently improving (progress delta < -5)
- OR moderate deviation with low reliability
- OR consistent but minor issue

**Action**: Keep tracking, continue current approach if improving

#### 🔇 **SUPPRESS** - Deprioritize
**Criteria**: Low reliability + not severe
- Low measurement confidence
- Small deviation
- May be noise rather than real issue

**Action**: Don't focus on these; prioritize reliable metrics first

### 3. Adaptive Coaching Focus Generator (`generate_adaptive_coaching_focus`)

Orchestrates the adaptive coaching system by computing priority scores, classifying issues, and generating structured recommendations.

**Process**:
1. For each coaching cue:
   - Extract metric, deviation, phase data
   - Get reliability level from system reliability analysis
   - Get phase stability score
   - Get progress delta from session tracking
2. Compute priority score using all factors
3. Classify issue (CRITICAL/PRIORITY/MONITOR/SUPPRESS)
4. Sort by priority score (highest first)
5. Group by classification for structured output

**Output Structure**:
```python
{
    'all_adaptive_cues': [...],  # All cues with priority data
    'critical': [...],           # Critical issues
    'priority': [...],           # Priority issues
    'monitor': [...],            # Monitoring items
    'suppressed': [...],         # Suppressed items
    'top_3': [...]              # Top 3 by priority score
}
```

### 4. New Report Section: "🎯 Adaptive Coaching Focus"

Added comprehensive adaptive coaching section to the report (appears after "Today's Focus", before "Progress Since Last Session").

**Section Structure**:

#### Introduction
Explains the adaptive coaching system and its benefits.

#### 🚨 Critical Issues (if any)
- Shows issues requiring immediate attention
- Displays severity, reliability, priority score
- Shows trend if available (↗ worsening / ↘ improving)
- Limited to top 3 critical issues

#### ⭐ Priority Issues
- Important areas with reliable measurements
- Shows deviation, reliability, phase stability
- Priority score for ranking
- Limited to top 3 priority issues

#### 📊 Monitoring
- Issues that are improving or need verification
- Shows status and specific recommendations
- Highlights improvements (🎉) or reliability concerns (⚠️)
- Limited to top 3 monitoring items

#### 🔇 Deprioritized Issues
- Lists suppressed items (low reliability or minor)
- Shows count and top 5 examples
- Explains why they're deprioritized

#### 📈 How Adaptive Coaching Works
- Explains priority scoring components
- Defines each classification
- Describes what makes issues actionable

**Example Output**:
```markdown
## 🎯 Adaptive Coaching Focus

### 📊 Monitoring (Track Progress)

1. **Hip Rotation** (Load)
   - Status: Verify measurement quality before focusing on this
   - ⚠️ Low reliability - verify measurement quality

2. **Right Elbow Angle** (Contact)
   - Status: Verify measurement quality before focusing on this
   - ⚠️ Low reliability - verify measurement quality

### 🔇 Deprioritized Issues (2 items)

- Left Elbow Angle (Low reliability)
- Stance Width Normalized (Low reliability)

### 📈 How Adaptive Coaching Works

**Priority Scoring considers:**
1. **Severity** (40%): How far from pro technique
2. **Reliability** (25%): Measurement confidence
3. **Phase Importance** (20%): Critical phases weighted higher
4. **Consistency** (15%): Stable issues vs random noise
5. **Progress Modifier** (±10%): Escalates worsening issues, deprioritizes improving ones
```

## Technical Implementation

### Files Modified

**`vision/compare.py`** (~350 lines added):

1. **New Functions** (added after reliability analysis):
   - `compute_issue_priority_score()` - Multi-factor priority computation
   - `classify_coaching_issue()` - Four-tier classification system
   - `generate_adaptive_coaching_focus()` - Adaptive recommendations orchestrator

2. **Updated Functions**:
   - `generate_report()` - Added adaptive coaching focus section
   - Uses existing `ranked_cues`, `user_reliability`, `user_phase_stability`, `progress_deltas`

### Integration Points

The adaptive coaching engine leverages existing system outputs:

1. **Ranked Cues** - From existing cue prioritization by deviation
2. **User Reliability** - From reliability analysis system
3. **Phase Stability** - From intra-phase stability computation
4. **Progress Deltas** - From longitudinal progress tracking

**Zero new data collection** - purely additive intelligence layer.

## How It Works

### Scenario 1: First Session (No Progress Data)

**Input**:
- User has large hip rotation deviation (88.5°)
- Measurement reliability: Low
- Phase stability: 81.7/100
- No previous session data

**Adaptive Engine Processing**:
```
Priority Score:
- Severity: 40 points (large deviation)
- Reliability: 5 points (low confidence)
- Phase: 15 points (load phase)
- Consistency: 12.3 points (81.7% stable)
- Progress: 0 points (no history)
Total: 72.3/100

Classification: MONITOR
Reason: Low reliability despite severity
```

**Recommendation**: "Verify measurement quality before focusing on this"

### Scenario 2: Subsequent Session (Worsening Issue)

**Input**:
- Same hip rotation issue
- Reliability improved: Medium
- Phase stability: 85/100
- Progress: -15 points (regressed significantly)

**Adaptive Engine Processing**:
```
Priority Score:
- Severity: 40 points
- Reliability: 15 points (medium confidence)
- Phase: 15 points
- Consistency: 12.8 points
- Progress: +10 points (worsening)
Total: 92.8/100

Classification: CRITICAL
Reason: Severe + reliable + worsening
```

**Recommendation**: "Address immediately - severe issue getting worse"

### Scenario 3: Improving Issue

**Input**:
- Elbow angle issue (28.5° deviation)
- Reliability: High
- Phase stability: 90/100
- Progress: -12 points (improved significantly)

**Adaptive Engine Processing**:
```
Priority Score:
- Severity: 30 points (moderate)
- Reliability: 25 points (high confidence)
- Phase: 20 points (contact)
- Consistency: 13.5 points
- Progress: -10 points (improving)
Total: 78.5/100

Classification: MONITOR
Reason: Actively improving
```

**Recommendation**: "Continue current approach - showing improvement 🎉"

## Benefits

### For Athletes

**Before**: All issues shown equally
- Overwhelmed by long list of problems
- Unclear what to focus on first
- Low-reliability metrics cause confusion
- No sense of progress impact

**After**: Intelligent prioritization
- Clear critical vs. minor issues
- Focus on reliable, actionable items
- Improving areas celebrated
- Worsening issues escalated

### For Coaches

**Before**: Manual triage required
- Had to mentally filter low-reliability metrics
- Hard to track what's improving
- No systematic prioritization
- Repeated same cues even if improving

**After**: Automated intelligent triage
- System filters unreliable measurements
- Progress automatically factored in
- Evidence-based prioritization
- Dynamic recommendations adapt to progress

### For System Quality

**Before**: Static recommendations
- Same cues regardless of progress
- No penalty for low reliability
- No reward for improvement
- Persistence not tracked

**After**: Dynamic, adaptive coaching
- Recommendations change with progress
- Low reliability deprioritized
- Improvements acknowledged
- Persistent issues escalated

## Use Cases

### Use Case 1: Filtering Measurement Noise

**Scenario**: User has several large deviations, but many have low reliability.

**Adaptive Engine Action**:
- High-reliability issues → PRIORITY or CRITICAL
- Low-reliability issues → MONITOR or SUPPRESS
- User focuses on trustworthy measurements first

**Result**: More effective training, less frustration

### Use Case 2: Celebrating Progress

**Scenario**: User has been working on elbow angles for 3 sessions, now showing -15 point improvement.

**Adaptive Engine Action**:
- Despite still having deviation, classified as MONITOR
- Shows "🎉 Improving: -15 points better"
- Deprioritized from top focus areas

**Result**: Positive reinforcement, maintain current approach

### Use Case 3: Escalating Persistent Issues

**Scenario**: Hip rotation issue present for 3 sessions, getting worse each time.

**Adaptive Engine Action**:
- Severity + persistence + worsening → CRITICAL
- Moved to top of recommendations
- Flagged with urgency indicators

**Result**: User addresses real, persistent problems

### Use Case 4: Phase-Specific Focus

**Scenario**: Multiple issues across phases, some in critical contact phase.

**Adaptive Engine Action**:
- Contact phase issues weighted higher (20 points)
- Preparation issues weighted lower (8 points)
- Priority reflects biomechanical importance

**Result**: Focus on phases with highest impact

## Validation & Testing

### Test 1: First Session Behavior

**Expected**: Normal coaching cues, adaptive section shows initial priorities

**Result**: ✅ Passed
- Low-reliability metrics moved to MONITOR
- No critical issues (no progress history)
- Clear explanation of prioritization

### Test 2: Subsequent Session Adaptation

**Expected**: Recommendations adapt based on progress

**Result**: ✅ Verified (from test run)
- Issues with low reliability deprioritized
- Progress tracking integrated into classifications
- Section appears dynamically

### Test 3: Reliability Impact

**Expected**: Low-reliability metrics have lower priority

**Result**: ✅ Confirmed
- Hip rotation (88.5° deviation, Low reliability) → MONITOR
- Not shown as CRITICAL despite large deviation
- Recommendation: "Verify measurement quality first"

## Future Enhancements (Not Implemented)

Possible extensions:

1. **Multi-Session Persistence Tracking**
   - Track issues across >2 sessions
   - Escalate issues present in 3+ sessions
   - De-escalate issues absent for 2+ sessions

2. **User Skill Level Adaptation**
   - Beginner: Focus on fundamentals (preparation, stance)
   - Intermediate: Focus on power (load, hip rotation)
   - Advanced: Focus on refinement (contact precision)

3. **Custom Priority Weights**
   - Allow coaches to adjust factor weights
   - Sport-specific priority profiles
   - User preference for risk tolerance

4. **Issue Clustering**
   - Group related issues (e.g., all upper body)
   - Suggest holistic fixes for clusters
   - Avoid overwhelming with similar issues

5. **Drill Recommendation Mapping**
   - Map issue classifications to specific drills
   - CRITICAL issues → intensive drills
   - MONITOR issues → maintenance drills

## Summary

The Adaptive Coaching Decision Engine transforms Coach AI from a static analysis tool into an intelligent coaching system that:

✅ **Prioritizes intelligently** using multi-factor scoring
✅ **Filters measurement noise** by deprioritizing low-reliability metrics
✅ **Celebrates progress** by monitoring improving areas
✅ **Escalates persistent problems** that worsen over time
✅ **Adapts dynamically** based on session history
✅ **Provides transparency** with clear explanation of prioritization
✅ **Maintains backward compatibility** - purely additive logic

**Implementation**: ~350 lines of intelligent decision logic, zero changes to existing metrics/scores, maximum impact on coaching effectiveness.

The system now provides **adaptive, personalized coaching** that evolves with the user's progress, making training more effective and motivating! 🎯

