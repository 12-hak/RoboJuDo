import logging
import numpy as np
import onnxruntime as ort

from robojudo.policy import Policy, policy_registry
from robojudo.policy.mjlab_policy_cfg import MjlabLocoPolicyCfg
from robojudo.utils.util_func import command_remap, quat_rotate_inverse_np

logger = logging.getLogger(__name__)


@policy_registry.register
class MjlabLocoPolicy(Policy):
    """Mjlab-trained locomotion policy using ONNX runtime"""
    
    cfg_policy: MjlabLocoPolicyCfg
    
    def __init__(self, cfg_policy: MjlabLocoPolicyCfg, device):
        import os
        if not os.path.isfile(cfg_policy.policy_file):
            raise FileNotFoundError(f"Model file not found at {cfg_policy.policy_file}")
        
        logger.info(f"Loading mjlab policy from {cfg_policy.policy_file}")
        self.session = ort.InferenceSession(cfg_policy.policy_file)
        
        self.input_names = [i.name for i in self.session.get_inputs()]
        self.output_names = [o.name for o in self.session.get_outputs()]
        
        logger.info(f"Model inputs: {self.input_names}")
        logger.info(f"Model outputs: {self.output_names}")
        
        super().__init__(cfg_policy=cfg_policy, device=device)
        
        self.obs_scales = cfg_policy.obs_scales
        self.commands_map = cfg_policy.commands_map
        
        self.reset()
    
    def reset(self):
        self.timestep: int = 0
        self.lin_vel_command = np.array([0.0, 0.0], dtype=np.float32)
        self.ang_vel_command = np.array([0.0], dtype=np.float32)
        self.last_action = np.zeros(self.num_actions, dtype=np.float32)
    
    def post_step_callback(self, commands: list[str] | None = None):
        self.timestep += 1
    
    def get_observation(self, env_data, ctrl_data):
        self._update_commands(ctrl_data)
        
        base_quat = env_data.base_quat  # [x, y, z, w]
        base_ang_vel = env_data.base_ang_vel
        # Get base_lin_vel from environment (should be available in real robot env)
        base_lin_vel = env_data.base_lin_vel if env_data.base_lin_vel is not None else np.zeros(3, dtype=np.float32)
        dof_pos = env_data.dof_pos
        dof_vel = env_data.dof_vel
        
        dof_pos_minus_default = dof_pos - self.default_dof_pos
        
        v = np.array([0, 0, -1])
        projected_gravity = quat_rotate_inverse_np(base_quat, v)
        
        # Build observation in EXACT MJLAB TRAINING ORDER (99 dims total)
        # This matches the policy_terms order from velocity_env_cfg.py lines 40-68
        obs = np.concatenate([
            # 1. base_lin_vel (3) - linear velocity in base frame
            base_lin_vel.astype(np.float32),  # No scaling in training config
            
            # 2. base_ang_vel (3) - angular velocity
            (base_ang_vel * self.obs_scales.ang_vel).astype(np.float32),
            
            # 3. projected_gravity (3) - gravity vector in base frame
            (projected_gravity * self.obs_scales.projected_gravity).astype(np.float32),
            
            # 4. joint_pos (29) - joint positions relative to default
            (dof_pos_minus_default * self.obs_scales.dof_pos).astype(np.float32),
            
            # 5. joint_vel (29) - joint velocities
            (dof_vel * self.obs_scales.dof_vel).astype(np.float32),
            
            # 6. actions (29) - previous actions
            self.last_action.astype(np.float32),
            
            # 7. command (3) - velocity commands [lin_vel_x, lin_vel_y, ang_vel_z]
            np.array([
                self.lin_vel_command[0],  # lin_vel_x (forward/back)
                self.lin_vel_command[1],  # lin_vel_y (left/right)
                self.ang_vel_command[0],  # ang_vel_z (turning)
            ], dtype=np.float32),
            
            # Total: 3 + 3 + 3 + 29 + 29 + 29 + 3 = 99 ✓
        ], axis=0)
        
        extras = {
            "commands": [self.lin_vel_command[0], self.lin_vel_command[1], self.ang_vel_command[0]],
        }
        return obs, extras
    
    def get_action(self, obs: np.ndarray) -> np.ndarray:
        # Use the actual input name from the ONNX model
        input_name = self.input_names[0] if self.input_names else "obs"
        
        ort_inputs = {
            input_name: np.expand_dims(obs, axis=0).astype(np.float32),
        }
        
        ort_outputs = self.session.run(
            [self.output_names[0]],  # Use actual output name from model
            ort_inputs,
        )
        actions: np.ndarray = np.asarray(ort_outputs[0]).squeeze()
        
        processed_actions = actions
        if self.action_clip is not None:
            processed_actions = np.clip(processed_actions, -self.action_clip, self.action_clip)
        
        self.last_action = actions.copy()
        
        # Apply action scale with per-joint scaling
        # Reduce waist actions to prevent wobble while keeping other joints normal
        # Joint order: legs(12), waist(3), arms(14)
        action_scales = np.ones(29, dtype=np.float32) * self.action_scale
        action_scales[12:15] *= 0.4  # Reduce waist to 40% to eliminate wobble (was 50%)
        
        processed_actions = processed_actions * action_scales
        return processed_actions
    
    def _update_commands(self, ctrl_data):
        for key in ctrl_data.keys():
            if key in ["JoystickCtrl", "UnitreeCtrl"]:
                axes = ctrl_data[key]["axes"]
                lx, ly, rx, _ry = axes["LeftX"], axes["LeftY"], axes["RightX"], axes["RightY"]
                
                # Map joystick to velocity commands
                # commands_map[0] = lin_vel_x range (forward/back)
                # commands_map[1] = lin_vel_y range (left/right)
                # commands_map[2] = ang_vel_z range (turning)
                self.lin_vel_command[0] = command_remap(ly, self.commands_map[0])  # forward/back
                self.lin_vel_command[1] = command_remap(lx, self.commands_map[1])  # left/right
                self.ang_vel_command[0] = command_remap(rx, self.commands_map[2])  # turning
                
                break
            elif key == "KeyboardCtrl":
                for event in ctrl_data[key]["keyboard_event"]:
                    if event["type"] == "keyboard" and event["pressed"]:
                        match event["name"]:
                            case "w":
                                self.lin_vel_command[0] += 0.1
                            case "s":
                                self.lin_vel_command[0] -= 0.1
                            case "a":
                                self.lin_vel_command[1] += 0.1
                            case "d":
                                self.lin_vel_command[1] -= 0.1
                            case "q":
                                self.ang_vel_command[0] -= 0.1
                            case "e":
                                self.ang_vel_command[0] += 0.1
                            case "z":
                                self.ang_vel_command[0] = 0.0
                                self.lin_vel_command[0] = 0.0
                                self.lin_vel_command[1] = 0.0
