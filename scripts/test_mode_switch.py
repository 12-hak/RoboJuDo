#!/usr/bin/env python3
"""
Simple script to test mode switching between sport mode and developer mode.
Useful for tuning the transitions.
"""
import logging
import signal
import sys
import time

from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg, G1UnitreeCfg
from robojudo.environment.unitree_cpp_env import UnitreeCppEnv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("Mode Switching Test Script")
    logger.info("=" * 60)
    logger.info("")
    logger.info("IMPORTANT: Before running this script:")
    logger.info("  1. Power on the robot")
    logger.info("  2. Press R2+A on the controller to enter SPORT MODE")
    logger.info("  3. Wait for robot to stand up")
    logger.info("  4. Then run this script")
    logger.info("")
    logger.info("Press Enter when robot is in sport mode and ready...")
    input()
    
    # Initialize environment
    logger.info("Initializing robot environment...")
    cfg = G1RealEnvCfg(
        unitree=G1UnitreeCfg(
            net_if="eth0",  # Change to your network interface
            delay_mode_release=True,  # Keep in sport mode initially
        )
    )
    
    env = UnitreeCppEnv(cfg_env=cfg)
    logger.info("✓ Environment initialized")
    
    # Immediately check mode status
    logger.info("\nChecking initial mode status...")
    if hasattr(env, "check_mode"):
        form, name = env.check_mode()
        logger.info(f"  Current mode - form: '{form}', name: '{name if name else '(none - developer mode)'}'")
        if not name:
            logger.warning("  ⚠ WARNING: Robot appears to be in developer mode, not sport mode!")
            logger.warning("  Please press R2+A on controller to enter sport mode, then restart this script.")
            return
        else:
            logger.info(f"  ✓ Robot is in sport mode: '{name}'")
    else:
        logger.warning("  check_mode() not available, cannot verify initial state")
    
    # Set up signal handler
    def signal_handler(sig, frame):
        logger.warning("\nInterrupt received, returning to sport mode and exiting...")
        if hasattr(env, "select_sport_mode"):
            env.select_sport_mode("ai")
            time.sleep(1)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Step 1: Verify robot is in sport mode (R2+A)
        logger.info("\n" + "=" * 60)
        logger.info("STEP 1: Verifying robot is in SPORT MODE (R2+A)")
        logger.info("Press Enter to continue...")
        input()
        
        # Check current mode
        if hasattr(env, "check_mode"):
            form, name = env.check_mode()
            logger.info(f"Current mode - form: '{form}', name: '{name if name else '(none)'}'")
        
        env.update()
        logger.info(f"Robot state - Base height: {env.base_pos[2]:.3f}m")
        logger.info("Waiting 3 seconds to observe sport mode behavior...")
        for i in range(3):
            env.update()
            logger.info(f"  [{i+1}/3] Height: {env.base_pos[2]:.3f}m")
            time.sleep(1)
        
        # Step 2: Release sport mode (switch to developer mode)
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Releasing sport mode -> Switching to DEVELOPER MODE (R1+Y)")
        logger.info("Press Enter to continue...")
        input()
        
        if hasattr(env, "release_mode"):
            logger.info("Calling release_mode()...")
            env.release_mode()
            logger.info("✓ release_mode() called")
            
            # Check mode after release
            time.sleep(1)  # Give it a moment
            if hasattr(env, "check_mode"):
                form, name = env.check_mode()
                logger.info(f"Mode after release - form: '{form}', name: '{name if name else '(none - should be developer mode)'}'")
        else:
            logger.error("release_mode() not available!")
            return
        
        # Wait and observe
        logger.info("\nWaiting 5 seconds to observe developer mode behavior...")
        logger.info("(Robot should now be in developer mode - you can send low-level commands)")
        for i in range(5):
            env.update()
            logger.info(f"  [{i+1}/5] Base height: {env.base_pos[2]:.3f}m, "
                       f"vel: {env.base_lin_vel[0]:.3f} m/s")
            time.sleep(1)
        
        # Step 3: Return to sport mode
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Returning to SPORT MODE (R2+A)")
        logger.info("Press Enter to continue...")
        input()
        
        if hasattr(env, "select_sport_mode"):
            # Try different mode names - G1 might use different names
            mode_names_to_try = ["ai", "SportAI", "normal", "sport_mode", "ai_sport"]
            
            logger.info("Attempting to return to sport mode...")
            for mode_name in mode_names_to_try:
                logger.info(f"\nTrying mode name: '{mode_name}'...")
                try:
                    env.select_sport_mode(mode_name)
                    logger.info(f"  ✓ Called select_sport_mode('{mode_name}')")
                    
                    # Wait a bit and check if it worked
                    time.sleep(2)
                    
                    # Check mode status
                    if hasattr(env, "check_mode"):
                        form, name = env.check_mode()
                        logger.info(f"  Mode check - form: '{form}', name: '{name if name else '(none)'}'")
                        if name:
                            logger.info(f"  ✓ SUCCESS! Mode '{mode_name}' worked - robot is now in sport mode: '{name}'")
                            break
                        else:
                            logger.warning(f"  ✗ Mode '{mode_name}' did not work - still in developer mode")
                    else:
                        env.update()
                        logger.info(f"  After switch - Height: {env.base_pos[2]:.3f}m")
                        if env.base_pos[2] > 0.3:
                            logger.info(f"  ✓ Mode '{mode_name}' appears to be working (robot standing)!")
                            break
                except Exception as e:
                    logger.warning(f"  Mode '{mode_name}' failed with exception: {e}")
        else:
            logger.error("select_sport_mode() not available!")
            return
        
        # Wait and observe
        logger.info("\nWaiting 5 seconds to observe sport mode behavior...")
        for i in range(5):
            env.update()
            logger.info(f"  [{i+1}/5] Base height: {env.base_pos[2]:.3f}m, "
                       f"vel: {env.base_lin_vel[0]:.3f} m/s")
            time.sleep(1)
        
        # Step 4: Test multiple switches
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: Testing multiple mode switches")
        logger.info("Will switch: Sport -> Developer -> Sport -> Developer -> Sport")
        logger.info("Press Enter to start...")
        input()
        
        for cycle in range(2):
            logger.info(f"\n--- Cycle {cycle + 1} ---")
            
            # To developer
            logger.info("Switching to DEVELOPER MODE...")
            if hasattr(env, "release_mode"):
                env.release_mode()
            time.sleep(3)
            env.update()
            logger.info(f"  Developer mode - Height: {env.base_pos[2]:.3f}m")
            
            # Back to sport
            logger.info("Switching to SPORT MODE...")
            if hasattr(env, "select_sport_mode"):
                # Try the mode name that worked before, or default to "ai"
                env.select_sport_mode("ai")  # G1 typically uses "ai" for sport mode
            time.sleep(3)
            env.update()
            logger.info(f"  Sport mode - Height: {env.base_pos[2]:.3f}m")
        
        logger.info("\n" + "=" * 60)
        logger.info("Test complete!")
        logger.info("Final state: Returning to sport mode...")
        if hasattr(env, "select_sport_mode"):
            # Try "ai" which is the common G1 sport mode name
            env.select_sport_mode("ai")
            time.sleep(2)
        
    except KeyboardInterrupt:
        logger.warning("\nKeyboard interrupt")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        # Always return to sport mode on exit
        logger.info("\nCleaning up - returning to sport mode...")
        if hasattr(env, "select_sport_mode"):
            # Try "ai" which is the common G1 sport mode name
            env.select_sport_mode("ai")
            time.sleep(1)
        logger.info("Done.")


if __name__ == "__main__":
    main()

