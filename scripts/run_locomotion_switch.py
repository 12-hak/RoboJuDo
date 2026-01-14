#!/usr/bin/env python3
"""
Script to run different locomotion methods with BeyondMimic on real robot.

Usage:
    python scripts/run_locomotion_switch.py [amo|asap|smooth|unitree|unitree-wogait]
    
    Default: amo

Available locomotion methods:
    - amo: AMO (Adaptive Motion Optimization) - Default, good balance
    - asap: ASAP (Adaptive Skill-based Agile Policies) - Fast and agile
    - smooth: Smooth policy - Smooth and stable movements
    - unitree: Unitree default policy - Standard Unitree locomotion
    - unitree-wogait: Unitree without gait - Alternative Unitree mode
"""

import argparse
import os
import sys
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.resolve()
ROBOJUDO_DIR = SCRIPT_DIR.parent

# Change to RoboJuDo directory
os.chdir(ROBOJUDO_DIR)

# Map locomotion method to config name
LOCOMOTION_CONFIGS = {
    "amo": {
        "config": "g1_locomimic_beyondmimic_real_amo",
        "name": "AMO",
        "description": "Adaptive Motion Optimization - Good balance of speed and stability"
    },
    "asap": {
        "config": "g1_locomimic_beyondmimic_real_asap",
        "name": "ASAP",
        "description": "Adaptive Skill-based Agile Policies - Fast and agile"
    },
    "smooth": {
        "config": "g1_locomimic_beyondmimic_real_smooth",
        "name": "Smooth",
        "description": "Smooth policy - Smooth and stable movements"
    },
    "unitree": {
        "config": "g1_locomimic_beyondmimic_real_unitree",
        "name": "Unitree",
        "description": "Unitree default policy - Standard Unitree locomotion"
    },
    "unitree-wogait": {
        "config": "g1_locomimic_beyondmimic_real_unitree_wogait",
        "name": "Unitree (without gait)",
        "description": "Unitree policy without gait - Alternative Unitree mode"
    },
}


def list_methods():
    """List all available locomotion methods."""
    print("Available locomotion methods:")
    print("=" * 60)
    for key, info in LOCOMOTION_CONFIGS.items():
        print(f"  {key:15} - {info['name']:20} - {info['description']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run different locomotion methods with BeyondMimic on real robot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_locomotion_switch.py amo
  python scripts/run_locomotion_switch.py asap
  python scripts/run_locomotion_switch.py --list
        """
    )
    parser.add_argument(
        "method",
        nargs="?",
        default="amo",
        choices=list(LOCOMOTION_CONFIGS.keys()) + ["list"],
        help="Locomotion method to use (default: amo)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available locomotion methods"
    )
    
    args = parser.parse_args()
    
    if args.list or args.method == "list":
        list_methods()
        return
    
    # Get config info
    loco_info = LOCOMOTION_CONFIGS[args.method]
    config_name = loco_info["config"]
    loco_name = loco_info["name"]
    
    # Print info
    print("=" * 60)
    print(f"Running with {loco_name} locomotion method")
    print(f"Config: {config_name}")
    print(f"Description: {loco_info['description']}")
    print("=" * 60)
    print("Available beyondmimic policies: Dance_wose, Jump_wose, Violin, Waltz, spinkick_safe")
    print("")
    print("Controls:")
    print("  - Select: Switch to Locomotion")
    print("  - Start: Switch to Mimic")
    print("  - R1: Next mimic policy")
    print("  - L1: Previous mimic policy")
    print("  - A: Shutdown")
    print("")
    print("=" * 60)
    print("")
    
    # Run the pipeline using subprocess
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "-c", config_name],
        cwd=ROBOJUDO_DIR
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

