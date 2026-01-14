from robojudo.policy.mjlab_policy_cfg import MjlabLocoPolicyCfg
from robojudo.tools.tool_cfgs import DoFConfig


class G1_29MjlabDoF(DoFConfig):
    """G1 29 DOF configuration (full body with wrists)"""
    
    joint_names: list[str] = [
        *[
            "left_hip_pitch_joint",
            "left_hip_roll_joint",
            "left_hip_yaw_joint",
            "left_knee_joint",
            "left_ankle_pitch_joint",
            "left_ankle_roll_joint",
        ],
        *[
            "right_hip_pitch_joint",
            "right_hip_roll_joint",
            "right_hip_yaw_joint",
            "right_knee_joint",
            "right_ankle_pitch_joint",
            "right_ankle_roll_joint",
        ],
        *["waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"],
        *[
            "left_shoulder_pitch_joint",
            "left_shoulder_roll_joint",
            "left_shoulder_yaw_joint",
            "left_elbow_joint",
            "left_wrist_roll_joint",
            "left_wrist_pitch_joint",
            "left_wrist_yaw_joint",
        ],
        *[
            "right_shoulder_pitch_joint",
            "right_shoulder_roll_joint",
            "right_shoulder_yaw_joint",
            "right_elbow_joint",
            "right_wrist_roll_joint",
            "right_wrist_pitch_joint",
            "right_wrist_yaw_joint",
        ],
    ]
    
    default_pos: list[float] | None = [
        *[-0.1, 0.0, 0.0, 0.3, -0.2, 0.0],
        *[-0.1, 0.0, 0.0, 0.3, -0.2, 0.0],
        *[0.0, 0.0, 0.0],
        *[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        *[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ]
    
    stiffness: list[float] | None = [
        *[150, 150, 150, 300, 60, 20],  # Legs
        *[150, 150, 150, 300, 60, 20],
        *[400, 400, 400],  # Waist: moderate (actions are scaled down instead)
        *[100, 100, 80, 80, 20, 20, 20],  # Arms
        *[100, 100, 80, 80, 20, 20, 20],
    ]
    
    damping: list[float] | None = [
        *[2.5, 2.5, 2.5, 5, 2, 1],  # Legs
        *[2.5, 2.5, 2.5, 5, 2, 1],
        *[20, 20, 20],  # Waist: moderate (actions are scaled down instead)
        *[2, 2, 1, 1, 1, 1, 1],  # Arms
        *[2, 2, 1, 1, 1, 1, 1],
    ]
    
    torque_limits: list[float] | None = [
        *[88, 139, 88, 139, 50, 50],
        *[88, 139, 88, 139, 50, 50],
        *[88, 50, 50],
        *[25, 25, 25, 25, 10, 10, 10],
        *[25, 25, 25, 25, 10, 10, 10],
    ]


class G1MjlabLocoPolicyCfg(MjlabLocoPolicyCfg):
    """G1-specific mjlab locomotion policy configuration"""
    robot: str = "g1"
    
    policy_name: str = "g1_velocity"
    relative_path: str = "g1_velocity.onnx"
    
    obs_dof: DoFConfig = G1_29MjlabDoF()
    action_dof: DoFConfig = G1_29MjlabDoF()  # Full body control
    
    # ===== BALANCED SIM-TO-REAL CONFIGURATION =====
    
    # Action scale - increased for better balance
    action_scale: float = 0.18  # Increased from 0.16 for better balance
    
    # VERY HEAVY smoothing to prevent wild corrections
    action_beta: float = 0.75  # Strong smoothing (75% new, 25% old) - prevents jerky movements
    
    # Conservative action clipping
    action_clip: float = 40.0
    
    # Increased commands for better responsiveness
    commands_map: list[list[float]] = [
        [-1.0, 0.0, 1.0],   # lin_vel_x: forward/back (increased)
        [0.8, 0.0, -0.8],   # lin_vel_y: left/right (NEGATED to fix direction)
        [-0.5, 0.0, 0.5],   # ang_vel_z: turning (increased)
    ]
    
    # Observation scales - match training
    obs_scales: MjlabLocoPolicyCfg.ObsScalesCfg = MjlabLocoPolicyCfg.ObsScalesCfg(
        ang_vel=0.25,
        dof_vel=0.05,
        dof_pos=1.0,
        projected_gravity=1.0,
        command_lin_vel=1.0,
        command_ang_vel=1.0,
    )
