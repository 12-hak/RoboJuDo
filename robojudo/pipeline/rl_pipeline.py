import logging
import time

import numpy as np
from box import Box

import robojudo.environment
import robojudo.policy
from robojudo.controller import CtrlManager
from robojudo.environment import Environment
from robojudo.pipeline import Pipeline, pipeline_registry
from robojudo.pipeline.pipeline_cfgs import RlPipelineCfg
from robojudo.policy import Policy, PolicyCfg
from robojudo.tools.dof import DoFAdapter
from robojudo.tools.tool_cfgs import DoFConfig
from robojudo.utils.progress import ProgressBar
from robojudo.utils.util_func import get_gravity_orientation

logger = logging.getLogger(__name__)


class PolicyWrapper:
    """A wrapper for Policy to handle observation and action adaptation."""

    def __init__(self, cfg_policy: PolicyCfg, env_dof_cfg: DoFConfig, device: str):
        self.env_dof_cfg = env_dof_cfg

        policy_type = cfg_policy.policy_type
        policy_name = policy_type
        if hasattr(cfg_policy, "policy_name"):
            policy_name += "@" + cfg_policy.policy_name  # type: ignore
        # while policy_name in self.policies.keys():
        #     policy_name += "_new"
        self.name = policy_name

        policy_class: type[Policy] = getattr(robojudo.policy, policy_type)
        self.policy: Policy = policy_class(cfg_policy=cfg_policy, device=device)
        self.obs_adapter = DoFAdapter(env_dof_cfg.joint_names, self.policy.cfg_obs_dof.joint_names)
        self.actions_adapter = DoFAdapter(self.policy.cfg_action_dof.joint_names, env_dof_cfg.joint_names)

    def get_observation(self, env_data: Box, ctrl_data: Box):
        env_data_adapted = env_data.copy()
        env_data_adapted.dof_pos = self.obs_adapter.fit(env_data_adapted.dof_pos)
        env_data_adapted.dof_vel = self.obs_adapter.fit(env_data_adapted.dof_vel)
        return self.policy.get_observation(env_data_adapted, ctrl_data)

    def get_action(self, obs):
        action = self.policy.get_action(obs)
        return self.actions_adapter.fit(action)

    def get_pd_target(self, obs):
        # Check if policy has its own get_pd_target implementation (e.g., AMO policy with arm control)
        if hasattr(self.policy, 'get_pd_target') and callable(getattr(self.policy, 'get_pd_target', None)):
            # Policy has custom get_pd_target, use it directly (it handles full DOF including arms)
            pd_target = self.policy.get_pd_target(obs)
            # Policy's get_pd_target returns in obs_dof space, need to adapt to env_dof
            # Use reverse of obs_adapter (obs_dof -> env_dof)
            from robojudo.tools.dof import DoFAdapter
            obs_to_env_adapter = DoFAdapter(self.policy.cfg_obs_dof.joint_names, self.env_dof_cfg.joint_names)
            pd_target_env = obs_to_env_adapter.fit(pd_target, template=self.env_dof_cfg.default_pos)
            
            # Debug logging to verify arm positions are preserved after adaptation
            if hasattr(self.policy, '_n_demo_dof') and self.policy.timestep % 50 == 0:
                import logging
                logger = logging.getLogger(__name__)
                # Find arm joint indices in both spaces
                obs_arm_joints = self.policy.cfg_obs_dof.joint_names[-self.policy._n_demo_dof:]
                env_arm_joints = [name for name in obs_arm_joints if name in self.env_dof_cfg.joint_names]
                if env_arm_joints:
                    obs_arm_indices = [self.policy.cfg_obs_dof.joint_names.index(name) for name in obs_arm_joints]
                    env_arm_indices = [self.env_dof_cfg.joint_names.index(name) for name in env_arm_joints]
                    logger.info(f"PolicyWrapper: obs_arm_joints={obs_arm_joints[:4]}, "
                               f"obs_pd_target[arm]={pd_target[obs_arm_indices[:4]]}, "
                               f"env_arm_joints={env_arm_joints[:4]}, "
                               f"env_pd_target[arm]={pd_target_env[env_arm_indices[:4]]}")
            
            return pd_target_env
        else:
            # Standard implementation: action + default_pos
            action = self.policy.get_action(obs)
            
            # --- G1 STABILITY PATCH ---
            # Flip Hip Roll to fix leg spreading
            # Indices: 0-5 Left, 6-11 Right
            if action.shape[-1] >= 12: 
                 action[..., 1] *= -1.0 # Left Hip Roll
                 action[..., 7] *= -1.0 # Right Hip Roll
            # ---------------------------

            pd_target = action + self.policy.default_pos
            return self.actions_adapter.fit(pd_target, template=self.env_dof_cfg.default_pos)

    def get_init_dof_pos(self):
        return self.actions_adapter.fit(self.policy.get_init_dof_pos(), template=self.env_dof_cfg.default_pos)

    def __getattr__(self, name):
        """Fallback: delegate other func to the wrapped policy."""
        return getattr(self.policy, name)


@pipeline_registry.register
class RlPipeline(Pipeline):
    cfg: RlPipelineCfg

    def __init__(self, cfg: RlPipelineCfg):
        super().__init__(cfg=cfg)

        env_class: type[Environment] = getattr(robojudo.environment, self.cfg.env.env_type)
        self.env: Environment = env_class(cfg_env=self.cfg.env, device=self.device)

        self.ctrl_manager = CtrlManager(cfg_ctrls=self.cfg.ctrl, env=self.env, device=self.device)

        self.policy = PolicyWrapper(
            cfg_policy=self.cfg.policy,
            env_dof_cfg=self.env.dof_cfg,
            device=self.device,
        )

        self.env.update_dof_cfg(override_cfg=self.policy.cfg_action_dof)
        self.visualizer = self.env.visualizer

        self.freq = self.cfg.policy.freq
        self.dt = 1.0 / self.freq

        self.self_check()
        self.reset()

    def self_check(self):
        self.env.self_check()
        for _ in range(10):
            self.step(dry_run=True)

    def reset(self):
        logger.info("Pipeline reset")
        self.timestep = 0

        self.env.reset()
        # self.env.reborn(init_qpos=[0.2, 0.2, 0.8] + [ 0.707, 0, 0, 0.707]) # FOR SIM DEBUG
        self.policy.reset()
        self.ctrl_manager.reset()

    def safety_check(self):
        if not self.do_safety_check:
            return
        gravity_ori = get_gravity_orientation(self.env.base_quat)
        angle = np.arccos(np.clip(-gravity_ori[2], -1.0, 1.0))
        # Increase tolerance for active motions like running (from 1.0 to 1.3 rad / ~75 deg)
        if abs(angle) > 1.3:  
            logger.error("Robot fallen! Shutdown for safety.")
            if hasattr(self.env, "reborn"):
                self.env.reborn()  # pyright: ignore[reportAttributeAccessIssue]
            else:
                self.env.shutdown()

    def post_step_callback(self, env_data, ctrl_data, extras, pd_target):
        self.timestep += 1
        commands = ctrl_data.get("COMMANDS", [])
        for command in commands:
            match command:
                case "[SHUTDOWN]":
                    logger.warning("Emergency shutdown!")
                    self.env.shutdown()
                case "[SIM_REBORN]":
                    if hasattr(self.env, "reborn"):
                        logger.warning("Simulation Env reborn!")
                        self.env.reborn()  # pyright: ignore[reportAttributeAccessIssue]
                case "[RETURN_TO_SPORT]":
                    if hasattr(self.env, "select_sport_mode"):
                        logger.warning("Returning to sport mode!")
                        self.env.select_sport_mode()

        self.ctrl_manager.post_step_callback(ctrl_data)

        self.policy.post_step_callback(commands)
        if self.visualizer is not None:
            self.policy.debug_viz(self.visualizer, env_data, ctrl_data, extras)

        self.safety_check()
        if self.cfg.debug.log_obs:
            self.debug_logger.log(
                env_data=env_data,
                ctrl_data=ctrl_data,
                extras=extras,
                pd_target=pd_target,
                timestep=self.timestep,
            )

    def step(self, dry_run=False):
        self.env.update()
        env_data = self.env.get_data()

        ctrl_data = self.ctrl_manager.get_ctrl_data(env_data)

        commands = ctrl_data.get("COMMANDS", [])
        if len(commands) > 0:
            logger.info(f"{'=' * 10} COMMANDS {'=' * 10}\n{commands}")

        obs, extras = self.policy.get_observation(env_data, ctrl_data)
        pd_target = self.policy.get_pd_target(obs)

        if not dry_run:
            # RAMP UP ACTION SCALE (Smooth Start)
            target_scale = getattr(self.policy, 'target_action_scale', self.policy.action_scale) 
            if not hasattr(self.policy, 'target_action_scale'):
                 self.policy.target_action_scale = self.policy.action_scale
            
            # Ramp over first 100 steps
            ramp_factor = min(self.timestep / 100.0, 1.0)
            self.policy.action_scale = target_scale * ramp_factor

            self.env.step(pd_target, extras.get("hand_pose", None))

        self.post_step_callback(env_data, ctrl_data, extras, pd_target)

    def prepare(self, init_motor_angle=None):
        if init_motor_angle is not None:
            desired_motor_angle = init_motor_angle
        else:
            desired_motor_angle = self.policy.get_init_dof_pos()

        # logger.info(f"{desired_motor_angle=}")
        current_motor_angle = np.array(self.env.dof_pos)
        # logger.info(f"{current_motor_angle=}")

        # Check if we're in prepare mode (sport mode active, don't send commands)
        in_prepare_mode = hasattr(self.env, "_in_prepare_mode") and self.env._in_prepare_mode
        
        traj_len = 1000
        last_step_time = time.time()
        logger.warning("prepare_init")
        if in_prepare_mode:
            logger.info("Robot in sport mode - letting sport mode handle robot during prepare")
        pbar = ProgressBar("Prepare", traj_len)

        for t in range(traj_len):
            current_motor_angle = np.array(self.env.dof_pos)
            
            # Standard blend (300 steps = 0.6s)
            blend_ratio = np.minimum(t / 300, 1)
            action = (1 - blend_ratio) * current_motor_angle + blend_ratio * desired_motor_angle

            # warm up network
            self.step(dry_run=True)

            # Only send commands if not in prepare mode (sport mode will handle it)
            if not in_prepare_mode:
                self.env.step(action)
            else:
                # Just update state, let sport mode control the robot
                self.env.update()

            time_diff = last_step_time + self.dt - time.time()
            if time_diff > 0:
                time.sleep(time_diff)
            else:
                logger.error("Warning: frame drop")
            last_step_time = time.time()
            pbar.update()

            if t == 0.9 * traj_len:
                logger.info(f"{'=' * 10} RESET ZERO POSITION {'=' * 10}")
                self.reset()

        time.sleep(0.01)
        pbar.close()
        logger.warning("prepare_done")


if __name__ == "__main__":
    pass
