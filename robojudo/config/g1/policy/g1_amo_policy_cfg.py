from robojudo.policy.policy_cfgs import AMOPolicyCfg
from robojudo.tools.tool_cfgs import DoFConfig


class G1AmoDoF(DoFConfig):
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
        *["left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint"],
        *["right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint"],
    ]

    default_pos: list[float] | None = [
        *[-0.1, 0.0, 0.0, 0.3, -0.2, 0.0],
        *[-0.1, 0.0, 0.0, 0.3, -0.2, 0.0],
        *[0.0, 0.0, 0.0],
        *[0.2, 0.0, 0.0, 0.6],  # Left arm: similar to beyondmimic (shoulder pitch 0.2, elbow 0.6)
        *[0.2, 0.0, 0.0, 0.6],  # Right arm: similar to beyondmimic (shoulder pitch 0.2, elbow 0.6)
    ]

    stiffness: list[float] | None = [
        *[150, 150, 150, 300, 80, 20],
        *[150, 150, 150, 300, 80, 20],
        *[400, 400, 400],
        *[100, 100, 80, 80],  # Left arm: high stiffness to ensure movement (testing)
        *[100, 100, 80, 80],  # Right arm: high stiffness to ensure movement (testing)
    ]

    damping: list[float] | None = [
        *[2, 2, 2, 4, 2, 1],
        *[2, 2, 2, 4, 2, 1],
        *[15, 15, 15],
        *[2, 2, 1, 1],
        *[2, 2, 1, 1],
    ]

    torque_limits: list[float] | None = [
        *[88, 139, 88, 139, 50, 50],
        *[88, 139, 88, 139, 50, 50],
        *[88, 50, 50],
        *[25, 25, 25, 25],
        *[25, 25, 25, 25],
    ]


class G1AmoLowerDoF(G1AmoDoF):
    _subset = True
    _subset_joint_names: list[str] | None = [
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
    ]


class G1AmoPolicyCfg(AMOPolicyCfg):
    robot: str = "g1"

    obs_dof: DoFConfig = G1AmoDoF()
    action_dof: DoFConfig = G1AmoLowerDoF()

    commands_map: list[list[float]] = [
        [-1.5, 0.0, 1.5],  # vel_y (forward/backward): increased to ±1.5 to match ASAP speed
        [1.0, 0.0, -1.0],  # ang_z (turning): increased to ±1.0 to match ASAP speed (was ±0.2)
        [1.0, 0.0, -1.0],  # vel_x (left/right): increased to ±1.0 to match ASAP speed (was ±0.8)
        [0.3, 0.75, 0.9],  # height
    ]


class G1MjlabAmoPolicyCfg(AMOPolicyCfg):
    """Custom AMO policy configuration for mjlab-trained locomotion model"""
    robot: str = "g1"

    obs_dof: DoFConfig = G1AmoDoF()
    action_dof: DoFConfig = G1AmoLowerDoF()

    @property
    def policy_file(self) -> str:
        from robojudo.config import ASSETS_DIR
        policy_file = ASSETS_DIR / f"models/{self.robot}/amo/mjlab_velocity.pt"
        return policy_file.as_posix()

    commands_map: list[list[float]] = [
        [-1.5, 0.0, 1.5],  # vel_y (forward/backward)
        [1.0, 0.0, -1.0],  # ang_z (turning)
        [1.0, 0.0, -1.0],  # vel_x (left/right)
        [0.3, 0.75, 0.9],  # height
    ]
