#!/usr/bin/env python3
"""
Analyze real robot data to identify sim-to-real gaps
Helps determine what to fix in simulation for better training
"""
import h5py
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def analyze_robot_data(filename):
    """Analyze collected robot data and identify issues"""
    
    print("="*70)
    print("🔍 REAL ROBOT DATA ANALYSIS - SIM-TO-REAL GAP IDENTIFICATION")
    print("="*70)
    
    with h5py.File(filename, 'r') as f:
        # Load data
        timestamps = f['timestamps'][:]
        dof_pos = f['dof_pos'][:]
        dof_vel = f['dof_vel'][:]
        actions_sent = f['actions_sent'][:]
        base_ang_vel = f['base_ang_vel'][:]
        base_lin_vel = f['base_lin_vel'][:]
        commands = f['commands'][:]
        
        # Load config
        action_scale = f.attrs.get('action_scale', 0.0)
        action_beta = f.attrs.get('action_beta', 0.0)
        
        duration = timestamps[-1] - timestamps[0]
        dt = np.diff(timestamps)
        
        print(f"\n📊 BASIC STATS")
        print(f"Duration: {duration:.2f}s")
        print(f"Samples: {len(timestamps)}")
        print(f"Frequency: {len(timestamps)/duration:.1f}Hz")
        print(f"Action scale: {action_scale}")
        print(f"Action beta: {action_beta}")
        
        # ISSUE 1: Check if robot is actually moving
        print(f"\n🚶 MOVEMENT ANALYSIS")
        forward_vel = base_lin_vel[:, 0]  # X velocity
        lateral_vel = base_lin_vel[:, 1]  # Y velocity
        
        print(f"Forward velocity:")
        print(f"  Mean: {forward_vel.mean():.4f} m/s")
        print(f"  Max: {forward_vel.max():.4f} m/s")
        print(f"  Std: {forward_vel.std():.4f} m/s")
        
        # Check if commanded forward but not moving
        forward_commands = commands[:, 0]  # lin_vel_x commands
        moving_forward = np.abs(forward_vel) > 0.05
        commanded_forward = np.abs(forward_commands) > 0.1
        
        if commanded_forward.any() and not moving_forward.any():
            print("  ⚠️  ISSUE: Commanded forward but robot not moving!")
            print("     → Action scale too low OR model not learned forward walking")
        
        # ISSUE 2: Check leg spreading
        print(f"\n🦵 LEG ANALYSIS (Hip Roll joints)")
        left_hip_roll = dof_pos[:, 1]   # Index 1: left_hip_roll
        right_hip_roll = dof_pos[:, 7]  # Index 7: right_hip_roll
        
        hip_spread = np.abs(left_hip_roll) + np.abs(right_hip_roll)
        print(f"Hip spread (sum of abs):")
        print(f"  Mean: {hip_spread.mean():.4f} rad ({np.degrees(hip_spread.mean()):.1f}°)")
        print(f"  Max: {hip_spread.max():.4f} rad ({np.degrees(hip_spread.max()):.1f}°)")
        
        if hip_spread.mean() > 0.3:  # More than ~17 degrees
            print("  ⚠️  ISSUE: Legs spreading too much!")
            print("     → Model learned different hip behavior in sim")
        
        # ISSUE 3: Check action magnitudes
        print(f"\n⚡ ACTION ANALYSIS")
        action_magnitudes = np.abs(actions_sent)
        print(f"Action magnitudes:")
        print(f"  Mean: {action_magnitudes.mean():.4f}")
        print(f"  Max: {action_magnitudes.max():.4f}")
        print(f"  Std: {action_magnitudes.std():.4f}")
        
        # Check if actions are saturating
        if action_magnitudes.max() > 0.8:
            print("  ⚠️  ISSUE: Actions near saturation!")
            print("     → Action scale might be too high")
        elif action_magnitudes.mean() < 0.1:
            print("  ⚠️  ISSUE: Actions very small!")
            print("     → Action scale might be too low")
        
        # ISSUE 4: Check joint velocity tracking
        print(f"\n🎯 JOINT VELOCITY TRACKING")
        action_changes = np.diff(actions_sent, axis=0)
        vel_changes = np.diff(dof_vel, axis=0)
        
        print(f"Action changes:")
        print(f"  Mean: {np.abs(action_changes).mean():.4f}")
        print(f"  Max: {np.abs(action_changes).max():.4f}")
        
        print(f"Velocity changes:")
        print(f"  Mean: {np.abs(vel_changes).mean():.4f}")
        print(f"  Max: {np.abs(vel_changes).max():.4f}")
        
        # ISSUE 5: Check stability
        print(f"\n⚖️  STABILITY ANALYSIS")
        ang_vel_magnitude = np.linalg.norm(base_ang_vel, axis=1)
        print(f"Base angular velocity magnitude:")
        print(f"  Mean: {ang_vel_magnitude.mean():.4f} rad/s")
        print(f"  Max: {ang_vel_magnitude.max():.4f} rad/s")
        
        if ang_vel_magnitude.mean() > 0.5:
            print("  ⚠️  ISSUE: High angular velocity (unstable)")
            print("     → Action scale too high OR smoothing too low")
        
        # RECOMMENDATIONS
        print(f"\n" + "="*70)
        print("💡 RECOMMENDATIONS FOR RETRAINING")
        print("="*70)
        
        issues_found = []
        
        if commanded_forward.any() and not moving_forward.any():
            issues_found.append("1. INCREASE forward walking reward in training")
            issues_found.append("   - Current model doesn't walk forward effectively")
            issues_found.append("   - Add specific reward for forward velocity tracking")
        
        if hip_spread.mean() > 0.3:
            issues_found.append("2. ADD hip roll penalty in training")
            issues_found.append("   - Penalize hip_roll joint movement")
            issues_found.append("   - Model learned to spread legs in sim")
        
        if action_magnitudes.mean() < 0.15:
            issues_found.append("3. TRAIN with lower action scale in sim")
            issues_found.append(f"   - Real robot needs action_scale={action_scale}")
            issues_found.append("   - Train with action_scale=0.3-0.4 instead of 0.5")
        
        if ang_vel_magnitude.mean() > 0.5:
            issues_found.append("4. ADD base stability penalty")
            issues_found.append("   - Penalize high angular velocity")
            issues_found.append("   - Increase upright reward weight")
        
        if issues_found:
            for issue in issues_found:
                print(issue)
        else:
            print("✅ No major issues detected!")
            print("   Model might just need fine-tuning of action_scale/beta")
        
        print("\n" + "="*70)
        
        # Create plots
        create_analysis_plots(timestamps, dof_pos, dof_vel, actions_sent, 
                            base_lin_vel, base_ang_vel, commands)
        
        return {
            'forward_movement': moving_forward.any(),
            'hip_spread_mean': hip_spread.mean(),
            'action_magnitude_mean': action_magnitudes.mean(),
            'stability': ang_vel_magnitude.mean(),
        }


def create_analysis_plots(timestamps, dof_pos, dof_vel, actions, 
                         base_lin_vel, base_ang_vel, commands):
    """Create diagnostic plots"""
    
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    
    # Plot 1: Base velocities vs commands
    axes[0].plot(timestamps, base_lin_vel[:, 0], label='Actual forward vel', linewidth=2)
    axes[0].plot(timestamps, commands[:, 0], '--', label='Commanded forward vel', alpha=0.7)
    axes[0].set_title('Forward Velocity Tracking')
    axes[0].set_ylabel('Velocity (m/s)')
    axes[0].legend()
    axes[0].grid(True)
    
    # Plot 2: Hip roll joints (leg spreading)
    axes[1].plot(timestamps, np.degrees(dof_pos[:, 1]), label='Left hip roll')
    axes[1].plot(timestamps, np.degrees(dof_pos[:, 7]), label='Right hip roll')
    axes[1].set_title('Hip Roll Joints (Leg Spreading)')
    axes[1].set_ylabel('Angle (degrees)')
    axes[1].legend()
    axes[1].grid(True)
    axes[1].axhline(y=0, color='k', linestyle='--', alpha=0.3)
    
    # Plot 3: Action magnitudes
    action_mags = np.linalg.norm(actions, axis=1)
    axes[2].plot(timestamps, action_mags)
    axes[2].set_title('Action Magnitude Over Time')
    axes[2].set_ylabel('Action magnitude')
    axes[2].grid(True)
    
    # Plot 4: Base angular velocity (stability)
    ang_vel_mag = np.linalg.norm(base_ang_vel, axis=1)
    axes[3].plot(timestamps, ang_vel_mag)
    axes[3].set_title('Base Angular Velocity (Stability Indicator)')
    axes[3].set_ylabel('Angular velocity (rad/s)')
    axes[3].set_xlabel('Time (s)')
    axes[3].grid(True)
    
    plt.tight_layout()
    plt.savefig('robot_data_analysis.png', dpi=150)
    print(f"\n📈 Saved plots to: robot_data_analysis.png")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analyze_robot_data.py <data_file.h5>")
        print("\nLooking for latest file in robot_data_logs/...")
        
        log_dir = Path("robot_data_logs")
        if log_dir.exists():
            files = sorted(log_dir.glob("robot_data_*.h5"))
            if files:
                latest = files[-1]
                print(f"Found: {latest}")
                analyze_robot_data(latest)
            else:
                print("No data files found!")
        else:
            print("No robot_data_logs directory found!")
    else:
        analyze_robot_data(sys.argv[1])
