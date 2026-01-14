#!/usr/bin/env python3
"""
Script to run different locomotion methods with BeyondMimic on real robot using FAST pipeline.
The fast pipeline includes optimized policy loading for faster startup.

Usage:
    python scripts/run_locomotion_switch_fast.py [amo|asap|smooth|unitree|unitree-wogait]
    
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

# Map locomotion method to fast config name
LOCOMOTION_CONFIGS = {
    "amo": {
        "config": "g1_locomimic_beyondmimic_real_amo_fast",
        "name": "AMO (Fast)",
        "description": "Adaptive Motion Optimization - Good balance of speed and stability (Fast loading)"
    },
    "asap": {
        "config": "g1_locomimic_beyondmimic_real_asap_fast",
        "name": "ASAP (Fast)",
        "description": "Adaptive Skill-based Agile Policies - Fast and agile (Fast loading)"
    },
    "smooth": {
        "config": "g1_locomimic_beyondmimic_real_smooth_fast",
        "name": "Smooth (Fast)",
        "description": "Smooth policy - Smooth and stable movements (Fast loading)"
    },
    "unitree": {
        "config": "g1_locomimic_beyondmimic_real_unitree_fast",
        "name": "Unitree (Fast)",
        "description": "Unitree default policy - Standard Unitree locomotion (Fast loading)"
    },
    "unitree-wogait": {
        "config": "g1_locomimic_beyondmimic_real_unitree_wogait_fast",
        "name": "Unitree (without gait) (Fast)",
        "description": "Unitree policy without gait - Alternative Unitree mode (Fast loading)"
    },
}


def list_methods():
    """List all available locomotion methods."""
    print("Available locomotion methods (FAST VERSION):")
    print("=" * 60)
    for key, info in LOCOMOTION_CONFIGS.items():
        print(f"  {key:15} - {info['name']:30} - {info['description']}")
    print("=" * 60)
    print("\nNote: Fast version uses optimized policy loading for faster startup.")


def main():
    parser = argparse.ArgumentParser(
        description="Run different locomotion methods with BeyondMimic on real robot (FAST VERSION)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_locomotion_switch_fast.py amo
  python scripts/run_locomotion_switch_fast.py asap
  python scripts/run_locomotion_switch_fast.py --list
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
    print(f"Running with {loco_name} locomotion method (FAST VERSION)")
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


