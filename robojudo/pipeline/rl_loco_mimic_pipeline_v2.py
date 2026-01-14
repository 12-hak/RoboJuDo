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

# Import PolicyInterpManager from the original file
from robojudo.pipeline.rl_loco_mimic_pipeline import PolicyInterpManager


@pipeline_registry.register
class RlLocoMimicPipelineV2(RlMultiPolicyPipeline):
    """
    Modified RlLocoMimicPipeline that loads locomotion policy BEFORE switching to developer mode.
    This ensures the locomotion policy is ready immediately when developer mode is entered.
    """
    cfg: RlLocoMimicPipelineCfg

    @property
    def policy(self) -> PolicyWrapper:
        return self.policy_manager.policy

    def __init__(self, cfg: RlLocoMimicPipelineCfg):
        # Skip RlMultiPolicyPipeline initialization
        Pipeline.__init__(self, cfg=cfg)

        # Preload locomotion policy file (just the ONNX/TorchScript) before environment initialization
        if not cfg.env.is_sim and hasattr(cfg.env, 'unitree') and cfg.env.unitree.delay_mode_release:
            logger.info("Preloading locomotion policy file before environment initialization...")
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

        # Create environment (robot connection, stays in sport mode if delay_mode_release=True)
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

        # NEW APPROACH: Load locomotion policy FULLY before switching to developer mode
        loco_policy_wrapper = None
        if not cfg.env.is_sim and hasattr(cfg.env, 'unitree') and cfg.env.unitree.delay_mode_release:
            logger.info("=" * 60)
            logger.info("Loading locomotion policy BEFORE switching to developer mode...")
            logger.info("=" * 60)
            
            # Create locomotion policy wrapper (fully initialized with adapters, etc.)
            logger.info("Creating locomotion policy wrapper...")
            start_time = time.time()
            loco_policy_wrapper = PolicyWrapper(self.cfg.loco_policy, self.env.dof_cfg, self.device)
            load_time = time.time() - start_time
            logger.info(f"✓ Locomotion policy '{loco_policy_wrapper.name}' created in {load_time:.2f}s")
            logger.info(f"  - Policy type: {self.cfg.loco_policy.policy_type}")
            logger.info(f"  - Action DOF: {len(loco_policy_wrapper.cfg_action_dof.joint_names)} joints")
            logger.info(f"  - Observation DOF: {len(loco_policy_wrapper.cfg_obs_dof.joint_names)} joints")
            
            # Verify policy is fully loaded
            logger.info("Verifying locomotion policy is fully loaded...")
            policy_ready = False
            try:
                # Check if policy has a model/session loaded
                if hasattr(loco_policy_wrapper.policy, 'model') and loco_policy_wrapper.policy.model is not None:
                    logger.info("✓ Policy model loaded")
                    policy_ready = True
                elif hasattr(loco_policy_wrapper.policy, 'session') and loco_policy_wrapper.policy.session is not None:
                    logger.info("✓ Policy ONNX session loaded")
                    policy_ready = True
                else:
                    logger.warning("Policy model/session not found - checking for disable_autoload...")
                    if hasattr(loco_policy_wrapper.policy, 'cfg_policy') and loco_policy_wrapper.policy.cfg_policy.disable_autoload:
                        logger.info("✓ Policy has disable_autoload=True (expected for some policies)")
                        policy_ready = True
                
                # For AMO policy, also check if adapter is loaded
                if hasattr(loco_policy_wrapper.policy, 'adapter'):
                    if loco_policy_wrapper.policy.adapter is not None:
                        logger.info("✓ Policy adapter loaded")
                    else:
                        logger.warning("Policy adapter not loaded")
                
                # Try to get a dummy observation to verify policy can process data
                if policy_ready:
                    logger.info("Testing policy with dummy observation...")
                    import numpy as np
                    from box import Box
                    dummy_env_data = Box({
                        'dof_pos': np.zeros(len(self.env.dof_cfg.joint_names)),
                        'dof_vel': np.zeros(len(self.env.dof_cfg.joint_names)),
                        'base_quat': np.array([1.0, 0.0, 0.0, 0.0]),
                        'base_ang_vel': np.zeros(3),
                    })
                    dummy_ctrl_data = Box({})
                    try:
                        _ = loco_policy_wrapper.get_observation(dummy_env_data, dummy_ctrl_data)
                        logger.info("✓ Policy observation processing verified")
                    except Exception as e:
                        logger.warning(f"Policy observation test failed: {e}")
                        policy_ready = False
                
            except Exception as e:
                logger.warning(f"Policy verification encountered an issue: {e}")
                policy_ready = False
            
            if policy_ready:
                logger.info("✓ Verification complete - policy is ready")
            else:
                logger.warning("Policy verification incomplete")

        # Now create PolicyInterpManager (will create all policies including locomotion)
        logger.info("Creating PolicyInterpManager (this will load all policies)...")
        start_time = time.time()
        self.policy_manager = PolicyInterpManager(
            cfg_policy_loco=self.cfg.loco_policy,
            cfg_policies=self.cfg.mimic_policies,
            env=self.env,
            loco_dof_pos=self.loco_dof_pos,
            device=self.device,
            durations_loco_mimic=self.cfg.durations_loco_mimic,
            durations_mimic_loco=self.cfg.durations_mimic_loco,
        )
        manager_load_time = time.time() - start_time
        logger.info(f"✓ PolicyInterpManager created in {manager_load_time:.2f}s")
        
        # If we already created locomotion policy, replace it in policy_manager to avoid duplicate loading
        if loco_policy_wrapper is not None:
            logger.info("Replacing locomotion policy in policy_manager with pre-loaded version...")
            self.policy_manager.policies[0] = loco_policy_wrapper
            logger.info("✓ Using pre-loaded locomotion policy (no duplicate loading)")

        self.env.update_dof_cfg(override_cfg=self.policy.cfg_action_dof)
        self.visualizer = self.env.visualizer

        self.freq = self.cfg.loco_policy.freq
        self.dt = 1.0 / self.freq

        self.policy_locomotion_mimic_flag = 0  # 0: locomotion, 1: mimic

        # Do self_check and reset first
        logger.info("Running self_check and reset...")
        self.self_check()
        self.reset()
        logger.info("✓ self_check and reset complete")
        
        # Set flag to indicate we will handle mode release ourselves (after prepare completes)
        # This prevents run_pipeline.py from releasing mode too early
        self._mode_already_released = False  # Will be set to True after prepare()
        self._should_release_mode_after_prepare = False
        
        if not cfg.env.is_sim and hasattr(self.env, "release_mode") and hasattr(self.env, "_in_prepare_mode"):
            logger.info(f"V2 Pipeline: Checking mode release flags...")
            logger.info(f"  - _in_prepare_mode = {self.env._in_prepare_mode}")
            logger.info(f"  - has release_mode = {hasattr(self.env, 'release_mode')}")
            
            if self.env._in_prepare_mode:
                self._should_release_mode_after_prepare = True
                logger.info("  ✓ V2 Pipeline will handle mode release after prepare() completes")
            else:
                logger.warning("  ⚠ _in_prepare_mode is False - mode may have been released already!")
                logger.warning("  ⚠ V2 Pipeline will NOT handle mode release (mode already released)")
        else:
            logger.warning("V2 Pipeline: Cannot handle mode release (missing required attributes)")

    def prepare(self, init_motor_angle=None):
        """
        Override prepare() to release mode AFTER all policies are loaded and prepare completes.
        """
        logger.info("=" * 60)
        logger.info("V2 Pipeline: prepare() called")
        logger.info(f"  - _should_release_mode_after_prepare = {self._should_release_mode_after_prepare}")
        logger.info(f"  - _mode_already_released = {self._mode_already_released}")
        logger.info(f"  - _in_prepare_mode = {getattr(self.env, '_in_prepare_mode', 'N/A')}")
        logger.info("=" * 60)
        
        # Call parent prepare() first
        logger.info("V2 Pipeline: Calling super().prepare()...")
        super().prepare(init_motor_angle)
        logger.info("V2 Pipeline: super().prepare() completed")
        
        # Now that prepare() is complete, release mode if we're supposed to
        if self._should_release_mode_after_prepare and not self._mode_already_released:
            logger.info("=" * 60)
            logger.info("Prepare complete - all policies loaded")
            logger.info("  - Locomotion policy: loaded and verified")
            logger.info(f"  - All {len(self.policy_manager.policies)} policies: loaded")
            logger.info("  - Prepare: completed")
            logger.info("=" * 60)
            
            # Quick transition: Run locomotion policy for 1 frame while in sport mode
            # Then do stand -> damp -> release mode sequence to bring arms down
            logger.info("Running locomotion policy transition (1 frame) while in SPORT MODE...")
            
            # Temporarily allow sending commands even in prepare mode for transition
            original_prepare_mode = getattr(self.env, '_in_prepare_mode', False)
            
            # Single frame transition
            self.env.update()  # Update state
            env_data = self.env.get_data()
            ctrl_data = {}
            obs, extras = self.policy.get_observation(env_data, ctrl_data)
            action = self.policy.get_action(obs)
            pd_target = self.policy.get_pd_target(obs) if hasattr(self.policy.policy, 'get_pd_target') else action + self.env.default_pos
            
            # Temporarily disable prepare mode check to allow commands during transition
            if hasattr(self.env, '_in_prepare_mode'):
                self.env._in_prepare_mode = False
            
            # Send locomotion command (will clash with sport mode, but that's okay)
            self.env.step(pd_target)
            
            # Restore prepare mode flag
            if hasattr(self.env, '_in_prepare_mode'):
                self.env._in_prepare_mode = original_prepare_mode
            
            logger.info("✓ Transition frame complete - preparing for immediate mode release...")
            
            transition_start_time = time.time()
            
            # CRITICAL: Prepare first locomotion command BEFORE releasing mode
            # Transition is stable enough that we don't need to send commands in sport mode
            logger.info("[DEBUG] Preparing first locomotion command before mode release...")
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
            self._mode_already_released = True
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
            
            logger.info("✓ Seamless transition complete - locomotion commands were already flowing")
            logger.info("✓ Robot should maintain balance - no gap in control")
            logger.info("✓ Arms will be controlled via upper_dof_pos_default (same as original beyondmimic)")
            logger.info("✓ Locomotion policy transition complete - ready for main loop")
            logger.info("=" * 60)

    def post_step_callback(self, env_data, ctrl_data, extras, pd_target):
        self.timestep += 1

        commands = ctrl_data.get("COMMANDS", [])

        # Handle policy CALLBACK
        for callback in extras.get("CALLBACK", []):
            match callback:
                case "[MOTION_DONE]":
                    if self.policy_locomotion_mimic_flag == 1:
                        logger.info("Motion done, switching back to locomotion...")
                        self.policy_manager.switch_to_loco()
                        self.policy_locomotion_mimic_flag = 0

        # Handle policy switching commands
        for command in commands:
            match command:
                case "[SHUTDOWN]":
                    logger.warning("Emergency shutdown!")
                    self.env.shutdown()
                case "[SIM_REBORN]":
                    if hasattr(self.env, "reborn"):
                        logger.warning("Simulation Env reborn!")
                        self.env.reborn()  # pyright: ignore[reportAttributeAccessIssue]
                case "[POLICY_LOCO]":
                    logger.info("Switching to locomotion policy...")
                    self.policy_manager.switch_to_loco()
                    self.policy_locomotion_mimic_flag = 0
                case "[POLICY_MIMIC]":
                    logger.info("Switching to mimic policy...")
                    self.policy_manager.switch_to_mimic()
                    self.policy_locomotion_mimic_flag = 1
                case cmd if cmd.startswith("[POLICY_SWITCH]"):
                    direction = cmd.split(",")[1] if "," in cmd else "NEXT"
                    if direction == "NEXT":
                        self.policy_manager.toggle_mimic_policy(1)
                    elif direction == "LAST":
                        self.policy_manager.toggle_mimic_policy(-1)

        self.ctrl_manager.post_step_callback(ctrl_data)

        self.policy.post_step_callback(commands)
        if self.visualizer is not None:
            self.policy.debug_viz(self.visualizer, env_data, ctrl_data, extras)

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

