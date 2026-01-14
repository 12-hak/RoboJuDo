#!/usr/bin/env python3
"""
Quick script to force robot back into sport mode (R2+A) from developer mode.
Uses the proper FSM sequence: Zero Torque -> Damp -> Stand -> Run (Start)

Based on:
- unitree_sdk2_python example: motionSwitcher/motion_switcher_example.py
- unitree_g1_vibes/FSM_README.md
- AIM-Robotics/debug_g1_loco.py
"""
import logging
import sys
import time

# Try to use Python SDK directly
try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
    from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
    from unitree_sdk2py.g1.loco.g1_loco_api import ROBOT_API_ID_LOCO_GET_FSM_ID, ROBOT_API_ID_LOCO_GET_FSM_MODE
    import json
    PYTHON_SDK_AVAILABLE = True
except ImportError:
    PYTHON_SDK_AVAILABLE = False
    # Fallback to our wrapper
    from robojudo.config.g1.env.g1_real_env_cfg import G1RealEnvCfg, G1UnitreeCfg
    from robojudo.environment.unitree_cpp_env import UnitreeCppEnv

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_fsm_id(client):
    """Get current FSM ID"""
    try:
        code, data = client._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
        if code == 0 and data:
            return json.loads(data).get("data")
    except:
        pass
    return None


def get_fsm_mode(client):
    """Get current FSM mode (0=static stand, 1=dynamic/gait, 2=feet unloaded)"""
    try:
        code, data = client._Call(ROBOT_API_ID_LOCO_GET_FSM_MODE, "{}")
        if code == 0 and data:
            return json.loads(data).get("data")
    except:
        pass
    return None




def return_to_sport_mode_python_sdk(net_if="eth0"):
    """Use Python SDK directly with proper FSM sequence"""
    logger.info("Using Python SDK (unitree_sdk2py) with FSM sequence...")
    
    # Initialize channel factory
    ChannelFactoryInitialize(0, net_if)
    logger.info(f"✓ Channel factory initialized (net_if: {net_if})")
    
    # Initialize both clients
    msc = MotionSwitcherClient()
    msc.SetTimeout(10.0)
    msc.Init()
    logger.info("✓ MotionSwitcherClient initialized")
    
    loco_client = LocoClient()
    loco_client.SetTimeout(10.0)
    loco_client.Init()
    logger.info("✓ LocoClient initialized")
    
    # PRE-INITIALIZE LocoClient before mode switch to save time
    loco_client = LocoClient()
    loco_client.SetTimeout(10.0)
    loco_client.Init()
    logger.info("✓ LocoClient pre-initialized")

    # Step 1: Select sport mode
    logger.info("\n" + "=" * 60)
    logger.info("STEP 1: Selecting sport mode and triggering stand IMMEDIATELY")
    logger.info("=" * 60)
    
    logger.info("Selecting 'ai' mode...")
    msc.SelectMode("ai")
    
    # IMMEDIATE TRIGGER: Don't wait, start requesting FSM 4 immediately
    # The first few requests will fail while mode is switching, but it will
    # catch it at the earliest possible millisecond.
    logger.info("Spamming SetFsmId(4) to catch transition...")
    success_trigger = False
    for i in range(20):
        code = loco_client.SetFsmId(4)
        if code == 0:
            logger.info(f"✓ Stand-up command (FSM 4) caught after {i*0.1:.2f}s!")
            success_trigger = True
            break
        time.sleep(0.1)
    
    if not success_trigger:
        logger.warning("⚠ Could not trigger FSM 4 automatically - robot may be in zero torque")
        logger.info("  Standard sequence: Set FSM Stand (4)...")
        code = loco_client.SetFsmId(4)  # FSM 4 = Stand-up
        if code == 0:
            logger.info("  ✓ SetFsmId(4) successful")
        else:
            logger.warning(f"  ⚠ SetFsmId(4) returned code: {code}")
    
    # User requested sequence: Spam(4) -> L2+B(1) -> L2+Up(4) -> Wait -> R2+A(801)
    logger.info("\nUser Sequence: Triggering L2+B (Damping / FSM 1)...")
    loco_client.SetFsmId(1)
    time.sleep(1.0)
    
    logger.info("User Sequence: Triggering L2+Up (Stand-up / FSM 4)...")
    loco_client.SetFsmId(4)
    
    logger.info("  Waiting 3 seconds for Stand-up to complete...")
    time.sleep(3)
    # Step 2: R2+A (Run Mode / FSM 801)
    logger.info("\nSTEP 2: Transitioning to Start/run mode (FSM 801) - R2+A mode...")
    code = loco_client.SetFsmId(801)  # FSM 801 = R2+A run mode
    if code == 0:
        logger.info("  ✓ SetFsmId(801) successful")
    else:
        logger.warning(f"  ⚠ SetFsmId(801) returned code: {code}")
    logger.info("  Waiting 1.5 seconds for R2+A run mode to activate...")
    time.sleep(1.5)
    
    # Verify final state
    final_fsm = get_fsm_id(loco_client)
    final_mode = get_fsm_mode(loco_client)
    logger.info(f"\nFinal FSM ID: {final_fsm}, Mode: {final_mode}")
    
    if final_fsm == 801:
        logger.info("✓ SUCCESS! Robot is in FSM 801 (R2+A run mode)")
        if final_mode == 0:
            logger.info("✓ Robot is standing with feet loaded - ready for operation!")
            return True
        elif final_mode == 1:
            logger.info("✓ Robot is in dynamic/gait mode - ready for walking!")
            return True
        else:
            logger.warning(f"⚠ Mode is {final_mode} (feet may be unloaded)")
            return True  # Still consider it success if FSM is 801
    else:
        logger.error(f"✗ Failed to reach FSM 801 (got {final_fsm})")
        logger.info(f"  Note: If you manually press R2+A, check what FSM ID the robot reports")
        return False


def return_to_sport_mode_cpp_wrapper(net_if="eth0"):
    """Fallback: Use our C++ wrapper (limited functionality)"""
    logger.warning("C++ wrapper does not support FSM sequence - use Python SDK instead")
    logger.warning("Falling back to basic mode selection...")
    
    cfg = G1RealEnvCfg(
        unitree=G1UnitreeCfg(
            net_if=net_if,
            delay_mode_release=False,
        )
    )
    
    env = UnitreeCppEnv(cfg_env=cfg)
    logger.info("✓ Environment initialized")
    
    if not hasattr(env, "select_sport_mode"):
        logger.error("select_sport_mode() not available!")
        return False
    
    # Just try to select mode - won't do full FSM sequence
    logger.warning("NOTE: This will only put robot in zero torque mode.")
    logger.warning("You will need to manually transition: Damp -> Stand -> Start")
    
    code = env.select_sport_mode("ai")
    time.sleep(0.5)
    
    return code == 0


def diagnostic_loop(net_if="eth0"):
    """Continuously monitor FSM ID and mode to detect R2+A button press"""
    if not PYTHON_SDK_AVAILABLE:
        logger.error("Python SDK not available - cannot run diagnostic")
        return
    
    logger.info("\n" + "=" * 60)
    logger.info("FSM DIAGNOSTIC MODE - Monitoring Robot State")
    logger.info("=" * 60)
    logger.info("Press R2+A on the controller to see what FSM ID it reports")
    logger.info("Press Ctrl+C to exit diagnostic mode")
    logger.info("=" * 60 + "\n")
    
    # Initialize channel factory
    ChannelFactoryInitialize(0, net_if)
    logger.info(f"✓ Channel factory initialized (net_if: {net_if})")
    
    # Initialize LocoClient
    loco_client = LocoClient()
    loco_client.SetTimeout(10.0)
    loco_client.Init()
    logger.info("✓ LocoClient initialized\n")
    
    last_fsm = None
    last_mode = None
    iteration = 0
    
    try:
        while True:
            current_fsm = get_fsm_id(loco_client)
            current_mode = get_fsm_mode(loco_client)
            
            # Detect changes
            fsm_changed = (current_fsm != last_fsm)
            mode_changed = (current_mode != last_mode)
            
            if fsm_changed or mode_changed or iteration == 0:
                # Format mode description
                mode_desc = {
                    0: "Static stand (feet loaded)",
                    1: "Dynamic/gait (feet loaded)",
                    2: "Feet unloaded (hanging/airborne)"
                }.get(current_mode, f"Unknown mode ({current_mode})")
                
                # Format FSM description
                fsm_desc = {
                    0: "Zero Torque",
                    1: "Damp",
                    2: "Squat",
                    3: "Sit",
                    4: "Stand-up",
                    200: "Start (balance/gait) - Python SDK",
                    500: "Start (balance/gait) - C++ SDK",
                    801: "R2+A Run Mode",
                    702: "Lie-to-Stand",
                    706: "Squat-to-Stand-up"
                }.get(current_fsm, f"Unknown FSM ({current_fsm})")
                
                timestamp = time.strftime("%H:%M:%S")
                change_indicator = " [CHANGED]" if (fsm_changed or mode_changed) and iteration > 0 else ""
                
                logger.info(f"[{timestamp}] FSM ID: {current_fsm:3d} ({fsm_desc}) | Mode: {current_mode} ({mode_desc}){change_indicator}")
            
            last_fsm = current_fsm
            last_mode = current_mode
            iteration += 1
            time.sleep(0.5)  # Check every 0.5 seconds
            
    except KeyboardInterrupt:
        logger.info("\n\nDiagnostic mode stopped by user")
        logger.info(f"Final state - FSM ID: {last_fsm}, Mode: {last_mode}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Return robot to sport mode from developer mode")
    parser.add_argument("--net-if", type=str, default="eth0", help="Network interface (default: eth0)")
    parser.add_argument("--diagnostic", action="store_true", help="Run diagnostic loop to monitor FSM ID (for detecting R2+A mode)")
    args = parser.parse_args()
    
    # If diagnostic mode requested, skip main function
    if args.diagnostic:
        diagnostic_loop(net_if=args.net_if)
        return 0
    
    logger.info("=" * 60)
    logger.info("Returning Robot to Sport Mode (R2+A)")
    logger.info("Using FSM sequence: Zero Torque -> Damp -> Stand -> Run")
    logger.info("=" * 60)
    
    success = False
    
    # Prefer Python SDK if available
    if PYTHON_SDK_AVAILABLE:
        logger.info("\nPython SDK available - using FSM sequence")
        success = return_to_sport_mode_python_sdk(net_if=args.net_if)
    else:
        logger.warning("\nPython SDK not available - using C++ wrapper (limited)")
        success = return_to_sport_mode_cpp_wrapper(net_if=args.net_if)
    
    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✓ SUCCESS! Robot should now be in sport mode (FSM 801 - R2+A)")
        logger.info("  Robot should be standing and ready for operation")
        logger.info("  If robot doesn't stand properly, check FSM state manually")
    else:
        logger.error("✗ FAILED to complete FSM sequence")
        logger.error("")
        logger.error("TROUBLESHOOTING:")
        logger.error("")
        logger.error("1. MANUAL METHOD (Recommended if SDK fails):")
        logger.error("   Press R2+START simultaneously on the controller")
        logger.error("   Then manually transition: Damp -> Stand -> Start")
        logger.error("")
        logger.error("2. Check if services are running:")
        logger.error("   systemctl status motion_switcher")
        logger.error("   systemctl status loco")
        logger.error("")
        logger.error("3. Last resort - reboot the robot:")
        logger.error("   sudo reboot")
    logger.info("=" * 60)
    
    # Offer to run diagnostic mode
    if success:
        logger.info("\n💡 TIP: Run with --diagnostic flag to monitor FSM ID when pressing R2+A")
        logger.info("   Example: python return_to_sport_mode.py --diagnostic")
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
