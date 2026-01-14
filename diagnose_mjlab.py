#!/usr/bin/env python3
"""Diagnostic script to debug mjlab policy observations"""
import numpy as np
import sys
sys.path.insert(0, '/home/unitree/development/RoboJuDo')

from robojudo.config.g1.policy.g1_mjlab_policy_cfg import G1MjlabLocoPolicyCfg
from robojudo.policy.mjlab_policy import MjlabLocoPolicy

# Create policy
cfg = G1MjlabLocoPolicyCfg()
policy = MjlabLocoPolicy(cfg, device='cpu')

print("=" * 60)
print("MJLAB POLICY DIAGNOSTIC")
print("=" * 60)

# Simulate environment data
class FakeEnvData:
    def __init__(self):
        self.base_quat = np.array([0, 0, 0, 1], dtype=np.float32)  # No rotation
        self.base_ang_vel = np.zeros(3, dtype=np.float32)
        self.base_lin_vel = np.zeros(3, dtype=np.float32)
        self.dof_pos = policy.default_dof_pos.copy()
        self.dof_vel = np.zeros(29, dtype=np.float32)

env_data = FakeEnvData()
ctrl_data = {}

# Get observation
obs, extras = policy.get_observation(env_data, ctrl_data)

print(f"\nObservation Shape: {obs.shape}")
print(f"Expected: (99,)")
print(f"Match: {obs.shape == (99,)}")

print(f"\nObservation dtype: {obs.dtype}")
print(f"Expected: float32")

print(f"\nObservation breakdown:")
idx = 0
print(f"  base_lin_vel [{idx}:{idx+3}]: {obs[idx:idx+3]}")
idx += 3
print(f"  base_ang_vel [{idx}:{idx+3}]: {obs[idx:idx+3]}")
idx += 3
print(f"  projected_gravity [{idx}:{idx+3}]: {obs[idx:idx+3]}")
idx += 3
print(f"  joint_pos [{idx}:{idx+29}]: min={obs[idx:idx+29].min():.3f}, max={obs[idx:idx+29].max():.3f}")
idx += 29
print(f"  joint_vel [{idx}:{idx+29}]: min={obs[idx:idx+29].min():.3f}, max={obs[idx:idx+29].max():.3f}")
idx += 29
print(f"  actions [{idx}:{idx+29}]: min={obs[idx:idx+29].min():.3f}, max={obs[idx:idx+29].max():.3f}")
idx += 29
print(f"  command [{idx}:{idx+3}]: {obs[idx:idx+3]}")

print(f"\nObservation stats:")
print(f"  Min: {obs.min()}")
print(f"  Max: {obs.max()}")
print(f"  Mean: {obs.mean()}")
print(f"  Std: {obs.std()}")
print(f"  NaN count: {np.isnan(obs).sum()}")
print(f"  Inf count: {np.isinf(obs).sum()}")

# Try running through model
print(f"\n" + "=" * 60)
print("TESTING MODEL INFERENCE")
print("=" * 60)

try:
    action = policy.get_action(obs)
    print(f"✓ Model inference successful!")
    print(f"  Action shape: {action.shape}")
    print(f"  Action range: [{action.min():.3f}, {action.max():.3f}]")
    print(f"  Action mean: {action.mean():.3f}")
    print(f"  Action std: {action.std():.3f}")
except Exception as e:
    print(f"✗ Model inference FAILED!")
    print(f"  Error: {e}")

print(f"\n" + "=" * 60)
print("CONFIGURATION")
print("=" * 60)
print(f"Action scale: {cfg.action_scale}")
print(f"Action beta: {cfg.action_beta}")
print(f"Action clip: {cfg.action_clip}")
print(f"Commands map: {cfg.commands_map}")
print(f"Obs scales:")
print(f"  ang_vel: {cfg.obs_scales.ang_vel}")
print(f"  dof_vel: {cfg.obs_scales.dof_vel}")
print(f"  dof_pos: {cfg.obs_scales.dof_pos}")
print(f"  projected_gravity: {cfg.obs_scales.projected_gravity}")

print(f"\n" + "=" * 60)
print("RECOMMENDATIONS")
print("=" * 60)

# Check for potential issues
issues = []
if obs.shape != (99,):
    issues.append(f"Observation shape mismatch: {obs.shape} vs (99,)")
if np.isnan(obs).any():
    issues.append("NaN values in observations")
if np.isinf(obs).any():
    issues.append("Inf values in observations")
if abs(obs.mean()) > 10:
    issues.append(f"Observation mean very high: {obs.mean():.2f} (might need normalization)")
if obs.std() > 50:
    issues.append(f"Observation std very high: {obs.std():.2f} (might need scaling)")

if issues:
    print("⚠ POTENTIAL ISSUES FOUND:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("✓ No obvious issues detected")
    print("\nIf robot still doesn't balance, try:")
    print("  1. Increase action_scale gradually (0.12 → 0.15 → 0.18)")
    print("  2. Reduce action_beta for less smoothing (0.4 → 0.5 → 0.6)")
    print("  3. Check if base_lin_vel is being estimated correctly on real robot")
    print("  4. Verify PD gains aren't too low")
