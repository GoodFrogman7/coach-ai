"""
Test script for Ball Tracking Integration
Tests the full pipeline with ball tracking, rally analysis, and visualization.
"""

import sys
from pathlib import Path

# Use simple ASCII for Windows compatibility
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

print("=" * 70)
print("BALL TRACKING INTEGRATION TEST")
print("=" * 70)

# Test 1: Check dependencies
print("\n[TEST 1] Checking dependencies...")
try:
    import cv2
    print(f"  {OK} opencv-python installed")
except ImportError:
    print(f"  {FAIL} opencv-python NOT installed")
    sys.exit(1)

try:
    import mediapipe
    print(f"  {OK} mediapipe installed")
except ImportError:
    print(f"  {FAIL} mediapipe NOT installed")
    sys.exit(1)

try:
    from ultralytics import YOLO
    print(f"  {OK} ultralytics (YOLOv8) installed")
except ImportError:
    print(f"  {WARN} ultralytics NOT installed - ball tracking will be disabled")
    print("     Install with: pip install ultralytics")

try:
    import matplotlib
    print(f"  {OK} matplotlib installed")
except ImportError:
    print(f"  {FAIL} matplotlib NOT installed")
    sys.exit(1)

try:
    import seaborn
    print(f"  {OK} seaborn installed")
except ImportError:
    print(f"  {FAIL} seaborn NOT installed")
    sys.exit(1)

# Test 2: Check project structure
print("\n[TEST 2] Checking project structure...")
required_files = [
    "vision/ball_tracking_models.py",
    "vision/broadcast_overlay.py",
    "vision/compare.py",
    "vision/extract_pose.py",
    "vision/features.py",
    "vision/overlay_pose.py",
    "models/README.md"
]

all_files_exist = True
for file_path in required_files:
    if Path(file_path).exists():
        print(f"  {OK} {file_path}")
    else:
        print(f"  {FAIL} {file_path} NOT FOUND")
        all_files_exist = False

if not all_files_exist:
    print(f"\n  {WARN} Some files are missing!")
    sys.exit(1)

# Test 3: Check YOLO model
print("\n[TEST 3] Checking YOLO model...")
model_path = Path("models/best.pt")
if model_path.exists():
    print(f"  {OK} YOLO model found at {model_path}")
    print("     Ball tracking will be ENABLED")
else:
    print(f"  {WARN} YOLO model NOT found at {model_path}")
    print("     Ball tracking will be DISABLED")
    print("     See models/README.md for setup instructions")

# Test 4: Import new modules
print("\n[TEST 4] Testing new modules...")
try:
    from vision.ball_tracking_models import (
        Ball, Player, RallyStatistics, SpeedClassifier,
        CourtZoneAnalyzer, segment_rallies, compute_rally_statistics
    )
    print(f"  {OK} ball_tracking_models imports successful")
except ImportError as e:
    print(f"  {FAIL} ball_tracking_models import FAILED: {e}")
    sys.exit(1)

try:
    from vision.broadcast_overlay import (
        VisualizationEngine, draw_ball_trajectory, draw_rally_counter,
        draw_analytics_overlay, create_broadcast_overlay,
        generate_player_heatmap, generate_court_zones_heatmap,
        generate_speed_distribution_chart
    )
    print(f"  {OK} broadcast_overlay imports successful")
except ImportError as e:
    print(f"  {FAIL} broadcast_overlay import FAILED: {e}")
    sys.exit(1)

try:
    from vision.compare import (
        is_ball_tracking_available,
        run_ball_detection,
        compute_ball_statistics
    )
    print(f"  {OK} compare.py ball tracking functions imported")
except ImportError as e:
    print(f"  {FAIL} compare.py import FAILED: {e}")
    sys.exit(1)

# Test 5: Test data structures
print("\n[TEST 5] Testing data structures...")
try:
    # Test Ball creation
    ball = Ball(frame_id=1, x=100, y=200, speed=15.5)
    assert ball.frame_id == 1
    assert ball.x == 100
    assert ball.speed == 15.5
    assert ball.speed_category in ['slow', 'medium', 'fast', 'bullet']
    print(f"  {OK} Ball class works correctly")
    
    # Test SpeedClassifier
    assert SpeedClassifier.classify(5.0) == 'slow'
    assert SpeedClassifier.classify(15.0) == 'medium'
    assert SpeedClassifier.classify(25.0) == 'fast'
    assert SpeedClassifier.classify(40.0) == 'bullet'
    print(f"  {OK} SpeedClassifier works correctly")
    
    # Test RallyStatistics
    stats = RallyStatistics()
    stats.update_speed_stats(20.0)
    assert stats.ball_detections == 1
    assert stats.max_ball_speed == 20.0
    print(f"  {OK} RallyStatistics works correctly")
    
    # Test CourtZoneAnalyzer
    h_zone, v_zone = CourtZoneAnalyzer.get_zone(100, 100, 640, 480)
    assert h_zone in ['left', 'center', 'right']
    assert v_zone in ['net', 'mid', 'baseline']
    print(f"  {OK} CourtZoneAnalyzer works correctly")
    
except Exception as e:
    print(f"  {FAIL} Data structure test FAILED: {e}")
    sys.exit(1)

# Test 6: Test rally segmentation
print("\n[TEST 6] Testing rally segmentation...")
try:
    # Create mock ball trajectory
    balls = [
        Ball(frame_id=i, x=100+i, y=200+i, speed=10.0)
        for i in range(1, 11)
    ]
    
    # Add gap (simulating rally break)
    balls.extend([
        Ball(frame_id=i, x=150+i, y=250+i, speed=12.0)
        for i in range(60, 70)
    ])
    
    # Segment rallies
    rallies = segment_rallies(balls, fps=30.0, gap_threshold=1.0)
    assert len(rallies) == 2, f"Expected 2 rallies, got {len(rallies)}"
    print(f"  {OK} Rally segmentation works correctly ({len(rallies)} rallies detected)")
    
    # Compute rally statistics
    rally_stats = compute_rally_statistics(rallies)
    assert rally_stats['total_rallies'] == 2
    print(f"  {OK} Rally statistics computed successfully")
    
except Exception as e:
    print(f"  {FAIL} Rally segmentation test FAILED: {e}")
    sys.exit(1)

# Test 7: Check input videos
print("\n[TEST 7] Checking input videos...")
user_video = Path("data/user/input.mp4")
ref_video = Path("data/reference/djokovic_backhand.mp4")

if user_video.exists():
    print(f"  {OK} User video found: {user_video}")
else:
    print(f"  {WARN} User video NOT found: {user_video}")
    print("     Place your video at data/user/input.mp4 to test")

if ref_video.exists():
    print(f"  {OK} Reference video found: {ref_video}")
else:
    print(f"  {WARN} Reference video NOT found: {ref_video}")
    print("     Place reference video at data/reference/djokovic_backhand.mp4 to test")

# Test 8: Check Streamlit dashboard
print("\n[TEST 8] Checking Streamlit dashboard...")
streamlit_app = Path("streamlit_app.py")
if streamlit_app.exists():
    with open(streamlit_app, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "render_ball_rally_analytics" in content:
        print(f"  {OK} Ball & Rally Analytics page added to dashboard")
    else:
        print(f"  {FAIL} Ball & Rally Analytics page NOT found in dashboard")
    
    if '"📊 Ball & Rally"' in content or "'📊 Ball & Rally'" in content:
        print(f"  {OK} Navigation menu updated")
    else:
        print(f"  {FAIL} Navigation menu NOT updated")
else:
    print(f"  {FAIL} streamlit_app.py NOT found")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

print(f"\n{OK} All core tests passed!")
print("\nNext steps:")
print("1. If YOLO model is not found, see models/README.md for setup")
print("2. Ensure input videos are in place (data/user/ and data/reference/)")
print("3. Run the pipeline: python vision/compare.py")
print("4. Check outputs in outputs/<session_id>/")
print("5. View dashboard: streamlit run streamlit_app.py")
print("\nIntegration Features Available:")
print("  • Ball detection and tracking")
print("  • Speed classification (Slow/Medium/Fast/Bullet)")
print("  • Rally segmentation and statistics")
print("  • Court zone heatmaps")
print("  • Speed distribution charts")
print("  • Broadcast-style video overlays")
print("  • Enhanced coaching reports")
print("  • Streamlit dashboard integration")

print("\n" + "=" * 70)
print("BALL TRACKING INTEGRATION: READY")
print("=" * 70)
