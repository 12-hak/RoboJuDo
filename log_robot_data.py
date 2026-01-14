#!/usr/bin/env python3
"""
Standalone Real Robot Data Logger
Logs motor states and commands to identify sim-to-real gaps
Run this ALONGSIDE your existing pipeline (no code changes needed)
"""
import numpy as np
import h5py
import time
from datetime import datetime
from pathlib import Path
import sys

# Add RoboJuDo to path
sys.path.insert(0, '/home/unitree/development/RoboJuDo')

from robojudo.environment.unitree_cpp_env import UnitreeCppEnv


class StandaloneDataLogger:
    """Logs robot state without modifying existing code"""
    
    def __init__(self, duration_seconds=60):
        self.duration = duration_seconds
        self.output_dir = Path("robot_data_logs")
        self.output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = self.output_dir / f"motor_log_{timestamp}.h5"
        
        # Data buffers
        self.data = {
            'timestamps': [],
            'dof_pos_actual': [],      # What motors actually did
            'dof_vel_actual': [],      # Actual velocities
            'dof_pos_target': [],      # What was commanded
            'dof_torque': [],          # Actual torques
            'base_quat': [],
            'base_ang_vel': [],
            'base_lin_vel': [],
        }
        
        print("="*70)
        print("🤖 STANDALONE ROBOT DATA LOGGER")
        print("="*70)
        print(f"Duration: {duration_seconds}s")
        print(f"Output: {self.filename}")
        print("\nThis will log:")
        print("  - Joint positions (actual vs commanded)")
        print("  - Joint velocities")
        print("  - Joint torques")
        print("  - Base state (orientation, velocities)")
        print("\nPress Ctrl+C to stop early")
        print("="*70)
    
    def run(self):
        """Run the logger"""
        # Connect to robot
        print("\n🔌 Connecting to robot...")
        
        # Import config
        from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg
        
        env = UnitreeCppEnv(cfg_env=G1RealEnvCfg())
        
        print("✅ Connected!")
        print(f"\n📝 Logging for {self.duration}s...")
        print("(Robot should be running your policy in another terminal)")
        
        start_time = time.time()
        sample_count = 0
        
        try:
            while (time.time() - start_time) < self.duration:
                # Read current state
                env.update()
                
                # Log data
                self.data['timestamps'].append(time.time())
                self.data['dof_pos_actual'].append(env.dof_pos.copy())
                self.data['dof_vel_actual'].append(env.dof_vel.copy())
                self.data['dof_pos_target'].append(env.dof_pos_target.copy() if hasattr(env, 'dof_pos_target') else env.dof_pos.copy())
                self.data['dof_torque'].append(env.dof_torque.copy() if hasattr(env, 'dof_torque') else np.zeros(29))
                self.data['base_quat'].append(env.base_quat.copy())
                self.data['base_ang_vel'].append(env.base_ang_vel.copy())
                
                if hasattr(env, 'base_lin_vel') and env.base_lin_vel is not None:
                    self.data['base_lin_vel'].append(env.base_lin_vel.copy())
                else:
                    self.data['base_lin_vel'].append(np.zeros(3))
                
                sample_count += 1
                
                # Progress update every second
                if sample_count % 50 == 0:
                    elapsed = time.time() - start_time
                    print(f"  {elapsed:.1f}s / {self.duration}s - {sample_count} samples")
                
                time.sleep(0.02)  # ~50Hz
                
        except KeyboardInterrupt:
            print("\n⏹️  Stopped by user")
        
        print(f"\n✅ Collected {sample_count} samples")
        
        # Save and analyze
        self.save_and_analyze()
    
    def save_and_analyze(self):
        """Save data and do quick analysis"""
        print(f"\n💾 Saving to {self.filename}...")
        
        with h5py.File(self.filename, 'w') as f:
            for key, values in self.data.items():
                if values:
                    f.create_dataset(key, data=np.array(values))
            
            f.attrs['num_samples'] = len(self.data['timestamps'])
            f.attrs['duration_s'] = self.data['timestamps'][-1] - self.data['timestamps'][0]
            f.attrs['collection_date'] = datetime.now().isoformat()
        
        print("✅ Saved!")
        
        # Quick analysis
        self.analyze()
    
    def analyze(self):
        """Quick analysis of collected data"""
        print("\n" + "="*70)
        print("📊 QUICK ANALYSIS")
        print("="*70)
        
        timestamps = np.array(self.data['timestamps'])
        dof_pos_actual = np.array(self.data['dof_pos_actual'])
        dof_vel_actual = np.array(self.data['dof_vel_actual'])
        base_lin_vel = np.array(self.data['base_lin_vel'])
        
        duration = timestamps[-1] - timestamps[0]
        
        print(f"\n⏱️  Duration: {duration:.2f}s")
        print(f"📦 Samples: {len(timestamps)}")
        print(f"🔄 Frequency: {len(timestamps)/duration:.1f}Hz")
        
        # Movement analysis
        print(f"\n🚶 MOVEMENT")
        forward_vel = base_lin_vel[:, 0]
        print(f"Forward velocity:")
        print(f"  Mean: {forward_vel.mean():.4f} m/s")
        print(f"  Max: {forward_vel.max():.4f} m/s")
        print(f"  Min: {forward_vel.min():.4f} m/s")
        
        if np.abs(forward_vel).max() < 0.05:
            print("  ⚠️  Robot barely moving forward!")
        
        # Leg spreading check
        print(f"\n🦵 LEG SPREADING")
        left_hip_roll = dof_pos_actual[:, 1]   # Index 1
        right_hip_roll = dof_pos_actual[:, 7]  # Index 7
        
        print(f"Left hip roll:")
        print(f"  Mean: {np.degrees(left_hip_roll.mean()):.2f}°")
        print(f"  Range: [{np.degrees(left_hip_roll.min()):.2f}°, {np.degrees(left_hip_roll.max()):.2f}°]")
        
        print(f"Right hip roll:")
        print(f"  Mean: {np.degrees(right_hip_roll.mean()):.2f}°")
        print(f"  Range: [{np.degrees(right_hip_roll.min()):.2f}°, {np.degrees(right_hip_roll.max()):.2f}°]")
        
        hip_spread = np.abs(left_hip_roll) + np.abs(right_hip_roll)
        if hip_spread.mean() > 0.3:
            print(f"  ⚠️  Legs spreading! (mean spread: {np.degrees(hip_spread.mean()):.1f}°)")
        
        # Joint velocity analysis
        print(f"\n⚡ JOINT ACTIVITY")
        vel_magnitude = np.abs(dof_vel_actual).mean(axis=0)
        most_active_joints = np.argsort(vel_magnitude)[-5:][::-1]
        
        joint_names = [
            "left_hip_pitch", "left_hip_roll", "left_hip_yaw", "left_knee", 
            "left_ankle_pitch", "left_ankle_roll",
            "right_hip_pitch", "right_hip_roll", "right_hip_yaw", "right_knee",
            "right_ankle_pitch", "right_ankle_roll",
            "waist_yaw", "waist_roll", "waist_pitch",
            # Arms...
        ]
        
        print("Most active joints:")
        for i, idx in enumerate(most_active_joints, 1):
            joint_name = joint_names[idx] if idx < len(joint_names) else f"joint_{idx}"
            print(f"  {i}. {joint_name}: {vel_magnitude[idx]:.3f} rad/s")
        
        print("\n" + "="*70)
        print(f"📁 Full data saved to: {self.filename}")
        print("\nNext steps:")
        print("  1. Run: python analyze_robot_data.py " + str(self.filename))
        print("  2. Review plots and recommendations")
        print("  3. Update training config based on findings")
        print("="*70)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Log real robot data')
    parser.add_argument('--duration', type=int, default=30, 
                       help='Duration to log in seconds (default: 30)')
    args = parser.parse_args()
    
    logger = StandaloneDataLogger(duration_seconds=args.duration)
    logger.run()
