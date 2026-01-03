#!/usr/bin/env python3
"""
Stroke Abstraction Layer - Interactive Demo

This script provides an interactive demonstration of how stroke-specific
thresholds enable more intelligent coaching feedback.
"""

import sys
import io

# Fix Windows UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'vision')

from compare import (
    get_stroke_aware_threshold,
    get_stroke_phase_weights,
    STROKE_PROFILES
)


def print_header(title):
    """Print formatted header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print('='*80)


def print_section(title):
    """Print formatted section header"""
    print(f"\n{title}")
    print('-'*80)


def demo_coaching_scenario():
    """Demonstrate how stroke awareness improves coaching"""
    print_header("🎾 STROKE ABSTRACTION LAYER - INTERACTIVE DEMO")
    
    print("""
This demo shows how stroke-specific biomechanical context enables more
intelligent and accurate coaching feedback.
    """)
    
    # Scenario setup
    print_section("📊 SCENARIO: Hip Rotation Analysis")
    
    player_name = "Alex"
    measured_hip_rotation = 165  # degrees
    
    print(f"""
Player: {player_name}
Measured hip rotation: {measured_hip_rotation}°

Question: Is this good technique or does it need improvement?
    """)
    
    # Without stroke awareness
    print_section("❌ WITHOUT Stroke Awareness (Old Approach)")
    
    generic_threshold = 180
    print(f"Generic threshold: {generic_threshold}°")
    print(f"Player's rotation: {measured_hip_rotation}°")
    print(f"Deviation: {measured_hip_rotation - generic_threshold}° (below threshold)")
    print(f"\n⚠️  Coaching feedback: 'Increase hip rotation'")
    print(f"❌ Problem: This might be INCORRECT advice depending on the stroke!")
    
    # With stroke awareness
    print_section("✅ WITH Stroke Awareness (New Approach)")
    
    strokes = ['backhand', 'forehand', 'serve', 'volley', 'overhead']
    
    for stroke in strokes:
        range_min, range_max = get_stroke_aware_threshold('hip_rotation', stroke)
        rationale = get_stroke_aware_threshold('hip_rotation', stroke, 'rationale')
        
        # Determine if within range
        if range_min <= measured_hip_rotation <= range_max:
            status = "✅ GOOD"
            feedback = f"Maintain current technique"
        elif measured_hip_rotation < range_min:
            status = "⚠️  LOW"
            deficit = range_min - measured_hip_rotation
            feedback = f"Increase rotation by ~{deficit}°. {rationale}"
        else:
            status = "⚠️  HIGH"
            excess = measured_hip_rotation - range_max
            feedback = f"Reduce rotation by ~{excess}°. More compact motion needed"
        
        print(f"\n{stroke.upper():12} | {range_min:3d}-{range_max:3d}° | {status}")
        print(f"              └─ {feedback}")


def demo_phase_importance():
    """Demonstrate stroke-specific phase importance"""
    print_section("📈 PHASE IMPORTANCE BY STROKE")
    
    print("""
Different strokes emphasize different phases of movement.
This affects how we weight scoring and prioritize coaching cues.
    """)
    
    strokes = ['backhand', 'forehand', 'serve', 'volley', 'overhead']
    
    print(f"\n{'Stroke':<12} {'Prep':>8} {'Load':>8} {'Contact':>10} {'Follow':>10} {'Key Focus'}")
    print('-'*80)
    
    for stroke in strokes:
        weights = get_stroke_phase_weights(stroke)
        
        # Find most important phase
        max_phase = max(weights.items(), key=lambda x: x[1])
        key_focus = f"{max_phase[0].capitalize()} ({max_phase[1]*100:.0f}%)"
        
        print(f"{stroke.capitalize():<12} "
              f"{weights['preparation']*100:7.0f}% "
              f"{weights['load']*100:7.0f}% "
              f"{weights['contact']*100:9.0f}% "
              f"{weights['follow_through']*100:9.0f}%  "
              f"{key_focus}")
    
    print("\n💡 Insight:")
    print("   • Groundstrokes (backhand/forehand): Contact is most critical")
    print("   • Serve: Contact + Preparation (trophy position) are key")
    print("   • Volley: Contact + Preparation (split-step) dominate")


def demo_cross_stroke_comparison():
    """Demonstrate comparing metrics across strokes"""
    print_section("🔄 CROSS-STROKE METRIC COMPARISON")
    
    print("""
Understanding how metrics vary across strokes enables:
- Better technique assessment
- More relevant coaching cues
- Stroke-specific drill selection
    """)
    
    metrics = ['hip_rotation', 'elbow_angle', 'knee_flexion', 'spine_lean']
    strokes = ['backhand', 'forehand', 'serve', 'volley']
    
    for metric in metrics:
        print(f"\n{metric.upper().replace('_', ' ')}:")
        
        for stroke in strokes:
            threshold = get_stroke_aware_threshold(metric, stroke)
            if threshold:
                range_min, range_max = threshold
                print(f"  {stroke.capitalize():10} {range_min:4d}° to {range_max:4d}°")
            else:
                print(f"  {stroke.capitalize():10} Not defined")


def demo_coaching_intelligence():
    """Demonstrate intelligent coaching recommendations"""
    print_section("🧠 INTELLIGENT COACHING ENGINE")
    
    print("""
Stroke Abstraction enables context-aware coaching that adapts to:
- The specific stroke being performed
- The player's skill level and goals
- The biomechanical requirements of that stroke
    """)
    
    scenarios = [
        {
            'stroke': 'backhand',
            'issue': 'Low hip rotation (135°)',
            'expected': (150, 220),
            'advice': 'Focus on hip coiling during load phase. Use medicine ball rotations.'
        },
        {
            'stroke': 'forehand',
            'issue': 'Low hip rotation (160°)',
            'expected': (180, 270),
            'advice': 'Increase open stance width. Practice shadow swings with emphasis on rotation.'
        },
        {
            'stroke': 'serve',
            'issue': 'Limited elbow extension (125°)',
            'expected': (140, 180),
            'advice': 'Work on trophy position height. Practice overhead throwing motion.'
        },
        {
            'stroke': 'volley',
            'issue': 'Excessive hip rotation (120°)',
            'expected': (30, 90),
            'advice': 'Shorten backswing. Focus on compact, punching motion at net.'
        }
    ]
    
    print()
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. {scenario['stroke'].upper()}")
        print(f"   Issue: {scenario['issue']}")
        print(f"   Expected: {scenario['expected'][0]}-{scenario['expected'][1]}°")
        print(f"   ✅ Coaching: {scenario['advice']}\n")


def demo_future_vision():
    """Show future capabilities enabled by stroke abstraction"""
    print_section("🚀 FUTURE CAPABILITIES")
    
    print("""
The Stroke Abstraction Layer is a foundation that enables:

PHASE 3: Multi-Stroke Video Analysis
  → Automatically detect stroke type from video
  → Apply stroke-specific analysis to each rally shot
  → Generate cross-stroke comparison reports

PHASE 4: Full Tennis Game Intelligence
  → Analyze entire match footage
  → Track forehand/backhand patterns
  → Evaluate serve + return technique
  → Assess net play (volley/overhead)

PHASE 5: Adaptive Stroke-Specific Coaching
  → "Your forehand is strong (85/100), focus on backhand (62/100)"
  → "Serve contact point needs +3° extension"
  → "Volley preparation timing improving (+12% from last session)"

PHASE 6: Intelligent Drill Prescription
  → Forehand-specific drills for forehand issues
  → Serve-specific drills for serve mechanics
  → Cross-stroke drills for general athleticism

PHASE 7: Competitive Analysis
  → Compare your forehand vs. Federer's forehand
  → Compare your serve vs. Serena's serve
  → Identify stroke-specific strengths and weaknesses
    """)


def main():
    """Run interactive demo"""
    try:
        demo_coaching_scenario()
        demo_phase_importance()
        demo_cross_stroke_comparison()
        demo_coaching_intelligence()
        demo_future_vision()
        
        print_header("✅ DEMO COMPLETE")
        print("""
The Stroke Abstraction Layer provides:
  ✅ Stroke-specific biomechanical context
  ✅ Intelligent threshold interpretation
  ✅ Foundation for multi-stroke analysis
  ✅ 100% backward compatibility

Next Steps:
  1. Read STROKE_ABSTRACTION.md for technical details
  2. Run test_stroke_abstraction.py to see all tests pass
  3. Integrate stroke awareness into similarity scoring (Phase 3)

Ready to transform Coach AI from single-stroke to full-game intelligence! 🎾
        """)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

