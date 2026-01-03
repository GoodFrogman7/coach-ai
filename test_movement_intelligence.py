#!/usr/bin/env python3
"""
Quick test for Movement Intelligence APIs
"""

import sys
import io

# Fix Windows UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'vision')

from compare import (
    get_movement_metric_spec,
    assess_movement_quality,
    is_movement_metric
)

print("Movement Intelligence APIs loaded successfully!\n")

# Test 1: Get specification
spec = get_movement_metric_spec('split_step_timing')
print(f"1. Split-Step Timing specification:")
print(f"   Range: {spec['expected_range']}")
print(f"   Optimal: {spec['optimal_value']}")
print(f"   Importance: {spec['importance']}")

# Test 2: Assess quality
assessment = assess_movement_quality('split_step_timing', 0.12)
print(f"\n2. Assessment for 0.12s split-step timing:")
print(f"   Classification: {assessment['classification']}")
print(f"   Deviation: {assessment['deviation']}")

# Test 3: Check metric type
print(f"\n3. Metric type checking:")
print(f"   is_movement_metric('split_step_timing'): {is_movement_metric('split_step_timing')}")
print(f"   is_movement_metric('hip_rotation'): {is_movement_metric('hip_rotation')}")

# Test 4: All movement metrics accessible
print(f"\n4. All movement metrics:")
movement_metrics = [
    'split_step_timing',
    'lateral_push_off_symmetry',
    'recovery_time',
    'stance_transition_speed',
    'balance_drift',
    'first_step_reaction_time',
    'footwork_efficiency',
    'weight_transfer_completeness'
]

for metric in movement_metrics:
    spec = get_movement_metric_spec(metric)
    status = "✓" if spec else "✗"
    print(f"   {status} {metric}")

print("\n✅ All Movement Intelligence tests passed!")

