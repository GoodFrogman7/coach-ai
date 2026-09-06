# Coach AI - Tennis Backhand Analyzer

AI-powered tennis stroke analysis using computer vision. This MVP analyzes your two-handed backhand against professional references (Djokovic) and provides personalized coaching feedback.

## Features

- **Pose Extraction**: Uses MediaPipe Pose to track 33 body landmarks per frame
- **Biomechanical Analysis**: Computes joint angles, hip rotation, spine lean, and stance width
- **Movement Phase Segmentation**: Automatically segments strokes into preparation, load, contact, and follow-through
- **Impact Detection**: Automatically detects the ball contact frame via wrist speed
- **ML-Based Similarity**: Uses machine learning to compare movement patterns with professional techniques
- **Longitudinal Progress Tracking**: Tracks improvement across practice sessions
- **System Reliability Analysis**: Assesses measurement confidence and technique consistency
- **Video Overlay**: Generates annotated videos with skeleton visualization
- **Professional Coaching Reports**: Executive summary with key insights, actionable cues, and practice drills
- **Sport-Agnostic Configuration**: Customizable for different sports via YAML config files
- **Match Readiness Intelligence**: Synthesizes technique, movement, fatigue, and trust into a single readiness signal
- **Training Load & Session Planning**: Converts readiness signals into actionable training guidance (session type, intensity, focus areas)
- **Player Baseline & Personalization**: Computes personal reference values from historical sessions for relative improvement tracking
- **Progress Narratives & Coach Summaries**: Generates human-readable summaries of multi-session trends in coach-style language
- **RAG-Powered Q&A System**: "Ask Coach AI" interface with ensemble retrieval (TF-IDF + semantic embeddings) and LLM-powered explanations

## Project Structure

```
coach_ai/
├── vision/
│   ├── extract_pose.py    # MediaPipe pose extraction
│   ├── overlay_pose.py    # Skeleton overlay on video
│   ├── features.py        # Biomechanical feature computation
│   └── compare.py         # Full pipeline + report generation
├── data/
│   ├── user/              # Place your video here (input.mp4)
│   └── reference/         # Reference videos (djokovic_backhand.mp4)
├── kb/                    # Knowledge base markdown files
├── rag/                   # RAG system (indexing, retrieval, LLM)
├── outputs/               # Generated outputs (one folder per session)
├── users/                 # Player profiles: session names per player (JSON)
├── ui/
│   ├── data.py            # Read-only report parsing helpers
│   ├── users.py           # Player profiles and session naming
│   └── pages/             # One module per dashboard page (upload, dashboard, ...)
├── streamlit_app.py       # Dashboard entry point (router only)
├── requirements.txt       # Ranged dependencies
├── requirements.lock      # Pinned, CI-verified versions
└── README.md
```

## Installation

1. **Clone or navigate to the project**:
   ```bash
   cd C:\coach_ai
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or: source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   For the exact, CI-verified versions (Python 3.10), use the lock file instead.
   Install CPU-only torch first so the ML libraries do not pull the CUDA build:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   pip install -r requirements.lock
   ```
   After editing `requirements.txt`, regenerate the lock with `pip freeze > requirements.lock`
   from a clean environment and keep the header comment.

## Usage

### Quick Start

1. **Add your videos**:
   - Place your backhand video at: `data/user/input.mp4`
   - Place a reference video at: `data/reference/djokovic_backhand.mp4`

2. **Run the analysis**:
   ```bash
   python vision/compare.py
   ```

3. **View results** in the `outputs/` folder:
   - `overlay_user.mp4` - Your video with pose overlay
   - `overlay_ref.mp4` - Reference video with pose overlay
   - `user_features.csv` - Your frame-by-frame biomechanics
   - `ref_features.csv` - Reference frame-by-frame biomechanics
   - `report.md` - **Your personalized coaching report**

4. **View Dashboard** (optional):
   ```bash
   streamlit run streamlit_app.py
   ```
   - Interactive visualization dashboard
   - Performance metrics and trends
   - Drill effectiveness analysis
   - Progress tracking across sessions

5. **Setup RAG Q&A System** (optional):
   ```bash
   # Build knowledge base index (one-time setup)
   python rag/index_kb.py
   ```
   
   **Option A: Local LLM with Ollama (Recommended - Free & Private)**
   ```bash
   # Install Ollama: https://ollama.ai/download
   # Then pull a model:
   ollama pull llama3.2:3b
   
   # Configure Coach AI to use Ollama:
   # Windows PowerShell:
   $env:USE_OLLAMA="true"
   
   # Windows CMD:
   set USE_OLLAMA=true
   ```
   
   **Option B: Cloud LLM (Requires API Key)**
   ```bash
   # Windows PowerShell:
   $env:OPENAI_API_KEY="sk-..."
   # Or:
   $env:ANTHROPIC_API_KEY="sk-ant-..."
   ```
   
   - Navigate to "🤖 Ask Coach" in Streamlit
   - Ask questions about technique, metrics, training
   - Get AI-powered explanations grounded in KB + your data
   - **Strict Grounding (Recommended)**: Prevents LLM hallucination by blocking low-confidence retrievals
   - See detailed documentation in `OLLAMA_SETUP.md` and `RAG_SYSTEM.md`

#### RAG Strict Grounding Policy

Coach AI uses a **production-safe grounding policy** to prevent hallucination:

- **Low Confidence Retrieval** → LLM NOT called (shows retrieved sources only + clarifying questions)
- **Medium Confidence Retrieval** → LLM used with source citation requirements
- **High Confidence Retrieval** → Full LLM explanation with source citations

**UI Controls**:
- **Mode**: "Explain my session" | "Teach the concept" | "Drill how-to"
- **Depth**: "Quick" (2-3 paragraphs) | "Detailed" (comprehensive)
- **Strict Grounding**: ON (recommended) | OFF (allow LLM on low confidence)

**Q&A History**:
- All questions/answers logged to `outputs/{session_id}/qa_log.json`
- View recent questions in sidebar
- Click to re-display saved answers (no LLM call)

### Sport-Agnostic Configuration (Optional)

Coach AI now supports custom sport configurations via YAML files. This is **completely optional** - the system works perfectly with hardcoded tennis defaults.

**Default (Tennis Backhand)**:
```bash
python vision/compare.py
```

**Custom Sport Configuration**:
```bash
python vision/compare.py --config config/tennis_backhand.yaml
```

Configuration files let you customize:
- Movement phases and their importance weights
- Biomechanical metrics to analyze
- Phase names and descriptions
- Contact detection methods

See `CONFIG.md` for full documentation and examples for other sports (golf, baseball, etc.).

### Individual Scripts

You can also run components separately:

**Extract pose landmarks to CSV**:
```bash
python vision/extract_pose.py <video_path> [output_csv]
```

**Create overlay video**:
```bash
python vision/overlay_pose.py <input_video> <output_video>
```

**Compute features from landmarks CSV**:
```bash
python vision/features.py <landmarks_csv> [output_csv]
```

## Video Requirements

For best results:
- **Resolution**: 720p or higher
- **Frame rate**: 30+ fps recommended
- **Angle**: Side view (perpendicular to baseline) works best
- **Duration**: Capture the full stroke from preparation to follow-through
- **Lighting**: Well-lit, avoid backlit situations
- **Clothing**: Avoid loose/baggy clothes that obscure body position

## Analyzed Metrics

| Metric | Description |
|--------|-------------|
| Shoulder Angle | Hip-shoulder-elbow angle (arm position) |
| Elbow Angle | Shoulder-elbow-wrist angle (arm bend) |
| Knee Angle | Hip-knee-ankle angle (leg bend) |
| Hip Rotation | Shoulder line vs hip line angle |
| Spine Lean | Torso angle from vertical |
| Stance Width | Ankle distance normalized by hip width |

## Dependencies

- **MediaPipe** (0.10.9): Google's ML pose estimation
- **OpenCV** (4.8.1): Video I/O and rendering
- **NumPy** (1.26.2): Numerical computations
- **Pandas** (2.1.3): Data manipulation and CSV output

## 🎾 Stroke Abstraction Layer (Phase 2)

Coach AI now includes a **Stroke Abstraction Layer** that enables multi-stroke tennis intelligence.

### Supported Strokes

- **Backhand** (default) - Two-handed baseline backhand
- **Forehand** - Dominant-side groundstroke with larger rotation
- **Serve** - First or second serve with maximum power generation
- **Volley** - Net volley with compact, reactive motion
- **Overhead** - Overhead smash with serve-like mechanics

### Stroke-Specific Intelligence

Each stroke has unique biomechanical profiles:
- **Expected ranges** per metric (e.g., forehand hip rotation > backhand)
- **Phase emphasis** (e.g., serve prioritizes contact + preparation)
- **Biomechanical rationale** (why each range is optimal)

### API Usage

```python
from vision.compare import get_stroke_aware_threshold, get_stroke_phase_weights

# Get forehand hip rotation range
forehand_hip = get_stroke_aware_threshold('hip_rotation', 'forehand')
# Returns: (180, 270) - larger than backhand (150, 220)

# Get serve phase weights
serve_weights = get_stroke_phase_weights('serve')
# Returns: {'preparation': 0.20, 'load': 0.20, 'contact': 0.40, 'follow_through': 0.20}
```

### Backward Compatibility

✅ **100% preserved** - Default stroke type is 'backhand', maintaining all existing behavior.

See `STROKE_ABSTRACTION.md` for complete documentation.

## 🏃 Movement & Footwork Intelligence (Phase 2.2)

Coach AI now includes **Movement & Footwork Intelligence** for stroke-agnostic movement analysis.

### The Foundation Principle

**"Good feet, good shots"** - Movement is foundational to stroke execution.

### Movement Metrics

Coach AI evaluates 8 key movement & footwork metrics:

| Metric | Focus | Importance |
|--------|-------|------------|
| **Split-Step Timing** | Timing relative to opponent contact | HIGH |
| **Recovery Time** | Return to ready position speed | HIGH |
| **Balance Drift** | Center of mass stability | HIGH |
| **Weight Transfer** | Forward weight shift completeness | HIGH |
| **Lateral Push-Off Symmetry** | Left/right leg balance | MEDIUM |
| **Stance Transition Speed** | Ready → stroke stance speed | MEDIUM |
| **First Step Reaction** | Opponent contact → first step | MEDIUM |
| **Footwork Efficiency** | Steps per meter covered | MEDIUM |

### How It Complements Stroke Abstraction

| Layer | Focus | Example |
|-------|-------|---------|
| **Stroke Abstraction** | WHAT happens during swing | Hip rotation, elbow angle |
| **Movement Intelligence** | HOW you get into position | Split-step, recovery, balance |
| **Together** | Complete tennis technique | Full game analysis |

### Integration with Existing Systems

✅ **Reliability Analysis** - Movement metrics get reliability scores  
✅ **Adaptive Prioritization** - Movement issues classified as CRITICAL/PRIORITY/MONITOR  
✅ **Drill Recommendations** - 30+ footwork drills mapped to movement metrics  
✅ **Outcome Tracking** - Movement drill effectiveness tracked over time

### API Usage

```python
from vision.compare import get_movement_metric_spec, assess_movement_quality

# Get split-step timing specification
spec = get_movement_metric_spec('split_step_timing')
# Returns: {'expected_range': (-0.1, 0.1), 'optimal_value': 0.0, ...}

# Assess player's split-step timing
assessment = assess_movement_quality('split_step_timing', 0.12)
# Returns: {'classification': 'needs_work', 'feedback': '...', ...}
```

### Backward Compatibility

✅ **100% preserved** - Movement metrics are optional, system works without them.

See `MOVEMENT_INTELLIGENCE.md` for complete documentation.

## ⏱️ Rally & Fatigue Intelligence (Phase 2.3)

Coach AI now includes **Rally & Fatigue Intelligence** for temporal analysis and fatigue pattern detection.

### The Fatigue Problem

**Key Insight**: Tired players exhibit biomechanical degradation that looks like poor technique but has a different root cause.

**Example**:
- Early in session: Hip rotation = 180°, recovery time = 0.7s
- Late in session: Hip rotation = 160°, recovery time = 1.1s

**Question**: Technique issue or fatigue?

**Traditional Analysis** ❌: "Work on hip rotation technique"  
**With Fatigue Intelligence** ✅: "FATIGUE-DRIVEN (75/100 score) - Address conditioning first"

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Rally Segmentation** | Group strokes into rally sequences based on time gaps |
| **Metric Trajectories** | Track how metrics evolve over session duration |
| **Fatigue Inference** | Detect degradation patterns from biomechanics |
| **Fatigue-Aware Coaching** | Route issues to technique vs conditioning interventions |

### Fatigue Detection Signals

| Signal | Pattern | Weight |
|--------|---------|--------|
| Recovery time increasing | late > early by >15% | 25 pts |
| Balance drift increasing | late > early by >20% | 20 pts |
| Hip rotation decreasing | late < early by >10% | 20 pts |
| High variability | CV > 25% | 10 pts |

**Fatigue Score**: 0-100 (0=none, 100=strong fatigue signals)

### Integration

✅ **Works with Stroke Metrics** - Hip rotation, elbow angles, etc.  
✅ **Works with Movement Metrics** - Recovery time, balance drift, stance transition  
✅ **Adaptive Prioritization** - Fatigue-driven issues flagged for conditioning  
✅ **Graceful Degradation** - Works with sparse data or single-stroke sessions

### API Usage

```python
from vision.compare import infer_fatigue_from_biomechanics, classify_issue_with_fatigue_context

# Infer fatigue from session metrics
metrics = {
    'recovery_time': [0.7, 0.8, 0.9, 1.0, 1.1],
    'hip_rotation': [180, 175, 170, 165, 160]
}
fatigue = infer_fatigue_from_biomechanics(metrics)
# Returns: {'fatigue_score': 75, 'confidence': 'high', 'recommendation': '...'}

# Classify issue with fatigue context
result = classify_issue_with_fatigue_context(
    'recovery_time', 0.3, 'High', 80.0, None, fatigue
)
# Returns: {'fatigue_flag': True, 'intervention_type': 'conditioning', ...}
```

### Backward Compatibility

✅ **100% preserved** - Rally/fatigue analysis is optional, system works without it.

See `RALLY_FATIGUE_INTELLIGENCE.md` for complete documentation.

## 📹 CV-Based Movement Extraction (Phase 3.1)

Coach AI now includes **CV-Based Movement Extraction** to automatically compute movement metrics from video.

### The Automation Achievement

**Before Phase 3.1**: Movement metrics defined but required manual input  
**After Phase 3.1**: Automated extraction from MediaPipe pose → Real-time analysis

### Implemented Metrics

| Metric | Extraction Method | Confidence |
|--------|-------------------|------------|
| **Split-Step Timing** | COM vertical dip + knee flexion | 0.0-1.0 |
| **Recovery Time** | COM velocity stabilization | 0.0-1.0 |
| **Balance Drift** | Lateral COM movement | 0.0-1.0 |

### How It Works

```python
from vision.compare import extract_movement_metrics_from_video

# Automatic extraction from pose landmarks
metrics = extract_movement_metrics_from_video(landmarks_df, contact_frame=220, fps=24.0)

# Results with confidence scores
if metrics['split_step_timing']['confidence'] > 0.5:
    print(f"Split-step: {metrics['split_step_timing']['split_step_quality']}")
    # Output: "Split-step: on-time"

if metrics['recovery_time']['confidence'] > 0.5:
    print(f"Recovery: {metrics['recovery_time']['recovery_time_seconds']:.2f}s")
    # Output: "Recovery: 0.75s"
```

### Technical Approach

**Split-Step Detection**:
- COM vertical dip analysis (Gaussian smoothing + peak detection)
- Knee flexion confirmation
- Timing relative to contact: -150ms to +50ms optimal

**Recovery Measurement**:
- COM lateral velocity tracking
- Stabilization threshold: velocity < 0.005 for 3+ frames
- Time from contact to ready position

**Balance Assessment**:
- Lateral COM movement in ±10 frame window around contact
- Drift magnitude + stability score (0-100)
- Trajectory smoothness for confidence

### Integration

✅ **Movement Intelligence (Phase 2.2)** - Extracted metrics feed into assessment  
✅ **Fatigue Detection (Phase 2.3)** - Recovery time/balance are primary signals  
✅ **Reliability Analysis** - Confidence scores integrated  
✅ **Graceful Degradation** - Missing data handled safely

### Backward Compatibility

✅ **100% preserved** - All CV extraction is optional, pipeline works without it.

See `CV_MOVEMENT_EXTRACTION.md` for complete documentation.

## 🎯 Match Readiness Intelligence (Phase 4.1)

Coach AI now includes **Match Readiness Intelligence** - a synthesis layer that combines all existing intelligence into a single, explainable readiness signal.

### What Is Match Readiness?

**Match Readiness** synthesizes:
- **Technique Quality** (40% weight): Stroke biomechanics
- **Movement Quality** (30% weight): Footwork, balance, recovery
- **Energy Level** (20% weight): Inverse of fatigue signals
- **Signal Trust** (10% weight): Measurement reliability

**Result**: A single readiness score (0-100) with confidence and human-readable explanation.

### Example Output

```markdown
## 🎯 Match Readiness Assessment

### Overall Readiness: 🟢 Excellent

**Score**: 88.3/100 (Confidence: 95%)

**Summary**: Excellent readiness, driven by strong technique quality.

### Contributing Factors

- 🎾 Technique Quality: 92.5/100 (weight: 40%) → contributes 37.0 points
- 👟 Movement Quality: 85.2/100 (weight: 30%) → contributes 25.6 points
- ⚡ Energy Level: 88.0/100 (weight: 20%) → contributes 17.6 points
- 📊 Signal Quality: 92.0/100 (weight: 10%) → contributes 9.2 points

### What This Means For You

**Excellent Readiness (85-100)**: You're in peak form. Ready for competition or high-intensity training.
```

### Key Features

✅ **Explainable**: Every score includes human-readable explanation  
✅ **Graceful Degradation**: Works with partial data (minimum: technique only)  
✅ **Confidence Scoring**: Reflects data availability and trust  
✅ **Warning Flags**: Actionable alerts for specific concerns  
✅ **Read-Only Synthesis**: Does NOT alter existing analysis

### Important Clarifications

**Match Readiness IS**:
- ✅ A synthesis of observable biomechanical state
- ✅ A training and competition guidance signal
- ✅ An explainable, actionable metric

**Match Readiness IS NOT**:
- ❌ A performance prediction
- ❌ An injury risk assessment
- ❌ A physiological readiness measure
- ❌ A replacement for coach judgment

### Readiness Levels

| Level | Score | Guidance |
|-------|-------|----------|
| **Excellent** | 85-100 | Ready for competition or high-intensity training |
| **Good** | 70-84 | Solid condition. Can compete or train hard |
| **Fair** | 55-69 | Adequate for moderate training. Consider technical drills |
| **Poor** | 0-54 | Focus on recovery or technique refinement |

### Integration

Match readiness appears automatically in your coaching report when sufficient data is available. The system gracefully reweights components if some data is missing.

See `MATCH_READINESS_INTELLIGENCE.md` for complete documentation.

## 📋 Training Load & Session Planning (Phase 4.2)

Coach AI now includes **Training Load & Session Planning Intelligence** - a synthesis layer that converts readiness and fatigue signals into actionable training guidance.

### What Is Training Load Recommendation?

**Training Load Recommendation** answers three key questions:
1. **What type of session should I do today?** (Recovery/Technique/Movement/Conditioning/Full/Match-sim)
2. **What intensity is appropriate?** (Low/Moderate/High)
3. **What should I focus on or avoid?**

### Decision Logic

| Condition | Session Type | Intensity | Guidance |
|-----------|-------------|-----------|----------|
| **High fatigue (>60)** | Recovery | Low | Prioritize rest |
| **Low readiness (<55)** | Technique | Low | Build fundamentals |
| **Fair readiness (55-69)** | Technique | Moderate | Technical corrections |
| **Good readiness (70-84) + Low fatigue** | Full | High | Complete training |
| **Good readiness + Moderate fatigue** | Conditioning | Moderate | Maintain technique |
| **Excellent readiness (≥85)** | Match-sim | High | Competition prep |

### Example Output

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
```

### Key Features

✅ **Safety-first approach**: High fatigue always triggers recovery  
✅ **Explainable rationale**: Clear reasoning for every recommendation  
✅ **Focus & avoid areas**: Specific guidance for each session  
✅ **Graceful degradation**: Works with partial data

### Important Clarifications

**Training Load IS**:
- ✅ General training guidance based on biomechanical state
- ✅ Session type and intensity recommendations
- ✅ Focus areas and avoid areas

**Training Load IS NOT**:
- ❌ Medical advice or injury prevention
- ❌ Personalized workout prescription
- ❌ Scheduling or periodization system
- ❌ Volume/duration prescriptions

### Integration

Training load recommendations appear automatically in your coaching report when sufficient data is available. The system prioritizes safety (fatigue overrides readiness) and provides conservative guidance when data is limited.

See `TRAINING_LOAD_PLANNING.md` for complete documentation.

## 📊 Player Baseline & Personalization (Phase 5.1)

Coach AI now includes **Player Baseline & Personalization** - aggregates your historical sessions to compute personal reference values for relative improvement tracking.

### What Is a Player Baseline?

**Player Baseline** is YOUR typical performance averaged across recent sessions:
- **Typical Technique Score**: Your average technique similarity
- **Typical Readiness Score**: Your average readiness level
- **Typical Metrics**: Your average biomechanical values

**Result**: Relative interpretation like "Your technique is 8% above YOUR baseline!"

### Absolute vs Relative Scoring

| Type | What It Measures | Example |
|------|-----------------|---------|
| **Absolute** | Comparison to professional reference | "75% similar to Djokovic" |
| **Relative** | Comparison to YOUR baseline | "8% above YOUR baseline" |

**Both are valuable** - absolute shows technical quality, relative shows YOUR improvement.

### Example Output

```markdown
## 📊 Personal Baseline & Progress Context

### Your Baseline (computed from 8 sessions)

**Typical Technique Score**: 76.3%
**Typical Readiness Score**: 74.5/100

### Today's Session vs Your Baseline

**📈 Technique score is 8.1% above baseline**
**📈 Readiness score is 10.1% above baseline**

### How to Interpret

**Above Baseline**: Better than your typical level - great progress!
**Stable (within 5%)**: Consistent performance - normal variation
**Below Baseline**: Below your typical level - check for fatigue
```

### Key Features

✅ **Automatic computation**: Baselines update with each session  
✅ **Rolling window**: Uses last 10 sessions (adapts as you improve)  
✅ **Graceful degradation**: Works with 0, 1, 2, or 3+ sessions  
✅ **No configuration**: Fully automatic

### Minimum Requirements

- **3 sessions**: Minimum to compute first baseline
- **5-10 sessions**: Recommended for reliable baseline
- **No limit**: Baseline automatically uses rolling 10-session window

### Use Cases

1. **Track Improvement**: "15% above baseline" = clear progress signal
2. **Detect Regression**: "12% below baseline" = investigate cause
3. **Validate Consistency**: "Stable within 5%" = competition-ready

### Important Notes

**Baselines ARE**:
- ✅ YOUR personal averages
- ✅ Relative improvement tracking
- ✅ Context for daily variation

**Baselines ARE NOT**:
- ❌ Absolute standards or goals
- ❌ Professional benchmarks
- ❌ Performance predictors

### Integration

Baselines appear automatically in your coaching report when you have 3+ historical sessions. The system scans the `outputs/` directory and computes baselines from your session history.

See `PLAYER_BASELINE_PERSONALIZATION.md` for complete documentation.

## 📈 Progress Narratives & Coach Summaries (Phase 5.2)

Coach AI now includes **Progress Narratives & Coach Summaries** - human-readable interpretive summaries of multi-session trends in coach-style language.

### What Are Progress Narratives?

Instead of just numbers, you get coach-style feedback:

**Before (Numbers)**:
```
Session 1: 70%
Session 2: 72%
Session 3: 74%
Session 4: 76%
Session 5: 78%
```

**After (Narrative)**:
```
Great progress! Your technique is improving (+7%) over the last 5 sessions.

Coach's Take: You're building momentum. Keep up the consistent work 
and trust the process.
```

### How It Works

1. **Trend Detection**: Analyzes last 5 sessions
2. **Classification**: Improving/Stable/Declining (±5% threshold)
3. **Narrative Generation**: Coach-style summary
4. **Coach's Take**: Short actionable insight

### Example Output

```markdown
## 📈 Progress & Coach Summary

### Progress Summary (last 5 sessions)

Great progress! Your technique is improving (+7.0%) and readiness is 
climbing (+6.8%).

### Trend Details

📈 Technique: Improving (from 71.0% to 76.0%, +7.0%)
📈 Readiness: Improving (from 71.7/100 to 76.6/100, +6.8%)

### 🎓 Coach's Take

You're building momentum across the board. Keep up the consistent work 
and trust the process.
```

### Narrative Scenarios

| Scenario | Example Narrative |
|----------|-------------------|
| **Both Improving** | "Great progress! Your technique is improving..." |
| **Mixed Trends** | "Progress in technique, but readiness has dipped..." |
| **Both Stable** | "Solid consistency over 5 sessions..." |
| **Both Declining** | "Recent dips detected. Consider reviewing fundamentals..." |

### Key Features

✅ **Supportive language**: Positive trends first, concerns gently flagged  
✅ **No predictions**: Describes what IS, not what WILL BE  
✅ **Conservative thresholds**: ±5% to avoid false alarms  
✅ **Graceful degradation**: Works with ≥3 sessions

### Important Notes

**Narratives ARE**:
- ✅ Interpretive summaries of recent trends
- ✅ Coach-style feedback
- ✅ Pattern recognition from history

**Narratives ARE NOT**:
- ❌ Predictive models
- ❌ Performance guarantees
- ❌ Absolute truth (trends can reverse)

### Integration

Progress narratives appear automatically in your coaching report when you have 3+ historical sessions. The system analyzes your recent trends and provides encouraging, actionable feedback.

See `PROGRESS_NARRATIVES.md` for complete documentation.

## Troubleshooting

**"Cannot open video" error**:
- Ensure video file exists at the specified path
- Check video codec compatibility (MP4 with H.264 recommended)

**Poor pose detection**:
- Improve lighting conditions
- Ensure full body is visible in frame
- Use higher resolution video

**Import errors**:
- Run from the project root directory (`C:\coach_ai`)
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

## License

MIT License - Feel free to use and modify for your tennis improvement journey!

---

*Built with ❤️ for tennis players looking to level up their game.*

