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

import robojudo.pipeline
from robojudo.config.config_manager import ConfigManager
from robojudo.pipeline.pipeline_cfgs import RlPipelineCfg
from robojudo.pipeline.rl_pipeline import RlPipeline

logger = logging.getLogger("robojudo")


def parse_args():
    parser = argparse.ArgumentParser(description="Test AMO locomotion with height control")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="g1_amo_real",
        help="Name of the config class to use (default: g1_amo_real)",
    )
    args = parser.parse_args()
    return args


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal, cleaning up...")
    if "pipeline" in globals():
        pipeline.env.shutdown()
    sys.exit(0)


def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    args = parse_args()
    logger.info(f"Using config: {args.config}")
    logger.info("=" * 60)
    logger.info("AMO Locomotion with Height and Torso Control Test")
    logger.info("=" * 60)
    logger.info("Controls:")
    logger.info("  - Left stick: Forward/Backward, Left/Right")
    logger.info("  - Right stick X: Turn left/right")
    logger.info("  - Up button: Increase height")
    logger.info("  - Down button: Decrease height")
    logger.info("  - Left button: Decrease torso yaw (turn left)")
    logger.info("  - Right button: Increase torso yaw (turn right)")
    logger.info("  - Select+Up: Increase torso pitch (lean forward)")
    logger.info("  - Select+Down: Decrease torso pitch (lean backward)")
    logger.info("  - Select+Left: Decrease torso roll (lean left)")
    logger.info("  - Select+Right: Increase torso roll (lean right)")
    logger.info("  - F3 button: Emergency stop (shutdown)")
    logger.info("=" * 60)
    logger.info("Note: Arms will smoothly transition to down position (3 seconds)")
    logger.info("      Arms are controlled by AMO adapter (dampened, moveable)")
    logger.info("=" * 60)

    config_manager = ConfigManager(config_name=args.config)

    cfg: RlPipelineCfg = config_manager.get_cfg()

    pipeline_type = cfg.pipeline_type

    pipeline_class: type[RlPipeline] = getattr(robojudo.pipeline, pipeline_type)
    logger.info(f"Using pipeline: {pipeline_type} -> {pipeline_class}")

    pipeline = pipeline_class(cfg=cfg)

    if not cfg.env.is_sim:
        logger.info("Preparing robot...")
        pipeline.prepare()
        logger.info("Robot ready! Use Up/Down buttons to control height.")

    try:
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
                        logger.error(f"Warning: frame drop -> {time_diff}")
                        if time_diff < -0.2:
                            logger.critical("Exiting due to excessive frame drop")
                            pipeline.env.shutdown()
                            time.sleep(10)
                            break
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        if not cfg.env.is_sim:
            logger.info("Shutting down robot...")
            pipeline.env.shutdown()
        logger.info("Test completed")


if __name__ == "__main__":
    main()

