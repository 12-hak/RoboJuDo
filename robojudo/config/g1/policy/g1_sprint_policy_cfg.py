from robojudo.policy.mjlab_policy_cfg import MjlabLocoPolicyCfg
from robojudo.tools.tool_cfgs import DoFConfig


class G1_29SprintDoF(DoFConfig):
    """G1 29 DOF configuration for sprint model"""
    
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
        *[-0.20, 0.0, 0.0, 0.30, -0.20, 0.0], # Balanced Posture
        *[-0.20, 0.0, 0.0, 0.30, -0.20, 0.0],
        *[0.0, 0.0, 0.0], # Torso Upright
        *[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],


        *[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ]


    
    # Safe & Stable Tuning
    stiffness: list[float] | None = [
        *[100, 100, 100, 120, 40, 20],  # Moderate Stiffness
        *[100, 100, 100, 120, 40, 20],


        *[300, 300, 300],  # Waist
        *[100, 100, 80, 80, 20, 20, 20],  # Arms
        *[100, 100, 80, 80, 20, 20, 20],
    ]



    
    damping: list[float] | None = [
        *[6.0, 6.0, 6.0, 8.0, 3.0, 2.0],  # High Damping for Stability
        *[6.0, 6.0, 6.0, 8.0, 3.0, 2.0],


        *[15, 15, 15],  # Waist

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


class G1SprintLocoPolicyCfg(MjlabLocoPolicyCfg):
    """G1 Sprint locomotion policy - retrained with sim-to-real improvements"""
    robot: str = "g1"
    
    policy_type: str = "SprintLocoPolicy"  # Use SprintLocoPolicy, not MjlabLocoPolicy
    
    policy_name: str = "g1_sprint"
    relative_path: str = "g1_sprint.onnx"
    
    obs_dof: DoFConfig = G1_29SprintDoF()
    action_dof: DoFConfig = G1_29SprintDoF()
    
    # ===== CONSERVATIVE STARTING CONFIGURATION =====
    # Model was trained with improvements, but start gentle and tune up
    
    # Action scale - Safe
    action_scale: float = 0.50

    
    # Smooth control
    action_beta: float = 0.40  
    
    # Normal action clipping
    action_clip: float = 100.0  





    
    # Command speeds - turning direction FIXED
    commands_map: list[list[float]] = [
        [-1.2, 0.0, 1.2],   # lin_vel_x: increased forward/back
        [1.0, 0.0, -1.0],   # lin_vel_y: increased left/right
        [0.8, 0.0, -0.8],   # ang_vel_z: NEGATED to fix turning direction
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
