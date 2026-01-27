"""
ball_tracking_models.py
Data structures for ball tracking and rally analytics.
Adapted from Tennis Pro Analytics repository.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from enum import Enum


class SpeedCategory(Enum):
    """Ball speed classifications."""
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    BULLET = "bullet"
    UNKNOWN = "unknown"


class CourtZone(Enum):
    """Court spatial zones for shot placement analysis."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    NET = "net"
    MID = "mid"
    BASELINE = "baseline"


@dataclass
class Ball:
    """Represents a single ball detection with metadata."""
    frame_id: int
    x: int
    y: int
    speed: float = 0.0
    speed_category: str = "unknown"
    timestamp: float = 0.0
    confidence: float = 1.0
    
    def __post_init__(self):
        """Classify speed after initialization."""
        if self.speed_category == "unknown" and self.speed > 0:
            self.speed_category = SpeedClassifier.classify(self.speed)


@dataclass
class Player:
    """Represents player position and movement state."""
    frame_id: int
    x: int
    y: int
    velocity: float = 0.0
    landmarks: Optional[object] = None  # MediaPipe landmarks
    
    def get_position(self) -> Tuple[int, int]:
        """Return (x, y) position tuple."""
        return (self.x, self.y)


@dataclass
class PlayerMetrics:
    """Tracks player movement and performance across session."""
    total_distance: float = 0.0
    max_speed: float = 0.0
    avg_speed: float = 0.0
    positions: List[Tuple[int, int]] = field(default_factory=list)
    movement_samples: int = 0
    
    def add_position(self, x: int, y: int, speed: float = 0.0):
        """Add a position sample and update metrics."""
        self.positions.append((x, y))
        self.total_distance += speed
        self.movement_samples += 1
        
        if speed > self.max_speed:
            self.max_speed = speed
        
        if self.movement_samples > 0:
            self.avg_speed = self.total_distance / self.movement_samples


@dataclass
class RallyStatistics:
    """Comprehensive rally and match statistics."""
    total_frames: int = 0
    ball_detections: int = 0
    avg_ball_speed: float = 0.0
    max_ball_speed: float = 0.0
    speed_distribution: Dict[str, int] = field(default_factory=lambda: {
        "slow": 0,
        "medium": 0,
        "fast": 0,
        "bullet": 0
    })
    court_zones_hit: Dict[str, int] = field(default_factory=lambda: {
        "left": 0,
        "center": 0,
        "right": 0,
        "net": 0,
        "mid": 0,
        "baseline": 0
    })
    rally_count: int = 0
    avg_rally_length: float = 0.0
    longest_rally: int = 0
    
    def update_speed_stats(self, speed: float):
        """Update speed statistics with new ball detection."""
        # Update max
        if speed > self.max_ball_speed:
            self.max_ball_speed = speed
        
        # Update average (incremental)
        if self.ball_detections > 0:
            self.avg_ball_speed = (
                (self.avg_ball_speed * self.ball_detections + speed) / 
                (self.ball_detections + 1)
            )
        else:
            self.avg_ball_speed = speed
        
        self.ball_detections += 1
        
        # Update distribution
        category = SpeedClassifier.classify(speed)
        if category in self.speed_distribution:
            self.speed_distribution[category] += 1
    
    def update_court_zone(self, h_zone: str, v_zone: str):
        """Update court zone hit counts."""
        if h_zone in self.court_zones_hit:
            self.court_zones_hit[h_zone] += 1
        if v_zone in self.court_zones_hit:
            self.court_zones_hit[v_zone] += 1
    
    def get_speed_distribution_percentages(self) -> Dict[str, float]:
        """Get speed distribution as percentages."""
        total = sum(self.speed_distribution.values())
        if total == 0:
            return {k: 0.0 for k in self.speed_distribution.keys()}
        
        return {
            category: (count / total) * 100
            for category, count in self.speed_distribution.items()
        }


@dataclass
class Rally:
    """Represents a single rally sequence."""
    rally_id: int
    start_frame: int
    end_frame: int
    ball_positions: List[Ball] = field(default_factory=list)
    shot_count: int = 0
    duration_seconds: float = 0.0
    avg_ball_speed: float = 0.0
    max_ball_speed: float = 0.0
    
    def add_ball(self, ball: Ball):
        """Add a ball detection to this rally."""
        self.ball_positions.append(ball)
        self.shot_count = len(self.ball_positions)
        
        # Update speed stats
        if ball.speed > self.max_ball_speed:
            self.max_ball_speed = ball.speed
        
        speeds = [b.speed for b in self.ball_positions if b.speed > 0]
        if speeds:
            self.avg_ball_speed = sum(speeds) / len(speeds)
    
    def finalize(self, fps: float):
        """Finalize rally statistics."""
        self.end_frame = self.ball_positions[-1].frame_id if self.ball_positions else self.start_frame
        self.duration_seconds = (self.end_frame - self.start_frame) / fps if fps > 0 else 0


@dataclass
class AnalysisSession:
    """Complete analysis session data."""
    video_source: str = ""
    analysis_date: str = ""
    duration_seconds: float = 0.0
    fps: int = 0
    resolution: Tuple[int, int] = (0, 0)
    rally_stats: RallyStatistics = field(default_factory=RallyStatistics)
    player_metrics: PlayerMetrics = field(default_factory=PlayerMetrics)
    ball_trajectory: List[Ball] = field(default_factory=list)
    rallies: List[Rally] = field(default_factory=list)
    
    def get_summary_dict(self) -> Dict:
        """Export session data as dictionary for reports."""
        return {
            'video_info': {
                'source': self.video_source,
                'date': self.analysis_date,
                'duration': self.duration_seconds,
                'fps': self.fps,
                'resolution': f"{self.resolution[0]}x{self.resolution[1]}"
            },
            'ball_stats': {
                'total_detections': self.rally_stats.ball_detections,
                'avg_speed': self.rally_stats.avg_ball_speed,
                'max_speed': self.rally_stats.max_ball_speed,
                'speed_distribution': self.rally_stats.get_speed_distribution_percentages()
            },
            'rally_stats': {
                'total_rallies': len(self.rallies),
                'avg_rally_length': self.rally_stats.avg_rally_length,
                'longest_rally': self.rally_stats.longest_rally
            },
            'player_stats': {
                'total_distance': self.player_metrics.total_distance,
                'max_speed': self.player_metrics.max_speed,
                'avg_speed': self.player_metrics.avg_speed
            }
        }


class SpeedClassifier:
    """Classifies ball speed into categories."""
    
    # Speed thresholds (in pixels per frame)
    THRESHOLDS = {
        'slow': (0, 8),
        'medium': (8, 20),
        'fast': (20, 35),
        'bullet': (35, float('inf'))
    }
    
    @staticmethod
    def classify(speed: float) -> str:
        """Classify speed into category."""
        if speed < 0:
            return "unknown"
        
        for category, (min_val, max_val) in SpeedClassifier.THRESHOLDS.items():
            if min_val <= speed < max_val:
                return category
        
        return "bullet"
    
    @staticmethod
    def get_category_enum(speed: float) -> SpeedCategory:
        """Get SpeedCategory enum for given speed."""
        category_str = SpeedClassifier.classify(speed)
        try:
            return SpeedCategory(category_str)
        except ValueError:
            return SpeedCategory.UNKNOWN


class CourtZoneAnalyzer:
    """Analyzes ball positions relative to court zones."""
    
    @staticmethod
    def get_zone(x: int, y: int, frame_width: int, frame_height: int) -> Tuple[str, str]:
        """
        Determine horizontal and vertical court zones for a ball position.
        
        Returns:
            Tuple of (horizontal_zone, vertical_zone)
        """
        # Horizontal zones
        if x < frame_width * 0.33:
            h_zone = "left"
        elif x < frame_width * 0.66:
            h_zone = "center"
        else:
            h_zone = "right"
        
        # Vertical zones
        if y < frame_height * 0.33:
            v_zone = "net"
        elif y < frame_height * 0.66:
            v_zone = "mid"
        else:
            v_zone = "baseline"
        
        return h_zone, v_zone
    
    @staticmethod
    def get_zone_enums(x: int, y: int, frame_width: int, frame_height: int) -> Tuple[CourtZone, CourtZone]:
        """Get CourtZone enums for position."""
        h_zone, v_zone = CourtZoneAnalyzer.get_zone(x, y, frame_width, frame_height)
        return CourtZone(h_zone), CourtZone(v_zone)


def segment_rallies(ball_trajectory: List[Ball], fps: float, gap_threshold: float = 2.0) -> List[Rally]:
    """
    Segment ball trajectory into rally sequences.
    
    Args:
        ball_trajectory: List of Ball objects in chronological order
        fps: Video frame rate
        gap_threshold: Maximum time gap (seconds) to consider same rally
    
    Returns:
        List of Rally objects
    """
    if not ball_trajectory:
        return []
    
    rallies = []
    current_rally = None
    rally_id = 0
    gap_threshold_frames = gap_threshold * fps
    
    for ball in ball_trajectory:
        # Start new rally if needed
        if current_rally is None:
            rally_id += 1
            current_rally = Rally(
                rally_id=rally_id,
                start_frame=ball.frame_id,
                end_frame=ball.frame_id
            )
            current_rally.add_ball(ball)
        else:
            # Check if this ball belongs to current rally
            frame_gap = ball.frame_id - current_rally.ball_positions[-1].frame_id
            
            if frame_gap <= gap_threshold_frames:
                # Continue current rally
                current_rally.add_ball(ball)
            else:
                # Finalize current rally and start new one
                current_rally.finalize(fps)
                rallies.append(current_rally)
                
                rally_id += 1
                current_rally = Rally(
                    rally_id=rally_id,
                    start_frame=ball.frame_id,
                    end_frame=ball.frame_id
                )
                current_rally.add_ball(ball)
    
    # Finalize last rally
    if current_rally:
        current_rally.finalize(fps)
        rallies.append(current_rally)
    
    return rallies


def compute_rally_statistics(rallies: List[Rally]) -> Dict:
    """
    Compute aggregate statistics from rally list.
    
    Returns:
        Dictionary with rally statistics
    """
    if not rallies:
        return {
            'total_rallies': 0,
            'avg_rally_length': 0.0,
            'longest_rally': 0,
            'shortest_rally': 0,
            'avg_duration': 0.0
        }
    
    rally_lengths = [r.shot_count for r in rallies]
    durations = [r.duration_seconds for r in rallies]
    
    return {
        'total_rallies': len(rallies),
        'avg_rally_length': sum(rally_lengths) / len(rally_lengths) if rally_lengths else 0,
        'longest_rally': max(rally_lengths) if rally_lengths else 0,
        'shortest_rally': min(rally_lengths) if rally_lengths else 0,
        'avg_duration': sum(durations) / len(durations) if durations else 0
    }
