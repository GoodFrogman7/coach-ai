"""
ball_tracking.py

Optional YOLO-based ball detection and trajectory statistics.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import cv2

def is_ball_tracking_available() -> bool:
    """Check if YOLO model is available for ball tracking."""
    model_path = Path("models/best.pt")
    return model_path.exists()


def run_ball_detection(video_path: str, model_path: str = "models/best.pt", fps: float = 30.0) -> List:
    """
    Run YOLOv8 ball tracking on video.
    
    Args:
        video_path: Path to video file
        model_path: Path to YOLO model weights
        fps: Video frame rate (for timestamp calculation)
    
    Returns:
        List of Ball objects from ball_tracking_models
    """
    try:
        from ultralytics import YOLO
        from vision.ball_tracking_models import Ball
        import math
        
        if not Path(model_path).exists():
            print(f"  [WARN] Ball tracking model not found at {model_path}")
            return []
        
        print("\n[BALL TRACKING] Initializing YOLOv8...")
        model = YOLO(model_path)
        
        # Open video to get dimensions
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"  [WARN] Cannot open video for ball tracking: {video_path}")
            return []
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        print(f"[BALL TRACKING] Detecting balls in {total_frames} frames...")
        
        # Run detection with tracking
        results = model.track(str(video_path), persist=True, conf=0.3, verbose=False)
        
        ball_trajectory = []
        prev_ball = None
        
        for frame_idx, result in enumerate(results):
            if frame_idx % 50 == 0:
                progress = (frame_idx / total_frames) * 100
                print(f"  Ball tracking progress: {progress:.1f}%", end='\r')
            
            # Get best detection for this frame
            best_detection = None
            best_conf = 0
            
            if result.boxes is not None:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    if conf > best_conf:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                        best_detection = (cx, cy, conf)
                        best_conf = conf
            
            if best_detection:
                cx, cy, conf = best_detection
                
                # Calculate speed from previous frame
                speed = 0.0
                if prev_ball:
                    dx = cx - prev_ball.x
                    dy = cy - prev_ball.y
                    speed = math.sqrt(dx**2 + dy**2)
                
                # Create Ball object
                ball = Ball(
                    frame_id=frame_idx + 1,  # 1-indexed
                    x=cx,
                    y=cy,
                    speed=speed,
                    timestamp=(frame_idx + 1) / fps,
                    confidence=conf
                )
                
                ball_trajectory.append(ball)
                prev_ball = ball
        
        print(f"\n[BALL TRACKING] Detected {len(ball_trajectory)} ball positions")
        return ball_trajectory
        
    except ImportError:
        print("  [WARN] ultralytics not installed. Ball tracking disabled.")
        print("  Install with: pip install ultralytics")
        return []
    except Exception as e:
        print(f"  [WARN] Ball tracking failed: {e}")
        return []


def compute_ball_statistics(ball_trajectory: List) -> Dict:
    """
    Compute statistics from ball trajectory.
    
    Args:
        ball_trajectory: List of Ball objects
    
    Returns:
        Dictionary with ball statistics
    """
    from vision.ball_tracking_models import RallyStatistics, CourtZoneAnalyzer
    
    if not ball_trajectory:
        return None
    
    stats = RallyStatistics()
    stats.total_frames = len(ball_trajectory)
    stats.ball_detections = len(ball_trajectory)
    
    # Get frame dimensions from first ball (assuming consistent video)
    # Note: We'd need to pass frame dimensions, for now use placeholders
    frame_width = 1920  # Will be updated in run_pipeline
    frame_height = 1080
    
    for ball in ball_trajectory:
        # Update speed stats
        if ball.speed > 0:
            stats.update_speed_stats(ball.speed)
        
        # Update court zones
        h_zone, v_zone = CourtZoneAnalyzer.get_zone(
            ball.x, ball.y, frame_width, frame_height
        )
        stats.update_court_zone(h_zone, v_zone)
    
    return {
        'total_detections': stats.ball_detections,
        'avg_speed': stats.avg_ball_speed,
        'max_speed': stats.max_ball_speed,
        'speed_distribution': stats.speed_distribution,
        'court_zones': stats.court_zones_hit
    }

