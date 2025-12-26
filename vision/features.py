"""
features.py
Compute biomechanical features per frame for tennis stroke analysis.
"""

import numpy as np
import pandas as pd
from pathlib import Path

# MediaPipe Pose landmark indices
LANDMARKS = {
    'LEFT_SHOULDER': 11,
    'RIGHT_SHOULDER': 12,
    'LEFT_ELBOW': 13,
    'RIGHT_ELBOW': 14,
    'LEFT_WRIST': 15,
    'RIGHT_WRIST': 16,
    'LEFT_HIP': 23,
    'RIGHT_HIP': 24,
    'LEFT_KNEE': 25,
    'RIGHT_KNEE': 26,
    'LEFT_ANKLE': 27,
    'RIGHT_ANKLE': 28,
}


def angle_between_points(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
    """
    Calculate angle at p2 formed by p1-p2-p3.
    
    Args:
        p1, p2, p3: Points as (x, y) or (x, y, z) arrays
        
    Returns:
        Angle in degrees
    """
    v1 = p1 - p2
    v2 = p3 - p2
    
    # Use only x, y for 2D angle calculation
    v1 = v1[:2]
    v2 = v2[:2]
    
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle = np.degrees(np.arccos(cos_angle))
    
    return angle


def angle_from_vertical(p1: np.ndarray, p2: np.ndarray) -> float:
    """
    Calculate angle of line p1->p2 from vertical axis.
    
    Args:
        p1, p2: Points as (x, y) arrays
        
    Returns:
        Angle in degrees (0 = vertical, positive = leaning right)
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    
    # Vertical is (0, -1) in image coords (y increases downward)
    angle = np.degrees(np.arctan2(dx, -dy))
    
    return angle


def get_landmark_coords(frame_data: pd.DataFrame, landmark_id: int) -> np.ndarray:
    """Extract (x, y, z) coordinates for a landmark from frame data."""
    row = frame_data[frame_data['landmark_id'] == landmark_id]
    if row.empty:
        return np.array([np.nan, np.nan, np.nan])
    return np.array([row['x'].values[0], row['y'].values[0], row['z'].values[0]])


def compute_frame_features(frame_data: pd.DataFrame) -> dict:
    """
    Compute all biomechanical features for a single frame.
    
    Args:
        frame_data: DataFrame with landmark data for one frame
        
    Returns:
        Dictionary of feature values
    """
    features = {}
    
    # Get all landmark positions
    l_shoulder = get_landmark_coords(frame_data, LANDMARKS['LEFT_SHOULDER'])
    r_shoulder = get_landmark_coords(frame_data, LANDMARKS['RIGHT_SHOULDER'])
    l_elbow = get_landmark_coords(frame_data, LANDMARKS['LEFT_ELBOW'])
    r_elbow = get_landmark_coords(frame_data, LANDMARKS['RIGHT_ELBOW'])
    l_wrist = get_landmark_coords(frame_data, LANDMARKS['LEFT_WRIST'])
    r_wrist = get_landmark_coords(frame_data, LANDMARKS['RIGHT_WRIST'])
    l_hip = get_landmark_coords(frame_data, LANDMARKS['LEFT_HIP'])
    r_hip = get_landmark_coords(frame_data, LANDMARKS['RIGHT_HIP'])
    l_knee = get_landmark_coords(frame_data, LANDMARKS['LEFT_KNEE'])
    r_knee = get_landmark_coords(frame_data, LANDMARKS['RIGHT_KNEE'])
    l_ankle = get_landmark_coords(frame_data, LANDMARKS['LEFT_ANKLE'])
    r_ankle = get_landmark_coords(frame_data, LANDMARKS['RIGHT_ANKLE'])
    
    # 1. Shoulder angles (hip-shoulder-elbow)
    features['left_shoulder_angle'] = angle_between_points(l_hip, l_shoulder, l_elbow)
    features['right_shoulder_angle'] = angle_between_points(r_hip, r_shoulder, r_elbow)
    
    # 2. Elbow angles (shoulder-elbow-wrist)
    features['left_elbow_angle'] = angle_between_points(l_shoulder, l_elbow, l_wrist)
    features['right_elbow_angle'] = angle_between_points(r_shoulder, r_elbow, r_wrist)
    
    # 3. Knee angles (hip-knee-ankle)
    features['left_knee_angle'] = angle_between_points(l_hip, l_knee, l_ankle)
    features['right_knee_angle'] = angle_between_points(r_hip, r_knee, r_ankle)
    
    # 4. Hip rotation proxy (angle between shoulder line and hip line)
    shoulder_vec = r_shoulder[:2] - l_shoulder[:2]
    hip_vec = r_hip[:2] - l_hip[:2]
    
    shoulder_angle = np.degrees(np.arctan2(shoulder_vec[1], shoulder_vec[0]))
    hip_angle = np.degrees(np.arctan2(hip_vec[1], hip_vec[0]))
    features['hip_rotation'] = shoulder_angle - hip_angle
    
    # 5. Spine lean (mid-shoulder to mid-hip vs vertical)
    mid_shoulder = (l_shoulder[:2] + r_shoulder[:2]) / 2
    mid_hip = (l_hip[:2] + r_hip[:2]) / 2
    features['spine_lean'] = angle_from_vertical(mid_hip, mid_shoulder)
    
    # 6. Stance width (ankle distance, normalized by hip width)
    hip_width = np.linalg.norm(r_hip[:2] - l_hip[:2])
    ankle_dist = np.linalg.norm(r_ankle[:2] - l_ankle[:2])
    features['stance_width_normalized'] = ankle_dist / (hip_width + 1e-8)
    
    # Additional: Wrist positions for impact detection
    features['left_wrist_x'] = l_wrist[0]
    features['left_wrist_y'] = l_wrist[1]
    features['right_wrist_x'] = r_wrist[0]
    features['right_wrist_y'] = r_wrist[1]
    
    return features


def compute_features_from_landmarks(landmarks_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute biomechanical features for all frames in a landmarks DataFrame.
    
    Args:
        landmarks_df: DataFrame with columns [frame, landmark_id, x, y, z, visibility]
        
    Returns:
        DataFrame with one row per frame and feature columns
    """
    frames = landmarks_df['frame'].unique()
    all_features = []
    
    for frame_num in sorted(frames):
        frame_data = landmarks_df[landmarks_df['frame'] == frame_num]
        features = compute_frame_features(frame_data)
        features['frame'] = frame_num
        all_features.append(features)
    
    df = pd.DataFrame(all_features)
    
    # Reorder columns
    cols = ['frame'] + [c for c in df.columns if c != 'frame']
    df = df[cols]
    
    return df


def compute_wrist_speed(features_df: pd.DataFrame, fps: float = 30.0) -> pd.DataFrame:
    """
    Compute wrist speed (for impact frame detection).
    
    Args:
        features_df: Features DataFrame with wrist positions
        fps: Video frames per second
        
    Returns:
        DataFrame with wrist speed columns added
    """
    df = features_df.copy()
    
    # Compute frame-to-frame displacement
    df['left_wrist_dx'] = df['left_wrist_x'].diff()
    df['left_wrist_dy'] = df['left_wrist_y'].diff()
    df['right_wrist_dx'] = df['right_wrist_x'].diff()
    df['right_wrist_dy'] = df['right_wrist_y'].diff()
    
    # Compute speed (displacement magnitude per frame, scaled by fps)
    df['left_wrist_speed'] = np.sqrt(df['left_wrist_dx']**2 + df['left_wrist_dy']**2) * fps
    df['right_wrist_speed'] = np.sqrt(df['right_wrist_dx']**2 + df['right_wrist_dy']**2) * fps
    
    # Combined wrist speed (for two-handed backhand)
    df['combined_wrist_speed'] = (df['left_wrist_speed'] + df['right_wrist_speed']) / 2
    
    return df


def segment_stroke_phases(features_df: pd.DataFrame, impact_frame: int) -> dict:
    """
    Segment stroke into movement phases using wrist speed and hip rotation.
    
    Phases:
    1. Preparation: Start -> early hip rotation
    2. Load: Hip rotation peak -> acceleration begins
    3. Contact: Peak acceleration -> impact
    4. Follow-through: Impact -> end
    
    Args:
        features_df: Features DataFrame with wrist speed and hip rotation
        impact_frame: Frame number of ball contact
        
    Returns:
        Dictionary with phase boundaries: {phase_name: (start_frame, end_frame)}
    """
    df = features_df.copy()
    
    # Handle missing data
    df['combined_wrist_speed'] = df['combined_wrist_speed'].fillna(0)
    df['hip_rotation'] = df['hip_rotation'].fillna(df['hip_rotation'].mean())
    
    # Smooth signals for better phase detection
    window = 5
    df['wrist_speed_smooth'] = df['combined_wrist_speed'].rolling(window=window, center=True).mean()
    df['hip_rotation_smooth'] = df['hip_rotation'].rolling(window=window, center=True).mean()
    df = df.fillna(method='bfill').fillna(method='ffill')
    
    total_frames = len(df)
    
    # Find key transition points
    # 1. Find preparation end: when hip rotation starts changing significantly
    hip_rotation_change = df['hip_rotation_smooth'].diff().abs()
    prep_search_end = min(impact_frame, int(total_frames * 0.7))
    prep_end_candidates = df[(df['frame'] < prep_search_end) & 
                              (hip_rotation_change > hip_rotation_change.quantile(0.6))]
    
    if len(prep_end_candidates) > 0:
        prep_end = int(prep_end_candidates.iloc[0]['frame'])
    else:
        prep_end = max(1, int(impact_frame * 0.3))
    
    # 2. Find load end: when wrist speed starts accelerating (20% of max speed)
    speed_threshold = df['wrist_speed_smooth'].max() * 0.2
    load_end_candidates = df[(df['frame'] > prep_end) & 
                              (df['frame'] < impact_frame) & 
                              (df['wrist_speed_smooth'] > speed_threshold)]
    
    if len(load_end_candidates) > 0:
        load_end = int(load_end_candidates.iloc[0]['frame'])
    else:
        load_end = max(prep_end + 1, int(impact_frame * 0.6))
    
    # 3. Contact phase: centered around impact frame
    contact_window = 5
    contact_start = max(load_end + 1, impact_frame - contact_window)
    contact_end = min(impact_frame + contact_window, total_frames - 1)
    
    # 4. Follow-through: from contact end to end of stroke
    follow_start = contact_end + 1
    follow_end = total_frames - 1
    
    phases = {
        'preparation': (0, prep_end),
        'load': (prep_end + 1, load_end),
        'contact': (contact_start, contact_end),
        'follow_through': (follow_start, follow_end)
    }
    
    return phases


def compute_phase_metrics(features_df: pd.DataFrame, phases: dict) -> dict:
    """
    Compute averaged biomechanical metrics for each phase.
    
    Args:
        features_df: Features DataFrame
        phases: Dictionary of phase boundaries
        
    Returns:
        Dictionary: {phase_name: {metric: value}}
    """
    phase_metrics = {}
    
    metrics_to_compute = [
        'left_shoulder_angle',
        'right_shoulder_angle',
        'left_elbow_angle',
        'right_elbow_angle',
        'left_knee_angle',
        'right_knee_angle',
        'hip_rotation',
        'spine_lean',
        'stance_width_normalized'
    ]
    
    for phase_name, (start_frame, end_frame) in phases.items():
        phase_data = features_df[
            (features_df['frame'] >= start_frame) & 
            (features_df['frame'] <= end_frame)
        ]
        
        if phase_data.empty:
            phase_metrics[phase_name] = {metric: np.nan for metric in metrics_to_compute}
            continue
        
        phase_metrics[phase_name] = {}
        for metric in metrics_to_compute:
            if metric in phase_data.columns:
                phase_metrics[phase_name][metric] = phase_data[metric].mean()
            else:
                phase_metrics[phase_name][metric] = np.nan
        
        # Add phase duration
        phase_metrics[phase_name]['duration_frames'] = end_frame - start_frame + 1
    
    return phase_metrics


def save_features(df: pd.DataFrame, output_path: str) -> None:
    """Save features DataFrame to CSV."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved features to {output_path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python features.py <landmarks_csv> [output_csv]")
        sys.exit(1)
    
    landmarks_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "features.csv"
    
    print(f"Computing features from: {landmarks_path}")
    landmarks_df = pd.read_csv(landmarks_path)
    features_df = compute_features_from_landmarks(landmarks_df)
    features_df = compute_wrist_speed(features_df)
    save_features(features_df, output_path)
    print(f"Computed {len(features_df)} frames of features")

