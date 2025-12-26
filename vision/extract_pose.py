"""
extract_pose.py
Load a video, run MediaPipe Pose, save per-frame landmarks to a DataFrame.
"""

import cv2
import mediapipe as mp
import pandas as pd
import numpy as np
from pathlib import Path


def extract_pose_landmarks(video_path: str) -> pd.DataFrame:
    """
    Extract pose landmarks from a video using MediaPipe Pose.
    
    Args:
        video_path: Path to input video file
        
    Returns:
        DataFrame with columns: frame, landmark_id, x, y, z, visibility
    """
    mp_pose = mp.solutions.pose
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    records = []
    frame_idx = 0
    
    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as pose:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)
            
            if results.pose_landmarks:
                for lm_id, landmark in enumerate(results.pose_landmarks.landmark):
                    records.append({
                        'frame': frame_idx,
                        'landmark_id': lm_id,
                        'x': landmark.x,
                        'y': landmark.y,
                        'z': landmark.z,
                        'visibility': landmark.visibility
                    })
            
            frame_idx += 1
    
    cap.release()
    
    df = pd.DataFrame(records)
    return df


def get_landmark_names() -> dict:
    """Return mapping of landmark IDs to names."""
    mp_pose = mp.solutions.pose
    return {lm.value: lm.name for lm in mp_pose.PoseLandmark}


def save_landmarks(df: pd.DataFrame, output_path: str) -> None:
    """Save landmarks DataFrame to CSV."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved landmarks to {output_path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python extract_pose.py <video_path> [output_csv]")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "landmarks.csv"
    
    print(f"Extracting pose from: {video_path}")
    df = extract_pose_landmarks(video_path)
    save_landmarks(df, output_path)
    print(f"Extracted {len(df)} landmark records from {df['frame'].nunique()} frames")

