"""
overlay_pose.py
Draw skeleton/keypoints on video frames and save output video with overlay.
"""

import cv2
import mediapipe as mp
from pathlib import Path


# MediaPipe Pose connections for drawing skeleton
POSE_CONNECTIONS = [
    (11, 12),  # shoulders
    (11, 13), (13, 15),  # left arm
    (12, 14), (14, 16),  # right arm
    (11, 23), (12, 24),  # torso sides
    (23, 24),  # hips
    (23, 25), (25, 27),  # left leg
    (24, 26), (26, 28),  # right leg
    (15, 17), (15, 19), (15, 21),  # left hand
    (16, 18), (16, 20), (16, 22),  # right hand
    (27, 29), (27, 31),  # left foot
    (28, 30), (28, 32),  # right foot
]

# Key landmarks for visualization emphasis
KEY_LANDMARKS = {
    11: "L_SHOULDER",
    12: "R_SHOULDER", 
    13: "L_ELBOW",
    14: "R_ELBOW",
    15: "L_WRIST",
    16: "R_WRIST",
    23: "L_HIP",
    24: "R_HIP",
    25: "L_KNEE",
    26: "R_KNEE",
    27: "L_ANKLE",
    28: "R_ANKLE",
}


def draw_pose_on_frame(frame, landmarks, draw_connections=True):
    """
    Draw pose landmarks and skeleton on a single frame.
    
    Args:
        frame: BGR image (numpy array)
        landmarks: List of (x, y, visibility) for each landmark
        draw_connections: Whether to draw skeleton lines
        
    Returns:
        Frame with pose overlay
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    # Draw connections (skeleton)
    if draw_connections:
        for start_idx, end_idx in POSE_CONNECTIONS:
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                start_lm = landmarks[start_idx]
                end_lm = landmarks[end_idx]
                
                # Only draw if both landmarks are visible enough
                if start_lm[2] > 0.5 and end_lm[2] > 0.5:
                    start_pt = (int(start_lm[0] * w), int(start_lm[1] * h))
                    end_pt = (int(end_lm[0] * w), int(end_lm[1] * h))
                    cv2.line(overlay, start_pt, end_pt, (0, 255, 128), 2)
    
    # Draw landmarks
    for idx, (x, y, vis) in enumerate(landmarks):
        if vis > 0.5:
            pt = (int(x * w), int(y * h))
            
            # Key landmarks get larger circles
            if idx in KEY_LANDMARKS:
                cv2.circle(overlay, pt, 6, (0, 140, 255), -1)
                cv2.circle(overlay, pt, 6, (255, 255, 255), 1)
            else:
                cv2.circle(overlay, pt, 3, (255, 200, 0), -1)
    
    return overlay


def create_overlay_video(video_path: str, output_path: str) -> None:
    """
    Process video, add pose overlay, and save result.
    
    Args:
        video_path: Path to input video
        output_path: Path for output video with overlay
    """
    mp_pose = mp.solutions.pose
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Setup video writer
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    frame_count = 0
    
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
            
            # Process frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)
            
            if results.pose_landmarks:
                # Extract landmarks as list
                landmarks = [
                    (lm.x, lm.y, lm.visibility)
                    for lm in results.pose_landmarks.landmark
                ]
                frame = draw_pose_on_frame(frame, landmarks)
            
            # Add frame counter
            cv2.putText(
                frame, 
                f"Frame: {frame_count}", 
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.7, 
                (255, 255, 255), 
                2
            )
            
            out.write(frame)
            frame_count += 1
            
            if frame_count % 30 == 0:
                print(f"Processed {frame_count}/{total_frames} frames...")
    
    cap.release()
    out.release()
    print(f"Saved overlay video to: {output_path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python overlay_pose.py <input_video> <output_video>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_path = sys.argv[2]
    
    print(f"Creating overlay video...")
    create_overlay_video(video_path, output_path)

