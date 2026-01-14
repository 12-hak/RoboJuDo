import logging
import time
from collections.abc import Callable
from enum import Enum, auto

import numpy as np

import robojudo.environment
from robojudo.controller import CtrlManager
from robojudo.environment import Environment
from robojudo.pipeline import Pipeline, pipeline_registry
from robojudo.pipeline.pipeline_cfgs import RlLocoMimicPipelineCfg
from robojudo.pipeline.rl_multi_policy_pipeline import PolicyManager, RlMultiPolicyPipeline
from robojudo.pipeline.rl_pipeline import PolicyWrapper
from robojudo.policy import PolicyCfg
from robojudo.utils.progress import ProgressBar

logger = logging.getLogger(__name__)


class PolicyInterpManager(PolicyManager):
    class InterpState(Enum):
        IDLE = auto()
        START = auto()
        IN_PROGRESS = auto()
        END = auto()

    DURATIONS_LOCO_MIMIC = [0, 75, 25]  # [start, in-progress, end] in steps
    DURATIONS_MIMIC_LOCO = [25, 75, 0]  # [start, in-progress, end] in steps

    def __init__(
        self,
        cfg_policy_loco: PolicyCfg,
        cfg_policies: list[PolicyCfg],
        env: Environment,
        loco_dof_pos: np.ndarray | None = None,
        device: str = "cpu",
        durations_loco_mimic: list[int] | None = None,
        durations_mimic_loco: list[int] | None = None,
    ):
        cfg_policies_all = [cfg_policy_loco] + cfg_policies
        super().__init__(cfg_policies_all, env, device)

        self.policy_loco_id = 0
        self.policy_mimic_num = len(cfg_policies)
        assert self.policy_mimic_num > 0, "At least one mimic policy is required for switching."
        self.policy_mimic_ids = list(range(1, self.policy_mimic_num + 1))
        self.policy_mimic_idx = 0

        # Interpolation durations (use provided or defaults)
        self.durations_loco_mimic = durations_loco_mimic if durations_loco_mimic is not None else self.DURATIONS_LOCO_MIMIC
        self.durations_mimic_loco = durations_mimic_loco if durations_mimic_loco is not None else self.DURATIONS_MIMIC_LOCO

        # Interpolation variables
        self.interp_state = self.InterpState.IDLE
        self.interp_timestep = 0
        self.interp_durations = [20, 40, 20]  # [start, in-progress, end] in steps
        self.interp_pbar = None
        self.interp_callback_start = None
        self.interp_callback_end = None

        self.loco_dof_pos = loco_dof_pos if loco_dof_pos is not None else self.env.default_pos.copy()
        self.override_dof_pos = self.loco_dof_pos.copy()

    def _interpolate_init(
        self,
        get_target_pos: Callable[[], np.ndarray],
        durations: list[int],
        callback_start=None,
        callback_end=None,
    ):
        self.interp_get_target_pos = get_target_pos
        self.interp_durations = durations
        self.interp_callback_start = callback_start
        self.interp_callback_end = callback_end
        self.interp_pbar = ProgressBar("Interpolation", durations[1])

        self.interp_state = self.InterpState.START
        # Starting Tasks
        self.timer.add(self._interpolate_start, delay_steps=durations[0])
        # Ending Tasks
        self.timer.add(self._interpolate_end, delay_steps=sum(durations) + 1)

    def _interpolate_start(self):
        if self.interp_state != self.InterpState.START:
            return
        if self.interp_callback_start is not None:
            self.interp_callback_start()
            self.interp_callback_start = None

        self.interp_start_pos = self.env.dof_pos.copy()
        self.interp_target_pos = self.interp_get_target_pos()
        self.interp_timestep = 0
        self.interp_state = self.InterpState.IN_PROGRESS

        # logger.debug("Interpolation started.")

    def _interpolate_end(self):
        if self.interp_state != self.InterpState.END:
            return
        self.override_dof_pos = self.interp_target_pos.copy()
        if self.interp_pbar:
            self.interp_pbar.close()
            self.interp_pbar = None
        if self.interp_callback_end is not None:
            self.interp_callback_end()
            self.interp_callback_end = None
        self.interp_state = self.InterpState.IDLE

        # logger.debug("Interpolation ended.")

    def _interpolate_step(self):
        if self.interp_state != self.InterpState.IN_PROGRESS:
            return

        if self.interp_pbar:
            self.interp_pbar.set(self.interp_timestep)

        progress = self.interp_timestep / self.interp_durations[1]
        alpha = min(progress, 1.0)
        self.override_dof_pos = (1 - alpha) * self.interp_start_pos + alpha * self.interp_target_pos

        if self.interp_timestep < self.interp_durations[1]:
            self.interp_timestep += 1
        else:
            self.interp_state = self.InterpState.END

    def toggle_mimic_policy(self, delta: int):
        # only switch mimic policy if current policy is locomotion
        if self.current_policy_id != self.policy_loco_id:
            logger.warning("Cannot switch mimic policy when policy is mimic.")
            return

        self.policy_mimic_idx = (self.policy_mimic_idx + delta) % self.policy_mimic_num
        policy_id = self.policy_mimic_ids[self.policy_mimic_idx]
        policy_name = self.policy_by_id(policy_id).name
        logger.info(f"Switch mimic policy to {self.policy_mimic_idx}: {policy_name}")

    def switch_to_loco(self):
        if self.current_policy_id == self.policy_loco_id and self.interp_state == self.InterpState.IDLE:
            logger.warning("Already in locomotion policy.")
            return
        if self.current_policy_id != self.policy_loco_id:
            self.policy_by_id(self.policy_loco_id).reset()
            self.warmup_policy_indices.add(self.policy_loco_id)
        self._interpolate_init(
            get_target_pos=lambda: self.loco_dof_pos,
            durations=self.durations_mimic_loco,
            callback_start=lambda: self.set_policy(self.policy_loco_id),
        )

    def switch_to_mimic(self):
        if self.current_policy_id != self.policy_loco_id:
            logger.warning("Already in mimic policy.")
            return
        policy_mimic_id = self.policy_mimic_ids[self.policy_mimic_idx]
        self.policy_by_id(policy_mimic_id).reset()
        self.warmup_policy_indices.add(policy_mimic_id)
        self._interpolate_init(
            get_target_pos=lambda: self.policy_by_id(policy_mimic_id).get_init_dof_pos(),
            durations=self.durations_loco_mimic,
            callback_end=lambda: self.set_policy(policy_mimic_id),
        )

    def step(self, env_data, ctrl_data):
        super().step(env_data, ctrl_data)
        self._interpolate_step()


@pipeline_registry.register
class RlLocoMimicPipeline(RlMultiPolicyPipeline):
    cfg: RlLocoMimicPipelineCfg

    @property
    def policy(self) -> PolicyWrapper:
        return self.policy_manager.policy

    def __init__(self, cfg: RlLocoMimicPipelineCfg):
        # Skip RlMultiPolicyPipeline initialization
        Pipeline.__init__(self, cfg=cfg)

        # Preload locomotion policy BEFORE initializing environment to avoid mode switching during policy load
        if not cfg.env.is_sim and hasattr(cfg.env, 'unitree') and cfg.env.unitree.delay_mode_release:
            logger.info("Preloading locomotion policy before environment initialization...")
            if not cfg.loco_policy.disable_autoload:
                loco_policy_file = cfg.loco_policy.policy_file
                loco_policy_type = cfg.loco_policy.policy_type
                logger.info(f"Preloading {loco_policy_type} from {loco_policy_file}...")
                try:
                    # Handle different policy file formats
                    if loco_policy_file.endswith('.onnx'):
                        import onnxruntime as ort
                        sess_options = ort.SessionOptions()
                        providers = ["CPUExecutionProvider"]
                        _ = ort.InferenceSession(loco_policy_file, sess_options, providers=providers)
                        logger.info("✓ Locomotion policy (ONNX) preloaded successfully")
                    else:
                        # Assume TorchScript (.pt file)
                        import torch
                        _ = torch.jit.load(loco_policy_file, map_location=self.device)
                        logger.info("✓ Locomotion policy (TorchScript) preloaded successfully")
                except Exception as e:
                    logger.warning(f"Failed to preload locomotion policy: {e}")

        env_class: type[Environment] = getattr(robojudo.environment, self.cfg.env.env_type)
        self.env: Environment = env_class(cfg_env=self.cfg.env, device=self.device)

        self.ctrl_manager = CtrlManager(cfg_ctrls=self.cfg.ctrl, env=self.env, device=self.device)

        # upper body override
        self.num_upper_body_dof = self.cfg.upper_dof_num
        if upper_dof_pos_default := self.cfg.upper_dof_pos_default:
            loco_dof_pos = self.env.default_pos.copy()
            loco_dof_pos[-self.num_upper_body_dof :] = upper_dof_pos_default
            self.loco_dof_pos = loco_dof_pos
        else:
            self.loco_dof_pos = self.env.default_pos
        if override_dof_indices := self.cfg.upper_dof_override_indices:
            self.override_dof_indices = override_dof_indices
        else:
            self.override_dof_indices = list(range(-self.num_upper_body_dof, 0))

        self.policy_manager = PolicyInterpManager(
            cfg_policy_loco=self.cfg.loco_policy,
            cfg_policies=self.cfg.mimic_policies,
            env=self.env,
            loco_dof_pos=self.loco_dof_pos,
            device=self.device,
            durations_loco_mimic=self.cfg.durations_loco_mimic,
            durations_mimic_loco=self.cfg.durations_mimic_loco,
        )
        self.env.update_dof_cfg(override_cfg=self.policy.cfg_action_dof)
        self.visualizer = self.env.visualizer

        self.freq = self.cfg.loco_policy.freq
        self.dt = 1.0 / self.freq

        self.policy_locomotion_mimic_flag = 0  # 0: locomotion, 1: mimic
        
        # Track if we should release mode after prepare (don't release in __init__)
        self._should_release_mode_after_prepare = False
        if not cfg.env.is_sim and hasattr(self.env, "release_mode") and hasattr(self.env, "_in_prepare_mode"):
            if self.env._in_prepare_mode:
                self._should_release_mode_after_prepare = True
                logger.info("Will release sport mode AFTER prepare() completes (locomotion policy must be fully loaded)")

        self.self_check()
        self.reset()

    def post_step_callback(self, env_data, ctrl_data, extras, pd_target):
        self.timestep += 1

        commands = ctrl_data.get("COMMANDS", [])

        # Handle policy CALLBACK
        for callback in extras.get("CALLBACK", []):
            match callback:
                case "[MOTION_DONE]":
                    if self.policy_locomotion_mimic_flag == 1:
                        commands.append("[POLICY_LOCO]")
                        logger.info("Mimic motion done, switch to locomotion policy.")

        for command in commands:
            match command:
                case "[SHUTDOWN]":
                    logger.warning("Emergency shutdown!")
                    self.env.shutdown()
                case "[SIM_REBORN]":
                    if hasattr(self.env, "reborn"):
                        logger.warning("Simulation Env reborn!")
                        self.env.reborn()  # pyright: ignore[reportAttributeAccessIssue]
                case cmd if cmd.startswith("[POLICY_SWITCH]"):
                    switch_target = cmd.split(",")[1]
                    if switch_target == "NEXT":
                        self.policy_manager.toggle_mimic_policy(1)
                    elif switch_target == "LAST":
                        self.policy_manager.toggle_mimic_policy(-1)
                case "[POLICY_LOCO]":
                    self.policy_locomotion_mimic_flag = 0
                    self.policy_manager.switch_to_loco()
                case "[POLICY_MIMIC]":
                    self.policy_locomotion_mimic_flag = 1
                    self.policy_manager.switch_to_mimic()
                case "[RETURN_TO_SPORT]":
                    if hasattr(self.env, "select_sport_mode"):
                        logger.warning("Returning to sport mode!")
                        self.env.select_sport_mode()

        self.ctrl_manager.post_step_callback(ctrl_data)

        self.policy.post_step_callback(commands)
        if self.visualizer is not None:
            self.policy.debug_viz(self.visualizer, env_data, ctrl_data, extras)

        # # Handle policy switch after step to avoid mid-step change
        self.policy_manager.step(env_data, ctrl_data)

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

        if self.policy_manager.current_policy_id == self.policy_manager.policy_loco_id:
            ctrl_data["ref_dof_pos"] = self.policy.obs_adapter.fit(self.policy_manager.override_dof_pos)

        obs, extras = self.policy.get_observation(env_data, ctrl_data)

        pd_target = self.policy.get_pd_target(obs)

        if self.policy_manager.current_policy_id == self.policy_manager.policy_loco_id:
            pd_target[self.override_dof_indices] = self.policy_manager.override_dof_pos[self.override_dof_indices]

        if not dry_run:
            self.env.step(pd_target, extras.get("hand_pose", None))
            # logger.debug(pd_target)

        self.post_step_callback(env_data, ctrl_data, extras, pd_target)

    def prepare(self):
        """
        Override prepare() to release mode AFTER prepare completes and locomotion policy is fully ready.
        """
        init_motor_angle = self.loco_dof_pos.copy()
        super().prepare(init_motor_angle=init_motor_angle)
        
        # Now release sport mode AFTER prepare is complete (locomotion policy is fully loaded)
        if self._should_release_mode_after_prepare:
            transition_start_time = time.time()
            logger.info("=" * 60)
            logger.info("Prepare complete - locomotion policy fully loaded")
            logger.info("Fast transition: Sport mode -> Developer mode with blending...")
            logger.info("=" * 60)
            
            # CRITICAL: Prepare first locomotion command BEFORE releasing mode
            # Transition is stable enough that we don't need to send commands in sport mode
            logger.info("[DEBUG] Preparing first locomotion command before mode release...")
            self.env.update()
            env_data = self.env.get_data()
            ctrl_data = {}
            obs, extras = self.policy.get_observation(env_data, ctrl_data)
            action = self.policy.get_action(obs)
            first_loco_target = self.policy.get_pd_target(obs) if hasattr(self.policy.policy, 'get_pd_target') else action + self.env.default_pos
            logger.info(f"[DEBUG] ✓ First locomotion command prepared: {len(first_loco_target)} DOFs")
            
            # NOW release mode - transition is stable, no need for pre-release commands
            t_release_start = time.time()
            logger.info("[DEBUG] Releasing sport mode - switching to developer mode...")
            self.env.release_mode()
            t_release_end = time.time()
            logger.info(f"[DEBUG] env.release_mode() took {(t_release_end-t_release_start)*1000:.2f}ms")
            logger.info("✓ Sport mode released - locomotion policy now has full control")
            
            # IMMEDIATE COMMAND: Send first command with ZERO delay
            t_first_step = time.time()
            logger.info("[DEBUG] ⚡ SENDING IMMEDIATE FULL LOCOMOTION COMMAND (100% locomotion, zero delay)...")
            self.env.step(first_loco_target)  # Send INSTANTLY at 100% locomotion
            t_first_step_end = time.time()
            logger.info(f"[DEBUG] env.step() (first command) took {(t_first_step_end-t_first_step)*1000:.2f}ms")
            
            # Send a couple more commands to establish control loop
            logger.info("[DEBUG] Sending 2 more commands to establish control loop...")
            for i in range(2):
                frame_start = time.time()
                self.env.update()
                env_data = self.env.get_data()
                ctrl_data = {}
                obs, extras = self.policy.get_observation(env_data, ctrl_data)
                action = self.policy.get_action(obs)
                loco_target = self.policy.get_pd_target(obs) if hasattr(self.policy.policy, 'get_pd_target') else action + self.env.default_pos
                self.env.step(loco_target)
                frame_time = (time.time() - frame_start) * 1000
                logger.info(f"[DEBUG] Post-release frame {i+1}: {frame_time:.2f}ms")
                time.sleep(0.01)  # ~100Hz
            
            transition_end_time = time.time()
            total_transition_time = (transition_end_time - transition_start_time) * 1000
            logger.info(f"[DEBUG] =========================================")
            logger.info(f"[DEBUG] TOTAL TRANSITION TIME: {total_transition_time:.2f}ms")
            logger.info(f"[DEBUG] =========================================")
            
            logger.info("✓ Fast blended transition complete - robot should maintain balance")
            logger.info("=" * 60)


if __name__ == "__main__":
    pass
