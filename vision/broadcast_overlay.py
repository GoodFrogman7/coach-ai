"""
broadcast_overlay.py
Broadcast-style visualization and overlay rendering for tennis analysis.
Adapted from Tennis Pro Analytics repository.
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional
from collections import deque
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

from vision.ball_tracking_models import Ball, RallyStatistics, SpeedClassifier


class VisualizationEngine:
    """Handles all professional-grade visualizations for tennis analysis."""
    
    # Color Palette (BGR Format for OpenCV)
    COLORS = {
        'primary': (255, 165, 0),      # Orange
        'secondary': (0, 255, 255),    # Cyan
        'accent': (147, 20, 255),      # Pink
        'success': (0, 255, 100),      # Green
        'warning': (0, 200, 255),      # Yellow
        'danger': (0, 0, 255),         # Red
        'dark': (30, 30, 30),          # Dark Gray
        'light': (220, 220, 220),      # Light Gray
        'white': (255, 255, 255),
        'black': (0, 0, 0),
    }
    
    # Speed Category Colors
    SPEED_COLORS = {
        'slow': (0, 255, 100),         # Green
        'medium': (0, 255, 255),       # Yellow
        'fast': (0, 165, 255),         # Orange
        'bullet': (0, 0, 255),         # Red
        'unknown': (128, 128, 128),    # Gray
    }
    
    @staticmethod
    def get_speed_category_color(speed: float) -> Tuple[str, Tuple[int, int, int]]:
        """Classify speed and return category with corresponding color."""
        category = SpeedClassifier.classify(speed)
        color = VisualizationEngine.SPEED_COLORS.get(category, VisualizationEngine.SPEED_COLORS['unknown'])
        return category.upper(), color
    
    @staticmethod
    def draw_gradient_line(img, pt1, pt2, color1, color2, thickness=3):
        """Draw a gradient line between two points."""
        steps = 10
        for i in range(steps):
            t = i / steps
            x = int(pt1[0] + t * (pt2[0] - pt1[0]))
            y = int(pt1[1] + t * (pt2[1] - pt1[1]))
            x_next = int(pt1[0] + (t + 1/steps) * (pt2[0] - pt1[0]))
            y_next = int(pt1[1] + (t + 1/steps) * (pt2[1] - pt1[1]))
            
            color = tuple(int(c1 + t * (c2 - c1)) for c1, c2 in zip(color1, color2))
            cv2.line(img, (x, y), (x_next, y_next), color, thickness)
    
    @staticmethod
    def draw_dashboard_panel(img, x, y, w, h, title, opacity=0.85):
        """Draw a semi-transparent dashboard panel with title."""
        overlay = img.copy()
        
        # Main Panel Background
        cv2.rectangle(overlay, (x, y), (x+w, y+h), 
                     VisualizationEngine.COLORS['dark'], -1)
        
        # Border
        cv2.rectangle(overlay, (x, y), (x+w, y+h), 
                     VisualizationEngine.COLORS['primary'], 2)
        
        # Title Bar
        cv2.rectangle(overlay, (x, y), (x+w, y+30), 
                     VisualizationEngine.COLORS['primary'], -1)
        
        # Title Text
        cv2.putText(overlay, title, (x+10, y+22), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                   VisualizationEngine.COLORS['white'], 2)
        
        cv2.addWeighted(overlay, opacity, img, 1-opacity, 0, img)
        return img
    
    @staticmethod
    def draw_stat_row(img, x, y, label, value, color=None):
        """Draw a label-value pair in a stat panel."""
        if color is None:
            color = VisualizationEngine.COLORS['light']
        
        cv2.putText(img, f"{label}:", (x, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                   VisualizationEngine.COLORS['light'], 1)
        cv2.putText(img, str(value), (x+120, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    @staticmethod
    def draw_speed_gauge(img, x, y, speed, max_speed=50):
        """Draw a horizontal speed gauge."""
        gauge_w, gauge_h = 150, 20
        
        # Background
        cv2.rectangle(img, (x, y), (x+gauge_w, y+gauge_h), 
                     VisualizationEngine.COLORS['dark'], -1)
        cv2.rectangle(img, (x, y), (x+gauge_w, y+gauge_h), 
                     VisualizationEngine.COLORS['light'], 1)
        
        # Fill based on speed
        fill_w = int((min(speed, max_speed) / max_speed) * gauge_w)
        _, color = VisualizationEngine.get_speed_category_color(speed)
        if fill_w > 2:
            cv2.rectangle(img, (x+2, y+2), (x+fill_w-2, y+gauge_h-2), color, -1)
        
        # Speed Text
        cv2.putText(img, f"{speed:.1f} px/f", (x+gauge_w+10, y+15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    @staticmethod
    def draw_mini_heatmap(img, positions, x, y, w, h, frame_w, frame_h):
        """Draw a mini heatmap visualization."""
        if not positions:
            return
        
        # Create mini heatmap
        heatmap = np.zeros((h, w), dtype=np.float32)
        
        for px, py in positions:
            # Scale position to mini map
            mx = int((px / frame_w) * w)
            my = int((py / frame_h) * h)
            mx = max(0, min(w-1, mx))
            my = max(0, min(h-1, my))
            
            # Add gaussian blob
            cv2.circle(heatmap, (mx, my), 5, 1.0, -1)
        
        # Blur for smooth heatmap
        heatmap = cv2.GaussianBlur(heatmap, (15, 15), 0)
        
        # Normalize and colorize
        if heatmap.max() > 0:
            heatmap = (heatmap / heatmap.max() * 255).astype(np.uint8)
        else:
            heatmap = heatmap.astype(np.uint8)
        
        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        
        # Draw on main image
        img[y:y+h, x:x+w] = cv2.addWeighted(
            img[y:y+h, x:x+w], 0.3, heatmap_color, 0.7, 0
        )
        
        # Border
        cv2.rectangle(img, (x, y), (x+w, y+h), 
                     VisualizationEngine.COLORS['primary'], 2)


def draw_ball_trajectory(img: np.ndarray, ball_history: deque, viz: VisualizationEngine):
    """Draw ball trajectory with speed-based coloring."""
    if len(ball_history) < 2:
        return
    
    points = list(ball_history)
    
    for i in range(1, len(points)):
        pt1 = (points[i-1].x, points[i-1].y)
        pt2 = (points[i].x, points[i].y)
        
        # Get color based on speed
        _, color = viz.get_speed_category_color(points[i].speed)
        
        # Fade effect based on age
        alpha = (i / len(points))
        thickness = max(2, int(4 * alpha))
        
        cv2.line(img, pt1, pt2, color, thickness)
    
    # Draw current ball with glow effect
    if points:
        current = points[-1]
        # Outer glow
        cv2.circle(img, (current.x, current.y), 15, 
                  viz.COLORS['white'], 2)
        # Inner ball
        cv2.circle(img, (current.x, current.y), 8, 
                  viz.COLORS['primary'], -1)


def draw_rally_counter(img: np.ndarray, rally_count: int, shot_count: int):
    """Draw rally counter overlay."""
    h, w = img.shape[:2]
    
    # Position in top center
    text = f"RALLY #{rally_count} | SHOT: {shot_count}"
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    tx = (w - text_size[0]) // 2
    ty = 60
    
    # Background
    cv2.rectangle(img, (tx-10, ty-25), (tx+text_size[0]+10, ty+5),
                 VisualizationEngine.COLORS['dark'], -1)
    cv2.rectangle(img, (tx-10, ty-25), (tx+text_size[0]+10, ty+5),
                 VisualizationEngine.COLORS['accent'], 2)
    
    # Text
    cv2.putText(img, text, (tx, ty),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7,
               VisualizationEngine.COLORS['white'], 2)


def draw_analytics_overlay(
    frame: np.ndarray,
    frame_count: int,
    rally_stats: RallyStatistics,
    current_speed: float,
    ball_history: deque,
    viz: VisualizationEngine
):
    """Draw complete analytics overlay on frame."""
    h, w = frame.shape[:2]
    
    # === TOP LEFT: Live Stats Panel ===
    viz.draw_dashboard_panel(frame, 10, 10, 250, 180, "📊 LIVE ANALYTICS")
    
    speed_category, speed_color = viz.get_speed_category_color(current_speed)
    
    y_offset = 55
    stats = [
        ("Frame", f"#{frame_count}"),
        ("Ball Detections", rally_stats.ball_detections),
        ("Current Speed", f"{current_speed:.1f} px/f"),
        ("Speed Class", speed_category),
        ("Max Speed", f"{rally_stats.max_ball_speed:.1f} px/f"),
        ("Avg Speed", f"{rally_stats.avg_ball_speed:.1f} px/f"),
    ]
    
    for label, value in stats:
        color = viz.COLORS['light']
        if label == "Speed Class":
            color = speed_color
        viz.draw_stat_row(frame, 20, y_offset, label, value, color)
        y_offset += 22
    
    # === TOP RIGHT: Speed Distribution ===
    viz.draw_dashboard_panel(frame, w-220, 10, 210, 140, "⚡ SPEED DISTRIBUTION")
    
    dist = rally_stats.speed_distribution
    total = sum(dist.values()) or 1
    
    y_offset = 50
    for category in ['slow', 'medium', 'fast', 'bullet']:
        count = dist[category]
        pct = (count / total) * 100
        
        # Draw bar
        bar_w = int((count / total) * 150) if total > 0 else 0
        if bar_w > 0:
            cv2.rectangle(frame, (w-210, y_offset-12), 
                         (w-210+bar_w, y_offset+2),
                         viz.SPEED_COLORS[category], -1)
        
        # Label
        cv2.putText(frame, f"{category.upper()}: {pct:.0f}%", 
                   (w-210, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                   viz.COLORS['white'], 1)
        
        y_offset += 25
    
    # === BOTTOM LEFT: Speed Gauge ===
    viz.draw_dashboard_panel(frame, 10, h-80, 250, 70, "🎯 SPEED METER")
    viz.draw_speed_gauge(frame, 20, h-45, current_speed)
    
    # === BOTTOM RIGHT: Mini Heatmap ===
    if len(ball_history) > 5:
        positions = [(bp.x, bp.y) for bp in ball_history]
        viz.draw_mini_heatmap(frame, positions, 
                             w-170, h-130, 160, 120, w, h)
        cv2.putText(frame, "BALL HEATMAP", (w-165, h-135),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                   viz.COLORS['primary'], 1)


def create_broadcast_overlay(
    video_path: str,
    ball_trajectory: List[Ball],
    output_path: str,
    rally_stats: Optional[RallyStatistics] = None,
    fps: Optional[int] = None
) -> str:
    """
    Create a video with broadcast-style overlay graphics.
    
    Args:
        video_path: Path to input video
        ball_trajectory: List of Ball objects with detection data
        output_path: Path for output video
        rally_stats: Optional pre-computed rally statistics
        fps: Override FPS (uses video fps if None)
    
    Returns:
        Path to output video
    """
    # Open input video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    # Get video properties
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_fps = int(cap.get(cv2.CAP_PROP_FPS))
    if fps is None:
        fps = video_fps
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Create output writer with H.264 codec (browser-compatible) with fallbacks
    fourcc = None
    for codec in ['avc1', 'H264', 'X264', 'mp4v']:
        try:
            test_fourcc = cv2.VideoWriter_fourcc(*codec)
            test_writer = cv2.VideoWriter(output_path, test_fourcc, fps, (w, h))
            if test_writer.isOpened():
                fourcc = test_fourcc
                test_writer.release()
                if codec == 'mp4v':
                    print(f"  [WARNING] Using {codec} codec - videos may not play in browser")
                else:
                    print(f"  [INFO] Using {codec} codec for browser-compatible broadcast video")
                break
            test_writer.release()
        except:
            continue
    
    if fourcc is None:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        print("  [WARNING] No H.264 codec available, using mp4v - videos may not play in browser")
    
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
    
    # Initialize visualization engine
    viz = VisualizationEngine()
    
    # Initialize stats if not provided
    if rally_stats is None:
        rally_stats = RallyStatistics()
    
    # Create ball lookup by frame
    ball_by_frame = {ball.frame_id: ball for ball in ball_trajectory}
    ball_history = deque(maxlen=50)
    
    frame_count = 0
    current_speed = 0.0
    
    print("\n🎬 Creating broadcast overlay...")
    print(f"   Resolution: {w}x{h} @ {fps}fps")
    print(f"   Total Frames: {total_frames}")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Progress indicator
        if frame_count % 30 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"   Progress: {progress:.1f}% ({frame_count}/{total_frames})", end='\r')
        
        # Get ball data for this frame
        if frame_count in ball_by_frame:
            ball = ball_by_frame[frame_count]
            ball_history.append(ball)
            current_speed = ball.speed
        
        # Draw overlay frame
        overlay_frame = frame.copy()
        
        # Draw ball trajectory
        draw_ball_trajectory(overlay_frame, ball_history, viz)
        
        # Draw analytics panels
        draw_analytics_overlay(
            overlay_frame,
            frame_count,
            rally_stats,
            current_speed,
            ball_history,
            viz
        )
        
        # Write frame
        out.write(overlay_frame)
    
    # Cleanup
    cap.release()
    out.release()
    
    print(f"\n✅ Broadcast overlay created: {output_path}")
    return output_path


def generate_player_heatmap(
    positions: List[Tuple[int, int]],
    frame_width: int,
    frame_height: int,
    output_path: str,
    title: str = "Player Movement Heatmap"
) -> str:
    """
    Generate a full-size player movement heatmap.
    
    Args:
        positions: List of (x, y) positions
        frame_width: Video frame width
        frame_height: Video frame height
        output_path: Path to save heatmap image
        title: Title for the heatmap
    
    Returns:
        Path to saved heatmap
    """
    if not positions:
        print("⚠️  No positions provided for heatmap")
        return None
    
    # Create heatmap matrix
    heatmap = np.zeros((frame_height, frame_width), dtype=np.float32)
    
    # Add gaussian blobs for each position
    for x, y in positions:
        x = max(0, min(frame_width-1, int(x)))
        y = max(0, min(frame_height-1, int(y)))
        cv2.circle(heatmap, (x, y), 20, 1.0, -1)
    
    # Gaussian blur for smooth heatmap
    heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot heatmap
    im = ax.imshow(heatmap, cmap='hot', interpolation='gaussian', aspect='auto')
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_xlabel('Court Width', fontsize=12)
    ax.set_ylabel('Court Length', fontsize=12)
    ax.invert_yaxis()  # Image coordinates
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Movement Density', rotation=270, labelpad=20, fontsize=12)
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Player heatmap saved: {output_path}")
    return output_path


def generate_court_zones_heatmap(
    ball_trajectory: List[Ball],
    frame_width: int,
    frame_height: int,
    output_path: str,
    title: str = "Shot Placement Heatmap"
) -> str:
    """
    Generate court zone heatmap showing shot placement.
    
    Args:
        ball_trajectory: List of Ball objects
        frame_width: Video frame width
        frame_height: Video frame height
        output_path: Path to save heatmap image
        title: Title for the heatmap
    
    Returns:
        Path to saved heatmap
    """
    if not ball_trajectory:
        print("⚠️  No ball trajectory provided for heatmap")
        return None
    
    # Extract positions
    positions = [(ball.x, ball.y) for ball in ball_trajectory]
    
    # Create heatmap matrix
    heatmap = np.zeros((frame_height, frame_width), dtype=np.float32)
    
    # Add points for ball positions
    for x, y in positions:
        x = max(0, min(frame_width-1, int(x)))
        y = max(0, min(frame_height-1, int(y)))
        cv2.circle(heatmap, (x, y), 15, 1.0, -1)
    
    # Gaussian blur
    heatmap = cv2.GaussianBlur(heatmap, (31, 31), 0)
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot heatmap
    im = ax.imshow(heatmap, cmap='YlOrRd', interpolation='gaussian', aspect='auto')
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_xlabel('Court Width', fontsize=12)
    ax.set_ylabel('Court Length', fontsize=12)
    ax.invert_yaxis()
    
    # Add grid lines for court zones
    ax.axvline(x=frame_width * 0.33, color='white', linestyle='--', alpha=0.5, linewidth=1)
    ax.axvline(x=frame_width * 0.66, color='white', linestyle='--', alpha=0.5, linewidth=1)
    ax.axhline(y=frame_height * 0.33, color='white', linestyle='--', alpha=0.5, linewidth=1)
    ax.axhline(y=frame_height * 0.66, color='white', linestyle='--', alpha=0.5, linewidth=1)
    
    # Zone labels
    zones = [
        ("LEFT\nNET", 0.165, 0.165),
        ("CENTER\nNET", 0.5, 0.165),
        ("RIGHT\nNET", 0.835, 0.165),
        ("LEFT\nMID", 0.165, 0.5),
        ("CENTER\nMID", 0.5, 0.5),
        ("RIGHT\nMID", 0.835, 0.5),
        ("LEFT\nBASE", 0.165, 0.835),
        ("CENTER\nBASE", 0.5, 0.835),
        ("RIGHT\nBASE", 0.835, 0.835),
    ]
    
    for label, x_frac, y_frac in zones:
        ax.text(x_frac * frame_width, y_frac * frame_height, label,
               ha='center', va='center', fontsize=9, color='white',
               bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Shot Density', rotation=270, labelpad=20, fontsize=12)
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Court zones heatmap saved: {output_path}")
    return output_path


def generate_speed_distribution_chart(
    rally_stats: RallyStatistics,
    output_path: str,
    title: str = "Ball Speed Distribution"
) -> str:
    """
    Generate a bar chart of speed distribution.
    
    Args:
        rally_stats: RallyStatistics object with speed data
        output_path: Path to save chart image
        title: Chart title
    
    Returns:
        Path to saved chart
    """
    # Get percentages
    percentages = rally_stats.get_speed_distribution_percentages()
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    categories = ['Slow', 'Medium', 'Fast', 'Bullet']
    values = [percentages[cat.lower()] for cat in categories]
    colors = ['#00FF64', '#00FFFF', '#00A5FF', '#0000FF']
    
    # Bar chart
    bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}%',
               ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_ylim(0, max(values) * 1.2 if values else 100)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Speed distribution chart saved: {output_path}")
    return output_path
