# Configuration System

## Overview

Coach AI now supports sport-agnostic configuration through optional YAML files. This allows you to customize:
- Phase definitions and names
- Biomechanical metrics to analyze
- Phase importance weights
- Contact detection methods

**Important**: Configuration is **purely optional**. If no config is provided, the system uses hardcoded defaults that match the original tennis two-handed backhand implementation.

## Usage

### Default Behavior (Tennis)

Run without configuration to analyze tennis backhand technique:

```bash
python vision/compare.py
```

This uses hardcoded defaults:
- Phases: Preparation, Load, Contact, Follow-through
- Metrics: Shoulder/elbow/knee angles, hip rotation, spine lean, stance width
- Weights: Contact (35%) and Follow-through (25%) weighted highest
- Contact detection: Wrist speed

### Custom Sport Configuration

Run with a custom configuration file:

```bash
python vision/compare.py --config config/my_sport.yaml
```

## Configuration File Structure

### Example: Tennis Backhand (Default)

```yaml
# Sport and movement identification
sport: tennis
movement: two_handed_backhand

# Phase definitions
phases:
  preparation:
    name: Preparation
    description: Setup and early rotation
  load:
    name: Load
    description: Energy storage phase
  contact:
    name: Contact
    description: Ball impact
  follow_through:
    name: Follow-through
    description: Completion and recovery

# Phase importance weights (must sum to ~1.0)
phase_weights:
  preparation: 0.15
  load: 0.25
  contact: 0.35      # Highest - most critical moment
  follow_through: 0.25

# Biomechanical metrics to analyze
metrics:
  - left_shoulder_angle
  - right_shoulder_angle
  - left_elbow_angle
  - right_elbow_angle
  - left_knee_angle
  - right_knee_angle
  - hip_rotation
  - spine_lean
  - stance_width_normalized

# Contact/impact detection
contact_detection:
  method: wrist_speed
  signal: combined_wrist_speed

# Reference video info
reference:
  athlete: Novak Djokovic
  video: djokovic_backhand.mp4
  description: Professional technique
```

### Creating Config for Other Sports

#### Golf Swing Example

```yaml
sport: golf
movement: driver_swing

phases:
  address:
    name: Address
    description: Setup position
  backswing:
    name: Backswing
    description: Club take-back
  impact:
    name: Impact
    description: Ball contact
  follow_through:
    name: Follow-through
    description: Post-impact rotation

phase_weights:
  address: 0.15
  backswing: 0.30
  impact: 0.40
  follow_through: 0.15

metrics:
  - left_shoulder_angle
  - right_shoulder_angle
  - left_elbow_angle
  - right_elbow_angle
  - hip_rotation
  - spine_lean
  - stance_width_normalized

contact_detection:
  method: wrist_speed
  signal: combined_wrist_speed
```

#### Baseball Pitch Example

```yaml
sport: baseball
movement: fastball_pitch

phases:
  windup:
    name: Windup
    description: Initial leg lift
  stride:
    name: Stride
    description: Step toward plate
  release:
    name: Release
    description: Ball release point
  follow_through:
    name: Follow-through
    description: Deceleration

phase_weights:
  windup: 0.10
  stride: 0.30
  release: 0.45
  follow_through: 0.15

metrics:
  - left_shoulder_angle
  - right_shoulder_angle
  - left_elbow_angle
  - right_elbow_angle
  - hip_rotation
  - spine_lean
```

## Configuration Fields

### Required Fields

- `sport`: Sport name (string)
- `movement`: Specific movement type (string)
- `phases`: Dictionary of phase definitions
  - Each phase must have: `name`, `description`
- `phase_weights`: Dictionary mapping phase keys to weights (0.0-1.0)
  - Weights should sum to approximately 1.0
- `metrics`: List of biomechanical metric names to analyze

### Optional Fields

- `contact_detection`: Method for detecting key contact frame
  - `method`: Detection algorithm (default: "wrist_speed")
  - `signal`: Specific signal to use
- `reference`: Reference video metadata
  - `athlete`: Athlete name
  - `video`: Filename
  - `description`: Technique description

## Backward Compatibility

The configuration system is **100% backward compatible**:

1. **No config file**: Uses tennis backhand defaults (existing behavior)
2. **Config file missing**: Falls back to defaults with warning
3. **PyYAML not installed**: Falls back to defaults with helpful message
4. **Invalid config**: Falls back to defaults with error message

All existing scripts, notebooks, and workflows continue to work without modification.

## Implementation Notes

### How It Works

1. Configuration is loaded at the start of `run_pipeline()`
2. If no config is provided or loading fails, `config = None`
3. Helper functions (`get_phase_weights`, `get_metrics_list`, `get_phase_names`) return:
   - Config values if `config` is not None
   - Hardcoded tennis defaults if `config` is None
4. All existing functions receive config as an optional parameter
5. No core logic is modified - only parameter sources change

### Files Modified

- `vision/compare.py`: Added config loading and helper functions
- `requirements.txt`: Added `pyyaml>=6.0`
- `config/tennis_backhand.yaml`: Created default config template

### Testing

```bash
# Test 1: Default behavior (no config)
python vision/compare.py

# Test 2: Explicit tennis config
python vision/compare.py --config config/tennis_backhand.yaml

# Test 3: Custom sport config
python vision/compare.py --config config/my_custom_sport.yaml
```

All three should work correctly, with Test 1 and Test 2 producing identical results.

## Future Extensions

Possible future enhancements:
- Sport-specific phase segmentation algorithms
- Custom metric definitions (beyond current MediaPose landmarks)
- Multi-reference comparison (compare to multiple pros)
- Dynamic weight adjustment based on user skill level

