# Fix OMP perfmance issue on ARM platform (Jetson)
import os
import platform

if platform.machine().startswith("aarch64"):
    os.environ["OMP_NUM_THREADS"] = "1"

import argparse
import logging
import signal
import sys
import time

import numpy as np
import robojudo.pipeline
from robojudo.config.config_manager import ConfigManager
from robojudo.pipeline.pipeline_cfgs import RlPipelineCfg
from robojudo.pipeline.rl_pipeline import RlPipeline

logger = logging.getLogger("robojudo")


def ensure_robot_standing_in_sport_mode(net_if="eth0", timeout=15.0):
    """
    NOTE: This function is deprecated - if delay_mode_release=True, robot is already in sport mode.
    Sport mode will maintain balance automatically, so we don't need to check/ensure standing.
    """
    logger.info("Skipping robot standing check - sport mode (delay_mode_release=True) handles balance automatically")
    return True


def wait_for_stable_stand(env, timeout=10.0, check_interval=0.1):
    """Wait for robot to be in stable stand position before releasing sport mode"""
    logger.info("Waiting for robot to reach stable stand position...")
    start_time = time.time()
    stable_count = 0
    required_stable_count = 20  # Need 2 seconds of stability (20 * 0.1s)
    
    while time.time() - start_time < timeout:
        env.update()
        
        # Check if robot is standing (base height > threshold, low velocity)
        base_height = env.base_pos[2]  # Z position
        base_vel = np.linalg.norm(env.base_lin_vel)
        base_ang_vel = np.linalg.norm(env.base_ang_vel)
        
        # Criteria for stable stand:
        # - Base height reasonable (standing, not fallen)
        # - Low base velocity (not moving much)
        # - Low angular velocity (not rotating)
        is_stable = (
            base_height > 0.3 and base_height < 1.2 and  # Reasonable height
            base_vel < 0.1 and  # Low linear velocity
            base_ang_vel < 0.2  # Low angular velocity
        )
        
        if is_stable:
            stable_count += 1
            if stable_count >= required_stable_count:
                logger.info(f"Robot is in stable stand (height: {base_height:.3f}m, vel: {base_vel:.3f}m/s)")
                return True
        else:
            stable_count = 0  # Reset if not stable
        
        time.sleep(check_interval)
    
    logger.warning("Timeout waiting for stable stand, releasing mode anyway...")
    return False




def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="g1",
        help="Name of the config class to use",
    )
    args = parser.parse_args()
    return args


def preload_locomotion_policy(cfg: RlPipelineCfg):
    """
    Preload locomotion policy immediately at script start for faster initialization.
    This loads the policy before pipeline creation so it's ready when prepare() is called.
    """
    # Only preload for RlLocoMimicPipelineCfg with real robot
    if not hasattr(cfg, 'loco_policy'):
        return
    
    if cfg.env.is_sim:
        return
    
    if hasattr(cfg.loco_policy, 'disable_autoload') and cfg.loco_policy.disable_autoload:
        return
    
    loco_policy_file = cfg.loco_policy.policy_file
    loco_policy_type = cfg.loco_policy.policy_type
    device = "cpu"  # Default device
    
    logger.info("=" * 60)
    logger.info("PRELOADING LOCOMOTION POLICY AT SCRIPT START")
    logger.info(f"Policy: {loco_policy_type}")
    logger.info(f"File: {loco_policy_file}")
    logger.info("=" * 60)
    
    try:
        if loco_policy_file.endswith('.onnx'):
            import onnxruntime as ort
            sess_options = ort.SessionOptions()
            
            # OPTIMIZATION: Enable graph optimizations for faster loading and inference
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # OPTIMIZATION: Enable memory optimizations for faster startup
            sess_options.enable_mem_pattern = True
            sess_options.enable_cpu_mem_arena = True
            
            # OPTIMIZATION: Use fewer threads for faster initialization
            sess_options.intra_op_num_threads = 2
            sess_options.inter_op_num_threads = 2
            
            providers = ["CPUExecutionProvider"]
            preloaded_session = ort.InferenceSession(loco_policy_file, sess_options, providers=providers)
            logger.info("✓ Locomotion policy (ONNX) preloaded with optimizations")
        else:
            # Assume TorchScript (.pt file)
            import torch
            model = torch.jit.load(loco_policy_file, map_location=device)
            model.eval()
            preloaded_session = model
            logger.info("✓ Locomotion policy (TorchScript) preloaded with optimizations")
        
        # Attach preloaded session to config so pipeline can use it
        cfg.loco_policy._preloaded_session = preloaded_session
        logger.info("✓ Policy ready - will be used when pipeline initializes")
        logger.info("=" * 60)
    except Exception as e:
        logger.warning(f"Failed to preload locomotion policy: {e}")
        logger.warning("Pipeline will load policy normally (slower)")


def main():
    args = parse_args()
    logger.info(f"Using config: {args.config}")
    config_manager = ConfigManager(config_name=args.config)

    cfg: RlPipelineCfg = config_manager.get_cfg()

    # PRELOAD locomotion policy IMMEDIATELY at script start (before pipeline creation)
    # This ensures policy is loading/loaded by the time prepare() is called
    preload_locomotion_policy(cfg)

    pipeline_type = cfg.pipeline_type

    pipeline_class: type[RlPipeline] = getattr(robojudo.pipeline, pipeline_type)
    logger.info(f"Using pipeline: {pipeline_type} -> {pipeline_class}")

    pipeline = pipeline_class(cfg=cfg)
    
    # Set up signal handler to ensure clean shutdown
    def signal_handler(sig, frame):
        logger.warning("Interrupt received, shutting down gracefully...")
        if not cfg.env.is_sim:
            pipeline.env.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if not cfg.env.is_sim:
            # CRITICAL: Ensure robot is standing in sport mode BEFORE prepare
            # But do this AFTER pipeline creation so we can check if environment is in prepare mode
            net_if = getattr(cfg.env.unitree, 'net_if', 'eth0') if hasattr(cfg.env, 'unitree') else 'eth0'
            
            # Verify environment is in prepare mode (sport mode active)
            # Check config value first
            delay_mode_release = getattr(cfg.env.unitree, 'delay_mode_release', None) if hasattr(cfg.env, 'unitree') else None
            logger.info(f"Config delay_mode_release: {delay_mode_release}")
            
            in_prepare_mode = hasattr(pipeline.env, "_in_prepare_mode") and pipeline.env._in_prepare_mode
            logger.info(f"Environment _in_prepare_mode: {in_prepare_mode}")
            
            if not in_prepare_mode:
                logger.error("✗ CRITICAL: Robot is NOT in prepare mode (sport mode not active)!")
                logger.error(f"✗ Config delay_mode_release: {delay_mode_release}")
                if delay_mode_release is False or delay_mode_release is None:
                    logger.error("✗ delay_mode_release is False or not set in config!")
                    logger.error("✗ This will cause robot to drop! Aborting...")
                    raise RuntimeError("Robot not in prepare mode - delay_mode_release must be True in config")
                else:
                    logger.error("✗ delay_mode_release is True but _in_prepare_mode is False!")
                    logger.error("✗ This suggests mode was released during environment initialization")
                    logger.error("✗ Check environment initialization code")
                    raise RuntimeError("Robot not in prepare mode - mode may have been released too early")
            
            logger.info("✓ Robot is in prepare mode (sport mode active) - safe to proceed")
            logger.info("✓ Sport mode will maintain robot balance during prepare()")
            logger.info("✓ No need to check standing - sport mode handles it automatically")
            
            # Now do prepare (robot should be standing in sport mode)
            logger.info("Starting prepare() - robot should be standing in sport mode...")
            pipeline.prepare()
            # Release sport mode after prepare (if using UnitreeCppEnv with delay_mode_release)
            # BUT: V2 pipeline handles this internally, so check if it already released mode
            if hasattr(pipeline.env, "release_mode"):
                if hasattr(pipeline, "_mode_already_released") and pipeline._mode_already_released:
                    logger.info("Mode already released by pipeline (V2 pipeline handles mode release)")
                else:
                    # Robot should already be standing fine in sport mode - no need to wait
                    # Release sport mode immediately for fast switch
                    logger.info("Releasing sport mode and switching to developer mode (robot should already be standing)...")
                    pipeline.env.release_mode()

        while True:
            time_start = time.time()
            pipeline.step()
            time_end = time.time()
            time_diff = time_end - time_start

            # keep the pipeline running at the desired frequency
            if not cfg.run_fullspeed:
                time_diff = pipeline.dt - time_diff
                if time_diff > 0:
                    time.sleep(time_diff)
                else:
                    if not cfg.env.is_sim:
                        # Log as warning unless it's a very large drop
                        if time_diff < -0.1:
                            logger.error(f"Significant frame drop -> {time_diff}")
                        else:
                            logger.warning(f"Minor frame drop -> {time_diff}")
                            
                        # More tolerant exit threshold (500ms instead of 200ms)
                        if time_diff < -0.5:
                            logger.critical("Exiting due to excessive frame drop (>500ms)")
                            break
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt received")
    finally:
        # Ensure clean shutdown on exit
        if not cfg.env.is_sim:
            logger.info("Shutting down robot...")
            # If stand_at_end is True, use the safe transition instead of sudden shutdown
            if getattr(cfg, 'stand_at_end', False) and hasattr(pipeline.env, 'return_to_standing'):
                pipeline.env.return_to_standing()
            else:
                pipeline.env.shutdown()
            time.sleep(1)  # Give it time to switch to sport mode


if __name__ == "__main__":
    main()
