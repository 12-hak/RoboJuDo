#!/usr/bin/env python3
"""Diagnostic script to check observation dimensions"""
import numpy as np

# Simulate the observation building
base_ang_vel = np.zeros(3)
projected_gravity = np.array([0, 0, -1])
lin_vel_command = np.zeros(2)
ang_vel_command = np.zeros(1)
dof_pos_minus_default = np.zeros(29)
dof_vel = np.zeros(29)
last_action = np.zeros(29)

obs = np.concatenate([
    base_ang_vel,  # 3
    projected_gravity,  # 3
    lin_vel_command,  # 2
    ang_vel_command,  # 1
    dof_pos_minus_default,  # 29
    dof_vel,  # 29
    last_action,  # 29
    np.zeros(3),  # Padding to reach 99
], axis=0)

print(f"Observation breakdown:")
print(f"  base_ang_vel: 3")
print(f"  projected_gravity: 3")
print(f"  lin_vel_command: 2")
print(f"  ang_vel_command: 1")
print(f"  dof_pos: 29")
print(f"  dof_vel: 29")
print(f"  last_action: 29")
print(f"  padding: 3")
print(f"  TOTAL: {len(obs)}")
print(f"\nExpected: 99")
print(f"Match: {len(obs) == 99}")
