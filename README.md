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
├── outputs/               # Generated outputs
├── requirements.txt
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

