from robojudo.config import Config
from robojudo.policy.policy_cfgs import PolicyCfg
from robojudo.tools.tool_cfgs import DoFConfig


class MjlabLocoPolicyCfg(PolicyCfg):
    """Configuration for mjlab-trained locomotion policy (ONNX)"""
    
    policy_type: str = "MjlabLocoPolicy"
    disable_autoload: bool = True
    
    policy_name: str
    relative_path: str
    
    @property
    def policy_file(self) -> str:
        from robojudo.config import ASSETS_DIR
        policy_file = ASSETS_DIR / f"models/{self.robot}/mjlab/{self.policy_name}/{self.relative_path}"
        return policy_file.as_posix()
    
    # ======= POLICY SPECIFIC CONFIGURATION =======
    class ObsScalesCfg(Config):
        ang_vel: float = 0.25
        dof_vel: float = 0.05
        dof_pos: float = 1.0
        projected_gravity: float = 1.0
        command_lin_vel: float = 1.0
        command_ang_vel: float = 1.0
    
    action_scale: float = 0.25
    action_clip: float | None = 100.0
    obs_scales: ObsScalesCfg = ObsScalesCfg()
    
    # Mjlab model expects 99 observations, no history
    USE_HISTORY: bool = False
    
    # Command mapping for joystick control
    commands_map: list[list[float]] = [
        [-1.5, 0.0, 1.5],  # vel_y (forward/backward)
        [1.0, 0.0, -1.0],  # ang_z (turning)
        [1.0, 0.0, -1.0],  # vel_x (left/right)
    ]
