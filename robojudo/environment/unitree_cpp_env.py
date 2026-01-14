import logging
import time

import numpy as np
from unitree_cpp import RobotState, SportState, UnitreeController  # type: ignore

from robojudo.environment import Environment, env_registry
from robojudo.environment.env_cfgs import UnitreeEnvCfg
from robojudo.tools.retarget import HandRetarget
from robojudo.utils.rotation import TransformAlignment
from robojudo.utils.util_func import quat_rotate_inverse_np
from robojudo.tools.shm_odometry import ShmOdometry

logger = logging.getLogger(__name__)


@env_registry.register
class UnitreeCppEnv(Environment):
    cfg_env: UnitreeEnvCfg

    def __init__(self, cfg_env: UnitreeEnvCfg, device="cpu"):
        self.enabled: bool = cfg_env.act
        super().__init__(cfg_env=cfg_env, device=device)
        self.RemoteControllerHandler = None

        cfg_unitree: UnitreeEnvCfg.UnitreeCfg = cfg_env.unitree

        cfg_unitree_dict: dict = cfg_unitree.to_dict()
        cfg_unitree_dict["num_dofs"] = self.num_dofs
        cfg_unitree_dict["stiffness"] = self.stiffness
        cfg_unitree_dict["damping"] = self.damping

        # Debug: Log delay_mode_release value and ensure it's set
        delay_mode_release = cfg_unitree.delay_mode_release
        logger.info(f"UnitreeCppEnv: delay_mode_release from config = {delay_mode_release}")
        
        # ALWAYS set delay_mode_release in the dict to ensure it's passed to C++
        cfg_unitree_dict["delay_mode_release"] = delay_mode_release
        logger.info(f"UnitreeCppEnv: delay_mode_release set in dict = {cfg_unitree_dict['delay_mode_release']}")
        
        # Verify it's actually in the dict
        if "delay_mode_release" not in cfg_unitree_dict:
            logger.error("CRITICAL: delay_mode_release not in cfg_unitree_dict after setting!")
        else:
            logger.info(f"UnitreeCppEnv: Verified delay_mode_release in dict = {cfg_unitree_dict['delay_mode_release']}")

        self.robot = cfg_unitree.robot
        self._dof_idx = cfg_env.joint2motor_idx
        self._odometry_type = cfg_env.odometry_type
        if self._odometry_type == "ZED":
            assert self.cfg_env.zed_cfg is not None, "zed_cfg must be set if odometry_type is 'ZED'"
            from robojudo.tools.zed_odometry import ZedOdometry

            self.zed_odometry = ZedOdometry(self.cfg_env.zed_cfg)
        elif self._odometry_type == "DUMMY":
            pass
        elif self._odometry_type == "UNITREE":
            pass
        elif self._odometry_type == "SHM":
            self.shm_odometry = ShmOdometry()

        self.hand_type = cfg_unitree.hand_type
        if self.hand_type == "Inspire":
            self.hand_retarget = HandRetarget(cfg_env.hand_retarget)
        elif self.hand_type == "Dex-3":
            self.hand_retarget = None  # TODO
        else:
            self.hand_retarget = None

        self.sport_state: SportState = None  # pyright: ignore[reportAttributeAccessIssue]
        self.robot_state: RobotState = None  # pyright: ignore[reportAttributeAccessIssue]

        self.unitree = UnitreeController(cfg_unitree_dict)
        
        # Track if we're in prepare mode (sport mode active, don't send low-level commands)
        self._in_prepare_mode = cfg_unitree.delay_mode_release

        # born place alignment extra for h1 torso
        if self.robot == "h1":
            self.torso_align = TransformAlignment()

        # time.sleep(1)  # wait for unitree init
        self.self_check()

    def self_check(self):
        for _ in range(30):
            time.sleep(0.1)
            if self.unitree.self_check():
                logger.info("UnitreeCppEnv self check passed!")
                break
        if not self.unitree.self_check():
            logger.critical("UnitreeCppEnv self check failed!")
            exit()

    def reset(self):
        if self.born_place_align:  # TODO: merge
            self.born_place_align = False  # disable during reset
            self.update()
            self.born_place_align = True  # enable after reset
            self.set_born_place()
            self.update()

    def set_born_place(self, quat: np.ndarray | None = None, pos: np.ndarray | None = None):
        quat_ = self.base_quat if quat is None else quat
        pos_ = self.base_pos if pos is None else pos
        super().set_born_place(quat_, pos_)

        if self.robot == "h1":
            self.torso_align.set_base(quat=self.torso_quat)

        if self._odometry_type == "ZED":
            self.zed_odometry.set_zreo()

    def update(self):
        # robot state
        self.robot_state = self.unitree.get_robot_state()
        if self._dof_idx is None:
            self._dof_pos = np.array(self.robot_state.motor_state.q, dtype=np.float32)
            self._dof_vel = np.array(self.robot_state.motor_state.dq, dtype=np.float32)
        else:
            self._dof_pos = np.array(
                [self.robot_state.motor_state.q[self._dof_idx[i]] for i in range(len(self._dof_idx))],
                dtype=np.float32,
            )
            self._dof_vel = np.array(
                [self.robot_state.motor_state.dq[self._dof_idx[i]] for i in range(len(self._dof_idx))],
                dtype=np.float32,
            )

        if self.robot == "g1":
            quat = np.array(self.robot_state.imu_state.quaternion, dtype=np.float32)[[1, 2, 3, 0]]
            ang_vel = np.array(self.robot_state.imu_state.gyroscope, dtype=np.float32)
            rpy = np.array(self.robot_state.imu_state.rpy, dtype=np.float32)

            if self.born_place_align:
                quat = self.base_align.align_quat(quat)

            self._base_quat = quat
            self._base_ang_vel = ang_vel
            self._base_rpy = rpy

        elif self.robot == "h1":
            raise NotImplementedError("H1 robot with unitree_cpp not supported yet.")

        # odometry
        if self._odometry_type == "ZED":
            self.zed_odometry.update()
            if self.zed_odometry.is_valid:
                # born place aligned in zed_odometry
                self._base_pos = self.zed_odometry.pos
                self._lin_vel = self.zed_odometry.lin_vel
        elif self._odometry_type == "DUMMY":
            self._base_pos = np.array([0.0, 0.0, 0.8])
            self._base_lin_vel = np.array([0.0, 0.0, 0.0])
        elif self._odometry_type == "UNITREE":
            self.sport_state = self.unitree.get_sport_state()
            base_pos = np.asarray(self.sport_state.position, dtype=np.float32)
            lin_vel = np.asarray(self.sport_state.velocity, dtype=np.float32)
            self._base_lin_vel = quat_rotate_inverse_np(self.base_quat, lin_vel)
            if self.born_place_align:
                self._base_pos = self.base_align.align_pos(base_pos)
        elif self._odometry_type == "SHM":
            shm_data = self.shm_odometry.get_data()
            if shm_data:
                # Use filtered estimates from the new state estimator
                self._base_pos = shm_data["pos"]
                self._base_lin_vel = shm_data["vel_body"] # Policy expects BODY frame
                
                # Optionally override IMU data with filtered data if needed
                # (New state estimator has cleaner Orientation)
                self._base_quat = shm_data["quat"]
                self._base_ang_vel = shm_data["omega"]
                
                if self.born_place_align:
                    self._base_pos = self.base_align.align_pos(self._base_pos)


        # FK
        if self.update_with_fk:
            fk_info = self.fk()
            self._torso_pos = fk_info[self._torso_name]["pos"]
            if self.robot != "h1":
                self._torso_quat = fk_info[self._torso_name]["quat"]
                self._torso_ang_vel = fk_info[self._torso_name]["ang_vel"]

        # controller
        if self.RemoteControllerHandler:
            self.RemoteControllerHandler(self.robot_state.wireless_remote)

    def step(self, pd_target, hand_pose=None):
        assert len(pd_target) == self.num_dofs, "pd_target len should be num_dofs of env"

        # CRITICAL: Do NOT send commands if in prepare mode (sport mode is active)
        # Sport mode will handle robot control during prepare
        if self._in_prepare_mode:
            # Just update state, don't send commands
            logger.debug("In prepare mode - skipping command send (sport mode controls robot)")
            return

        # limits = self.position_limits
        # pd_target_clipped = np.clip(pd_target, limits[:, 0], limits[:, 1])

        # delta = pd_target - pd_target_clipped
        # if np.any(delta != 0):
        #     logger.warning(f"JOINT out of LIMIT-> {delta}")

        # positions = pd_target_clipped
        positions = pd_target
        
        # Debug: Log arm positions being sent (first few steps after mode release)
        if hasattr(self, '_step_count'):
            self._step_count += 1
        else:
            self._step_count = 0
        
        if self._step_count < 10:
            # Find arm joint indices
            arm_joint_names = [
                "left_shoulder_pitch_joint", "left_shoulder_roll_joint", 
                "left_shoulder_yaw_joint", "left_elbow_joint",
                "right_shoulder_pitch_joint", "right_shoulder_roll_joint", 
                "right_shoulder_yaw_joint", "right_elbow_joint"
            ]
            arm_indices = [self.joint_names.index(name) for name in arm_joint_names if name in self.joint_names]
            if arm_indices:
                arm_positions = [positions[i] for i in arm_indices]
                logger.info(f"UnitreeCppEnv.step: sending arm positions {arm_positions} to joints {arm_indices}")
        
        if self.enabled:
            self.unitree.step(positions.tolist())

        if hand_pose is not None:
            assert type(hand_pose) is np.ndarray, "hand_pose should be a numpy array"
            assert hand_pose.shape[0] == 2, "hand_pose should be of shape (2, -1)"
            if self.hand_retarget is not None:
                hand_pose = self.hand_retarget.from_pose_to_cmd(hand_pose)
                logger.debug(f"Hand pose retargeted: {hand_pose}")
            hand_pose = hand_pose.tolist()

            if self.enabled:
                self.unitree.step_hands(hand_pose[0], hand_pose[1])

    def shutdown(self):
        """Shutdown: disable all controls and apply dampening only to prevent vibration"""
        logger.info("Shutting down: disabling controls and applying dampening...")
        
        # Immediately disable command sending to prevent any new commands
        self.enabled = False
        self._in_prepare_mode = True
        
        # Set motors to dampening mode only (no position/torque control)
        # Use the C++ controller's damping method if available
        if hasattr(self, "unitree") and hasattr(self.unitree, "set_gains"):
            try:
                # Set zero stiffness and damping gains to prevent vibration
                num_dofs = self.num_dofs if hasattr(self, "num_dofs") else 29
                stiffness = [0.0] * num_dofs
                damping = [8.0] * num_dofs  # Damping only, no stiffness
                self.unitree.set_gains(stiffness, damping)
                # Send zero position command with damping multiple times to ensure it's applied
                zero_positions = [0.0] * num_dofs
                for _ in range(3):
                    self.unitree.step(zero_positions)
                    time.sleep(0.05)  # Brief delay between commands
                logger.info("✓ Shutdown complete: motors in dampening mode only")
            except Exception as e:
                logger.warning(f"Failed to set damping via C++ controller: {e}")
        else:
            logger.warning("⚠ set_gains not available, motors may not be properly dampened")

    def set_gains(self, stiffness, damping):
        if not hasattr(self, "unitree"):  # TODO
            return
        if not self.enabled:
            return
        self.unitree.set_gains(stiffness, damping)

    def release_mode(self):
        """
        Release sport mode (call after prepare to switch from R2+A to R1+Y).
        The default_pos from DOF config should already be set via set_gains(),
        so arms should maintain their default positions when entering developer mode.
        """
        if hasattr(self, "unitree") and hasattr(self.unitree, "release_mode"):
            logger.info("Releasing sport mode - switching to developer mode...")
            self.unitree.release_mode()
            self._in_prepare_mode = False  # Now we can send low-level commands
            logger.info("✓ Sport mode released - robot now in low-level control mode")
            logger.info("Note: Arms should maintain default_pos from DOF config (set via set_gains)")

    def check_mode(self):
        """Check current mode status"""
        if hasattr(self, "unitree") and hasattr(self.unitree, "check_mode"):
            form, name = self.unitree.check_mode()
            logger.info(f"Current mode - form: {form}, name: {name if name else '(none - developer mode)'}")
            return form, name
        return None, None

    def select_sport_mode(self, mode_name="ai"):
        """Return to sport mode (switch from R1+Y to R2+A)
        
        For G1, common mode names are:
        - "ai" (most common for G1 sport mode)
        - "normal" 
        - "SportAI" (less common)
        """
        if hasattr(self, "unitree") and hasattr(self.unitree, "select_sport_mode"):
            # Check current mode first
            form, name = self.check_mode()
            logger.info(f"Switching from mode '{name}' to sport mode '{mode_name}'...")
            
            self.unitree.select_sport_mode(mode_name)
            self._in_prepare_mode = True  # Stop sending low-level commands
            
            # Verify the switch
            time.sleep(0.5)
            form_new, name_new = self.check_mode()
            if name_new:
                logger.info(f"✓ Switched to sport mode: {name_new} - robot now in sport mode")
            else:
                logger.warning(f"Mode switch called but current mode is empty - may need to try different mode name")

    def return_to_standing(self):
        """
        Full transition from developer mode to standing safely in sport mode (FSM 801).
        Calls the external return_to_sport_mode.py script as a subprocess.
        """
        import os
        import subprocess
        import sys
        
        logger.info("\n" + "=" * 60)
        logger.info("STAND-UP TRANSITION: Safely returning to Sport Mode Standing")
        logger.info("=" * 60)

        # 1. PHASE 1: SAFE SQUAT (Low-level control)
        # Gradually lower the robot before releasing control to minimize drop
        logger.info("Phase 1: Squatting robot before mode switch to minimize drop...")
        current_pos = np.array(self.dof_pos)
        target_squat_pos = self.default_pos.copy()
        
        # Manually set knees and hips to a crouched/squat position
        # For G1: Knee indices are approx [9, 10], hip pitches are [0, 1]
        # These indices depend on joint2motor_idx, but self.default_pos is a good target
        # Let's just use a modified default_pos for a deeper squat
        # (Assuming indices 0,1 are hip pitch and 9,10 are knee pitch based on typical robot configs)
        # But safer to just interpolate to a known stable 'default' first
        
        trajectory_steps = 50 # 1 second at 50Hz
        for t in range(trajectory_steps):
            alpha = (t + 1) / trajectory_steps
            interp_pos = (1 - alpha) * current_pos + alpha * target_squat_pos
            self.step(interp_pos)
            time.sleep(0.02)
        
        logger.info("✓ Squat complete. Proceeding to mode switch.")

        # 2. PHASE 2: MODE SWITCH (External script)
        # Disable current controller to avoid interference during DDS handover
        self.enabled = False
        self._in_prepare_mode = True
        
        # Get path to the standalone return script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.abspath(os.path.join(current_dir, "..", "..", "scripts", "return_to_sport_mode.py"))
        
        net_if = getattr(self.cfg_env.unitree, 'net_if', 'eth0')
        
        if not os.path.exists(script_path):
            logger.error(f"Return script not found at {script_path}")
            logger.warning("Falling back to manual mode selection (robot may drop)...")
            self.select_sport_mode("ai")
            return False

        try:
            # Call the script as a separate process
            # This is safer than using the Python SDK in-process alongside unitree_cpp
            logger.info(f"Launching external transition script...")
            cmd = [sys.executable, script_path, "--net-if", net_if]
            
            # Execute and wait for completion
            result = subprocess.run(cmd)
            
            if result.returncode == 0:
                logger.info("✓ Stand-up transition completed successfully")
                return True
            else:
                logger.error(f"✗ Transition script failed with exit code {result.returncode}")
        except Exception as e:
            logger.error(f"Failed to execute transition script: {e}")
        
        logger.warning("Robot may not be standing. Please STAND UP manually (R2+START).")
        return False


if __name__ == "__main__":
    from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg

    env = UnitreeCppEnv(cfg_env=G1RealEnvCfg())
    env.set_gains(
        stiffness=[kp * 0.0 for kp in env.stiffness],
        damping=[kd * 0.1 for kd in env.damping],
    )
    while 1:
        # env.step(np.zeros(29), np.ones((2, 7)) * -0)
        env.step(np.zeros(29), None)
        # if controller.remote_controller("A"):
        #     controller.shutdown()
        print(env.base_rpy)
        print(env.dof_pos)
        print(env.base_pos)
        env.update()
        # print(env.base_pos)
        time.sleep(0.1)
    # print("Exit")
    # from robojudo.controller import UnitreeCtrl
    # ctrl = UnitreeCtrl(env=env)

    # while True:
    #     env.update()
    #     state = ctrl.get_state()
    #     events = ctrl.get_events()
    #     print("State:", state)
    #     print("Events:", events)
    #     time.sleep(0.1)  # Simulate a control loop
