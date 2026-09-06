"""
config_session.py

Session directory management and optional YAML configuration.

Extracted verbatim from compare.py during decomposition (logic unchanged).
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
# Optional: PyYAML for configuration support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

USER_VIDEO = "data/user/input.mp4"


REF_VIDEO = "data/reference/backhand/djokovic_backhand.mp4"


OUTPUT_USER_OVERLAY = "outputs/overlay_user.mp4"


OUTPUT_REF_OVERLAY = "outputs/overlay_ref.mp4"


OUTPUT_USER_FEATURES = "outputs/user_features.csv"


OUTPUT_REF_FEATURES = "outputs/ref_features.csv"


OUTPUT_REPORT = "outputs/report.md"


def generate_session_id() -> str:
    """
    Generate a unique session ID based on current timestamp.
    
    Returns:
        Session ID in format: YYYY-MM-DD_HH-MM-SS
    """
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def create_session_directory(session_id: str, base_dir: str = "outputs") -> Path:
    """
    Create a session-specific output directory.
    
    Args:
        session_id: Unique session identifier
        base_dir: Base output directory (default: "outputs")
        
    Returns:
        Path object for the session directory
        
    Raises:
        OSError: If directory creation fails (caller should handle)
    """
    session_dir = Path(base_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_session_paths(session_id: str = None, base_dir: str = "outputs") -> dict:
    """
    Get output file paths for a session.
    
    Args:
        session_id: Optional session ID. If None, uses base_dir directly (legacy mode)
        base_dir: Base output directory
        
    Returns:
        Dictionary of output paths
    """
    if session_id:
        output_dir = Path(base_dir) / session_id
    else:
        output_dir = Path(base_dir)
    
    return {
        'output_dir': output_dir,
        'overlay_user': output_dir / "overlay_user.mp4",
        'overlay_ref': output_dir / "overlay_ref.mp4",
        'features_user': output_dir / "user_features.csv",
        'features_ref': output_dir / "ref_features.csv",
        'report': output_dir / "report.md"
    }


def load_config(config_path: str = None) -> dict:
    """
    Load configuration from YAML file (optional).
    
    If no config is provided, returns None and system uses hardcoded defaults.
    This ensures 100% backward compatibility with existing tennis behavior.
    
    Args:
        config_path: Path to YAML config file (optional)
        
    Returns:
        Configuration dictionary or None if no config/YAML unavailable
    """
    if config_path is None:
        return None
    
    if not YAML_AVAILABLE:
        print("[WARNING] PyYAML not installed. Install with: pip install pyyaml")
        print("[INFO] Using hardcoded defaults for tennis backhand analysis")
        return None
    
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            print(f"[WARNING] Config file not found: {config_path}")
            print("[INFO] Using hardcoded defaults for tennis backhand analysis")
            return None
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        print(f"[CONFIG] Loaded configuration from: {config_path}")
        if 'sport' in config and 'movement' in config:
            print(f"[CONFIG] Sport: {config['sport']}, Movement: {config['movement']}")
        
        return config
    
    except Exception as e:
        print(f"[WARNING] Failed to load config: {e}")
        print("[INFO] Using hardcoded defaults for tennis backhand analysis")
        return None


def get_phase_weights(config: dict = None) -> dict:
    """
    Get phase weights from config or use defaults.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Phase weights dictionary
    """
    # Default tennis backhand weights (existing hardcoded behavior)
    default_weights = {
        'preparation': 0.15,
        'load': 0.25,
        'contact': 0.35,
        'follow_through': 0.25
    }
    
    if config and 'phase_weights' in config:
        return config['phase_weights']
    
    return default_weights


def get_metrics_list(config: dict = None) -> list:
    """
    Get metrics list from config or use defaults.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        List of metric names
    """
    # Default tennis backhand metrics (existing hardcoded behavior)
    default_metrics = [
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
    
    if config and 'metrics' in config:
        return config['metrics']
    
    return default_metrics


def get_phase_names(config: dict = None) -> dict:
    """
    Get phase names from config or use defaults.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dictionary mapping phase keys to display names
    """
    # Default tennis backhand phases (existing hardcoded behavior)
    default_phases = {
        'preparation': 'Preparation',
        'load': 'Load',
        'contact': 'Contact',
        'follow_through': 'Follow-through'
    }
    
    if config and 'phases' in config:
        return {key: phase['name'] for key, phase in config['phases'].items()}
    
    return default_phases

