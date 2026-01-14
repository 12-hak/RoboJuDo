#!/usr/bin/env python3
"""
Real Robot Data Logger for Sim-to-Real Analysis
Collects observations, actions, and robot state for comparison with simulation
"""
import numpy as np
import h5py
import time
from datetime import datetime
from pathlib import Path


class RobotDataLogger:
    """Logs real robot data for sim-to-real analysis"""
    
    def __init__(self, output_dir="robot_data_logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = self.output_dir / f"robot_data_{timestamp}.h5"
        
        # Data buffers
        self.data = {
            'timestamps': [],
            'observations': [],
            'actions_raw': [],  # From policy
            'actions_sent': [],  # After scaling/smoothing
            'dof_pos': [],
            'dof_vel': [],
            'dof_pos_target': [],
            'base_quat': [],
            'base_ang_vel': [],
            'base_lin_vel': [],
            'projected_gravity': [],
            'commands': [],  # User commands
            'policy_config': {},  # Store config once
        }
        
        self.step_count = 0
        print(f"📊 Data logger initialized: {self.filename}")
    
    def log_step(self, env_data, policy_output, commands, config=None):
        """Log one timestep of data"""
        self.data['timestamps'].append(time.time())
        self.data['dof_pos'].append(env_data.dof_pos.copy())
        self.data['dof_vel'].append(env_data.dof_vel.copy())
        self.data['base_quat'].append(env_data.base_quat.copy())
        self.data['base_ang_vel'].append(env_data.base_ang_vel.copy())
        
        # Handle base_lin_vel
        if hasattr(env_data, 'base_lin_vel') and env_data.base_lin_vel is not None:
            self.data['base_lin_vel'].append(env_data.base_lin_vel.copy())
        else:
            self.data['base_lin_vel'].append(np.zeros(3))
        
        # Log actions
        if isinstance(policy_output, dict):
            self.data['actions_raw'].append(policy_output.get('raw_action', np.zeros(29)))
            self.data['actions_sent'].append(policy_output.get('final_action', np.zeros(29)))
        else:
            self.data['actions_sent'].append(policy_output.copy())
            self.data['actions_raw'].append(policy_output.copy())
        
        # Log commands
        self.data['commands'].append(np.array(commands))
        
        # Store config once
        if config and not self.data['policy_config']:
            self.data['policy_config'] = {
                'action_scale': config.get('action_scale', 0.0),
                'action_beta': config.get('action_beta', 0.0),
                'action_clip': config.get('action_clip', 0.0),
            }
        
        self.step_count += 1
        
        # Auto-save every 100 steps
        if self.step_count % 100 == 0:
            print(f"📝 Logged {self.step_count} steps...")
    
    def save(self):
        """Save collected data to HDF5"""
        print(f"\n💾 Saving {self.step_count} samples to {self.filename}")
        
        with h5py.File(self.filename, 'w') as f:
            # Save time series data
            for key, values in self.data.items():
                if key == 'policy_config':
                    # Save config as attributes
                    for cfg_key, cfg_val in values.items():
                        f.attrs[cfg_key] = cfg_val
                elif values:  # Only save non-empty lists
                    f.create_dataset(key, data=np.array(values))
            
            # Add metadata
            f.attrs['num_samples'] = self.step_count
            f.attrs['duration_s'] = self.data['timestamps'][-1] - self.data['timestamps'][0] if self.data['timestamps'] else 0
            f.attrs['collection_date'] = datetime.now().isoformat()
        
        print(f"✅ Saved to {self.filename}")
        return self.filename
    
    def analyze_and_save(self):
        """Analyze data and save with summary"""
        filename = self.save()
        
        # Quick analysis
        print("\n" + "="*60)
        print("📊 DATA ANALYSIS")
        print("="*60)
        
        if self.data['timestamps']:
            duration = self.data['timestamps'][-1] - self.data['timestamps'][0]
            print(f"Duration: {duration:.2f}s")
            print(f"Samples: {self.step_count}")
            print(f"Frequency: {self.step_count/duration:.1f}Hz")
        
        if self.data['dof_vel']:
            dof_vel = np.array(self.data['dof_vel'])
            print(f"\nJoint Velocities:")
            print(f"  Mean: {np.abs(dof_vel).mean():.3f} rad/s")
            print(f"  Max: {np.abs(dof_vel).max():.3f} rad/s")
        
        if self.data['actions_sent']:
            actions = np.array(self.data['actions_sent'])
            print(f"\nActions Sent:")
            print(f"  Mean: {np.abs(actions).mean():.3f}")
            print(f"  Max: {np.abs(actions).max():.3f}")
            print(f"  Range: [{actions.min():.3f}, {actions.max():.3f}]")
        
        if self.data['base_lin_vel']:
            base_vel = np.array(self.data['base_lin_vel'])
            print(f"\nBase Linear Velocity:")
            print(f"  Forward (x): {base_vel[:, 0].mean():.3f} m/s")
            print(f"  Lateral (y): {base_vel[:, 1].mean():.3f} m/s")
        
        print("\n" + "="*60)
        print(f"📁 Data file: {filename}")
        print("="*60)
        
        return filename


# Integration example for your pipeline
def integrate_logger_example():
    """
    Example of how to integrate into your pipeline
    """
    logger = RobotDataLogger()
    
    # In your control loop:
    for step in range(1000):
        # Get observation
        obs, extras = policy.get_observation(env_data, ctrl_data)
        
        # Get action
        action = policy.get_action(obs)
        
        # Log the data
        logger.log_step(
            env_data=env_data,
            policy_output={'raw_action': action, 'final_action': action},
            commands=extras['commands'],
            config={
                'action_scale': policy.action_scale,
                'action_beta': policy.action_beta,
                'action_clip': policy.action_clip,
            }
        )
        
        # Execute action
        env.step(action)
    
    # Save when done
    logger.analyze_and_save()


if __name__ == "__main__":
    print("Robot Data Logger - Ready to integrate into pipeline")
    print("\nUsage:")
    print("1. Import: from robot_data_logger import RobotDataLogger")
    print("2. Create: logger = RobotDataLogger()")
    print("3. Log: logger.log_step(env_data, action, commands, config)")
    print("4. Save: logger.analyze_and_save()")
