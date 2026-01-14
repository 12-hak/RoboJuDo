from robojudo.config import cfg_registry
from robojudo.controller.ctrl_cfgs import (
    JoystickCtrlCfg,  # noqa: F401
    KeyboardCtrlCfg,  # noqa: F401
    UnitreeCtrlCfg,  # noqa: F401
)
from robojudo.pipeline.pipeline_cfgs import (
    RlLocoMimicPipelineCfg,  # noqa: F401
    RlMultiPolicyPipelineCfg,  # noqa: F401
    RlPipelineCfg,  # noqa: F401
)

from .ctrl.g1_beyondmimic_ctrl_cfg import G1BeyondmimicCtrlCfg  # noqa: F401
from .ctrl.g1_motion_ctrl_cfg import (  # noqa: F401
    G1MotionCtrlCfg,
    G1MotionH2HCtrlCfg,
    G1MotionKungfuBotCtrlCfg,
    G1MotionTwistCtrlCfg,
)
from .ctrl.g1_twist_redis_ctrl_cfg import G1TwistRedisCtrlCfg  # noqa: F401
from .env.g1_dummy_env_cfg import G1DummyEnvCfg  # noqa: F401
from .env.g1_mujuco_env_cfg import G1_12MujocoEnvCfg, G1_23MujocoEnvCfg, G1MujocoEnvCfg  # noqa: F401
from .env.g1_real_env_cfg import G1RealEnvCfg, G1UnitreeCfg  # noqa: F401
from .pipeline.g1_locomimic_pipeline_cfg import G1RlLocoMimicPipelineCfg  # noqa: F401
from .policy.g1_amo_policy_cfg import G1AmoPolicyCfg, G1MjlabAmoPolicyCfg  # noqa: F401
from .policy.g1_asap_policy_cfg import G1AsapLocoPolicyCfg, G1AsapPolicyCfg  # noqa: F401
from .policy.g1_beyondmimic_policy_cfg import G1BeyondMimicPolicyCfg  # noqa: F401
from .policy.g1_h2h_policy_cfg import G1H2HPolicyCfg  # noqa: F401
from .policy.g1_kungfubot_policy_cfg import G1KungfuBotGeneralPolicyCfg, G1KungfuBotPolicyCfg  # noqa: F401
from .policy.g1_mjlab_policy_cfg import G1MjlabLocoPolicyCfg  # noqa: F401
from .policy.g1_sprint_policy_cfg import G1SprintLocoPolicyCfg  # noqa: F401
from .policy.g1_smooth_policy_cfg import G1SmoothPolicyCfg  # noqa: F401
from .policy.g1_twist_policy_cfg import G1TwistPolicyCfg  # noqa: F401
from .policy.g1_unitree_policy_cfg import G1UnitreePolicyCfg, G1UnitreeWoGaitPolicyCfg  # noqa: F401

# ================= LocoMotion + MotionMimic Policy Switch Configs ================= #


@cfg_registry.register
class g1_locomimic_beyondmimic(G1RlLocoMimicPipelineCfg):
    """
    Smooth switch between multiple BeyondMimic policies, Sim2Sim.
    """

    robot: str = "g1"
    env: G1MujocoEnvCfg = G1MujocoEnvCfg()
    ctrl: list[KeyboardCtrlCfg | JoystickCtrlCfg] = [
        KeyboardCtrlCfg(
            triggers={
                "i": "[SIM_REBORN]",
                "o": "[SHUTDOWN]",
                "]": "[POLICY_LOCO]",
                "[": "[POLICY_MIMIC]",
                ";": "[POLICY_SWITCH],NEXT",
                "'": "[POLICY_SWITCH],LAST",
            }
        ),
        # JoystickCtrlCfg(
        #     combination_init_buttons=[],
        #     triggers={
        #         "A": "[SHUTDOWN]",
        #         "Back": "[POLICY_LOCO]",
        #         "Start": "[POLICY_MIMIC]",
        #         "RB": "[POLICY_SWITCH],NEXT",
        #         "LB": "[POLICY_SWITCH],LAST",
        #     },
        # ),
    ]

    loco_policy: G1AmoPolicyCfg = G1AmoPolicyCfg()
    # loco_policy: G1AsapLocoPolicyCfg = G1AsapLocoPolicyCfg()
    # loco_policy: G1UnitreePolicyCfg = G1UnitreePolicyCfg()
    # loco_policy: G1UnitreeWoGaitPolicyCfg = G1UnitreeWoGaitPolicyCfg()
    """Any LocoMotion policy, as init"""

    mimic_policies: list[G1BeyondMimicPolicyCfg] = [
        #G1BeyondMimicPolicyCfg(policy_name="Dance_wose", without_state_estimator=True),
        G1BeyondMimicPolicyCfg(policy_name="Violin", without_state_estimator=False, max_timestep=500)
        #G1BeyondMimicPolicyCfg(policy_name="Waltz", without_state_estimator=False, max_timestep=850),
    ]


@cfg_registry.register
class g1_locomimic_asap(G1RlLocoMimicPipelineCfg):
    """
    Unitree G1 robot configuration, ASAP Locomotion + Deepmimic, Sim2Sim.
    Dynamic switch, keyboard control.
    """

    robot: str = "g1"
    env: G1MujocoEnvCfg = G1MujocoEnvCfg(forward_kinematic=None, update_with_fk=False, born_place_align=True)

    ctrl: list[KeyboardCtrlCfg | JoystickCtrlCfg] = [  # note: the ranking of controllers matters
        KeyboardCtrlCfg(
            triggers={
                "i": "[SIM_REBORN]",
                "o": "[SHUTDOWN]",
                "]": "[POLICY_LOCO]",
                "[": "[POLICY_MIMIC]",
                ";": "[POLICY_SWITCH],NEXT",
                "'": "[POLICY_SWITCH],LAST",
            }
        ),
        # JoystickCtrlCfg(
        #     combination_init_buttons=[],
        #     triggers={
        #         "A": "[SHUTDOWN]",
        #         "Back": "[POLICY_LOCO]",
        #         "Start": "[POLICY_MIMIC]",
        #         "RB": "[POLICY_SWITCH],NEXT",
        #         "LB": "[POLICY_SWITCH],LAST",
        #     },
        # ),
    ]

    loco_policy: G1AsapLocoPolicyCfg = G1AsapLocoPolicyCfg()

    # fmt: off
    mimic_policies: list[G1AsapPolicyCfg] = [
        G1AsapPolicyCfg(), # default CR7_level1
        G1AsapPolicyCfg(
            policy_name="robomimic",
            relative_path="dance_0605.onnx",
            motion_length_s=18.0,
            start_upper_body_dof_pos = [
                0, 0, 0,
                0.35, 0.18, 0, 0.87, 
                0.35, -0.18, 0, 0.87,
            ],
        ),
        G1KungfuBotPolicyCfg(),
    ]
    # fmt: on


# ================= LocoMimic Policy Switch Sim2real Configs ================= #


@cfg_registry.register
class g1_locomimic_beyondmimic_real(g1_locomimic_beyondmimic):
    """
    Locomotion + Beyondmimic, Sim2Real.
    Warning: Make sure the policy is stable for real robot before using it.
    """

    env: G1RealEnvCfg = G1RealEnvCfg(
        # env_type="UnitreeEnv",  # For unitree_sdk2py (Python SDK)
        env_type="UnitreeCppEnv",  # For unitree_cpp, check README for more details
        unitree=G1UnitreeCfg(
            net_if="eth0",  # note: change to your network interface
            delay_mode_release=True,  # CRITICAL: Keep robot in sport mode until prepare completes
        ),
    )

    # Slower interpolation for smoother, more stable transitions on real robot
    durations_loco_mimic: list[int] = [0, 150, 50]  # [start, in-progress, end] in steps (~3s at 50Hz)
    durations_mimic_loco: list[int] = [50, 150, 0]  # [start, in-progress, end] in steps (~3s at 50Hz)
    ctrl: list[UnitreeCtrlCfg] = [
        UnitreeCtrlCfg(
            combination_init_buttons=[],
            triggers={
                "A": "[SHUTDOWN]",
                "Select": "[POLICY_LOCO]",
                "Start": "[POLICY_MIMIC]",
                "R1": "[POLICY_SWITCH],NEXT",
                "L1": "[POLICY_SWITCH],LAST",
            },
        ),
    ]

    # Add all available beyondmimic ONNX policies with stability improvements
    mimic_policies: list[G1BeyondMimicPolicyCfg] = [
        # Dance_wose: Most unstable, needs aggressive smoothing and slower transitions
        G1BeyondMimicPolicyCfg(
            policy_name="Dance_wose",
            without_state_estimator=True,
            action_beta=0.4,  # Lower = more smoothing (default 1.0)
            max_timestep=1000,
            action_scales=[  # Reduced by 25% for stability
                *[0.41, 0.41, 0.41, 0.26, 0.26, 0.33, 0.41, 0.41, 0.33, 0.26, 0.26],
                *[0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33],
                *[0.33, 0.33, 0.33, 0.33, 0.056, 0.056, 0.056, 0.056],
            ],
        ),
        # Jump_wose: Very unstable, needs most aggressive smoothing
        G1BeyondMimicPolicyCfg(
            policy_name="Jump_wose",
            without_state_estimator=True,
            action_beta=0.8,  # Increased for more responsive jump
            max_timestep=1000,
            action_scales=[  # Restored to full scales
                *[0.548, 0.548, 0.548, 0.351, 0.351, 0.439, 0.548, 0.548, 0.439, 0.351, 0.351],
                *[0.439, 0.439, 0.439, 0.439, 0.439, 0.439, 0.439, 0.439, 0.439, 0.439],
                *[0.439, 0.439, 0.439, 0.439, 0.075, 0.075, 0.075, 0.075],
            ],
        ),
        # Violin: Original settings restored
        G1BeyondMimicPolicyCfg(
            policy_name="Violin",
            without_state_estimator=False,
            max_timestep=1000,
        ),
        # Waltz: Stable but add some smoothing for consistency
        G1BeyondMimicPolicyCfg(
            policy_name="Waltz",
            without_state_estimator=False,
            action_beta=0.7,  # Moderate smoothing for stability
            max_timestep=1000,
        ),
        # SpinKick_safe: Side kick motion, needs moderate smoothing
        G1BeyondMimicPolicyCfg(
            policy_name="spinkick_safe",
            without_state_estimator=True,  # Assuming _wose means without state estimator
            action_beta=0.5,  # Moderate smoothing for kick stability
            max_timestep=1000,
        ),
        # g1_run: Running motion
        G1BeyondMimicPolicyCfg(
            policy_name="g1_run",
            without_state_estimator=False,
            action_beta=0.7,
            max_timestep=1000,
        ),
    ]

    do_safety_check: bool = True  # enable safety check for real robot


@cfg_registry.register
class g1_locomimic_beyondmimic_real_v2(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real - V2 Pipeline.
    This version loads the locomotion policy FULLY before switching to developer mode,
    ensuring the policy is ready immediately when developer mode is entered.
    """

    # Override pipeline type to use the new V2 pipeline
    pipeline_type: str = "RlLocoMimicPipelineV2"
    
    # Ensure delay_mode_release is True for V2 pipeline
    env: G1RealEnvCfg = G1RealEnvCfg(
        env_type="UnitreeCppEnv",
        unitree=G1UnitreeCfg(
            net_if="eth0",
            delay_mode_release=True,  # CRITICAL: Must be True to prevent early mode release
        ),
    )


@cfg_registry.register
class g1_locomimic_beyondmimic_real_v2_stand(g1_locomimic_beyondmimic_real_v2):
    """
    Locomotion + Beyondmimic, Sim2Real - V2 Pipeline with Auto-Standing.
    This version will automatically transition the robot back to a stable standing
    state in sport mode (FSM 801) when the script finishes or 'A' is pressed.
    """
    stand_at_end: bool = True


@cfg_registry.register
class g1_locomimic_beyondmimic_real_enhanced(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with height control.
    
    Controls:
    - Left stick: Forward/Backward, Left/Right movement
    - Right stick X: Turn left/right (angular velocity)
    - Up button: Increase height
    - Down button: Decrease height
    """
    
    # Override loco_policy to use AMO config with height control
    loco_policy: G1AmoPolicyCfg = G1AmoPolicyCfg(
        commands_map=[
            [-1.0, 0.0, 1.0],      # vel_y (forward/backward)
            [0.2, 0.0, -0.2],      # ang_z (yaw/turn)
            [0.8, 0.0, -0.8],      # vel_x (left/right)
            [0.3, 0.75, 0.9],      # height
        ],
    )


@cfg_registry.register
class g1_locomimic_asap_real(g1_locomimic_asap):
    """
    ASAP Locomotion + Deepmimic, Sim2Real.
    Warning: Make sure the policy is stable for real robot before using it.
    """

    # env: G1DummyEnvCfg = G1DummyEnvCfg()
    env: G1RealEnvCfg = G1RealEnvCfg(
        # env_type="UnitreeEnv",  # For unitree_sdk2py
        env_type="UnitreeCppEnv",  # For unitree_cpp, check README for more details
        unitree=G1UnitreeCfg(
            net_if="eth0",  # note: change to your network interface
        ),
    )

    ctrl: list[UnitreeCtrlCfg] = [
        UnitreeCtrlCfg(
            combination_init_buttons=[],
            triggers={
                "A": "[SHUTDOWN]",
                "Select": "[POLICY_LOCO]",
                "Start": "[POLICY_MIMIC]",
                "R1": "[POLICY_SWITCH],NEXT",
                "L1": "[POLICY_SWITCH],LAST",
            },
        ),
    ]

    do_safety_check: bool = True  # enable safety check for real robot


# ================= ASAP Policy  ================= #
@cfg_registry.register
class g1_locomimic_asap_full(G1RlLocoMimicPipelineCfg):
    """
    Exact reproduce of the original ASAP code.
    You need to download the model files from the official repo and put them in assets/models/g1/asap
    """

    robot: str = "g1"
    env: G1MujocoEnvCfg = G1MujocoEnvCfg(forward_kinematic=None, update_with_fk=False, born_place_align=True)

    ctrl: list[KeyboardCtrlCfg | JoystickCtrlCfg] = [  # note: the ranking of controllers matters
        KeyboardCtrlCfg(
            triggers={
                "i": "[SIM_REBORN]",
                "o": "[SHUTDOWN]",
                "]": "[POLICY_LOCO]",
                "[": "[POLICY_MIMIC]",
                ";": "[POLICY_SWITCH],NEXT",
                "'": "[POLICY_SWITCH],LAST",
            }
        ),
    ]

    loco_policy: G1AsapLocoPolicyCfg = G1AsapLocoPolicyCfg()

    mimic_policies: list[G1AsapPolicyCfg] = []

    def __init__(self, **data) -> None:
        super().__init__(**data)
        # add all the asap policies in asap.yaml
        from pathlib import Path

        import yaml

        asap_config = yaml.safe_load(open(Path(__file__).parent / "asap.yaml"))
        for plicy_name, relative_path in asap_config["mimic_models"].items():
            start_upper_body_dof_pos = asap_config["start_upper_body_dof_pos"].get(plicy_name, None)
            # remove some joints that are not in the g1 23-dof model
            if start_upper_body_dof_pos is not None:
                start_upper_body_dof_pos = [start_upper_body_dof_pos[i] for i in [0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13]]
            motion_length_s = asap_config["motion_length_s"].get(plicy_name, 10.0)
            self.mimic_policies.append(
                G1AsapPolicyCfg(
                    policy_name=plicy_name,
                    relative_path=relative_path,
                    start_upper_body_dof_pos=start_upper_body_dof_pos,
                    motion_length_s=motion_length_s,
                )
            )


# ================= Locomotion Method Variants ================= #


@cfg_registry.register
class g1_locomimic_beyondmimic_real_amo(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with AMO locomotion policy.
    Uses AMO (Adaptive Motion Optimization) for locomotion.
    """
    loco_policy: G1AmoPolicyCfg = G1AmoPolicyCfg()


@cfg_registry.register
class g1_locomimic_beyondmimic_real_mjlab(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with custom mjlab-trained locomotion policy.
    Uses mjlab-trained ONNX policy for full-body locomotion (29 DOF).
    """
    loco_policy: G1MjlabLocoPolicyCfg = G1MjlabLocoPolicyCfg()


@cfg_registry.register
class g1_locomimic_beyondmimic_real_sprint(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with RETRAINED sprint locomotion policy.
    Uses g1_sprint model trained with sim-to-real improvements:
    - Waist movement penalty (no wobble)
    - Action smoothness penalty (smooth movements)
    - Better turning rewards (responsive turning)
    - Standing stability (balanced when idle)
    """
    loco_policy: G1SprintLocoPolicyCfg = G1SprintLocoPolicyCfg()


@cfg_registry.register
class g1_locomimic_beyondmimic_real_asap(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with ASAP locomotion policy.
    Uses ASAP (Adaptive Skill-based Agile Policies) for locomotion.
    """
    loco_policy: G1AsapLocoPolicyCfg = G1AsapLocoPolicyCfg()


@cfg_registry.register
class g1_locomimic_beyondmimic_real_smooth(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with Smooth locomotion policy.
    Uses Smooth policy for locomotion.
    """
    loco_policy: G1SmoothPolicyCfg = G1SmoothPolicyCfg()


@cfg_registry.register
class g1_locomimic_beyondmimic_real_unitree(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with Unitree locomotion policy.
    Uses Unitree's default policy for locomotion.
    """
    loco_policy: G1UnitreePolicyCfg = G1UnitreePolicyCfg()


@cfg_registry.register
class g1_locomimic_beyondmimic_real_unitree_wogait(g1_locomimic_beyondmimic_real):
    """
    Locomotion + Beyondmimic, Sim2Real with Unitree (without gait) locomotion policy.
    Uses Unitree policy without gait for locomotion.
    """
    loco_policy: G1UnitreeWoGaitPolicyCfg = G1UnitreeWoGaitPolicyCfg()


# ================= Fast Pipeline Configs (Optimized Policy Loading) ================= #

@cfg_registry.register
class g1_locomimic_beyondmimic_real_amo_fast(g1_locomimic_beyondmimic_real_amo):
    """
    Fast version: Locomotion + Beyondmimic with AMO locomotion policy.
    Uses optimized policy loading for faster startup.
    """
    pipeline_type: str = "RlLocoMimicPipelineFast"


@cfg_registry.register
class g1_locomimic_beyondmimic_real_asap_fast(g1_locomimic_beyondmimic_real_asap):
    """
    Fast version: Locomotion + Beyondmimic with ASAP locomotion policy.
    Uses optimized policy loading for faster startup.
    """
    pipeline_type: str = "RlLocoMimicPipelineFast"


@cfg_registry.register
class g1_locomimic_beyondmimic_real_smooth_fast(g1_locomimic_beyondmimic_real_smooth):
    """
    Fast version: Locomotion + Beyondmimic with Smooth locomotion policy.
    Uses optimized policy loading for faster startup.
    """
    pipeline_type: str = "RlLocoMimicPipelineFast"


@cfg_registry.register
class g1_locomimic_beyondmimic_real_unitree_fast(g1_locomimic_beyondmimic_real_unitree):
    """
    Fast version: Locomotion + Beyondmimic with Unitree locomotion policy.
    Uses optimized policy loading for faster startup.
    """
    pipeline_type: str = "RlLocoMimicPipelineFast"


@cfg_registry.register
class g1_locomimic_beyondmimic_real_unitree_wogait_fast(g1_locomimic_beyondmimic_real_unitree_wogait):
    """
    Fast version: Locomotion + Beyondmimic with Unitree (without gait) locomotion policy.
    Uses optimized policy loading for faster startup.
    """
    pipeline_type: str = "RlLocoMimicPipelineFast"
