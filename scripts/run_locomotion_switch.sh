#!/bin/bash
# Script to run different locomotion methods with BeyondMimic on real robot
# Usage: ./run_locomotion_switch.sh [amo|asap|smooth|unitree|unitree-wogait]
# Default: amo

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROBOJUDO_DIR="$(dirname "$SCRIPT_DIR")"

# Change to RoboJuDo directory
cd "$ROBOJUDO_DIR" || exit 1

# Activate conda environment if it exists
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "Using conda environment: $CONDA_DEFAULT_ENV"
else
    # Try to activate robojudo environment if conda is available
    if command -v conda &> /dev/null; then
        echo "Activating robojudo conda environment..."
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate robojudo 2>/dev/null || echo "Warning: Could not activate robojudo environment"
    fi
fi

# Parse locomotion method argument
LOCO_METHOD="${1:-amo}"

# Map locomotion method to config name
case "$LOCO_METHOD" in
    amo)
        CONFIG_NAME="g1_locomimic_beyondmimic_real_amo"
        LOCO_NAME="AMO"
        ;;
    asap)
        CONFIG_NAME="g1_locomimic_beyondmimic_real_asap"
        LOCO_NAME="ASAP"
        ;;
    smooth)
        CONFIG_NAME="g1_locomimic_beyondmimic_real_smooth"
        LOCO_NAME="Smooth"
        ;;
    unitree)
        CONFIG_NAME="g1_locomimic_beyondmimic_real_unitree"
        LOCO_NAME="Unitree"
        ;;
    unitree-wogait)
        CONFIG_NAME="g1_locomimic_beyondmimic_real_unitree_wogait"
        LOCO_NAME="Unitree (without gait)"
        ;;
    *)
        echo "Error: Unknown locomotion method '$LOCO_METHOD'"
        echo "Available methods: amo, asap, smooth, unitree, unitree-wogait"
        exit 1
        ;;
esac

# Run the pipeline
echo "=========================================="
echo "Running with $LOCO_NAME locomotion method"
echo "Config: $CONFIG_NAME"
echo "=========================================="
echo "Available beyondmimic policies: Dance_wose, Jump_wose, Violin, Waltz, spinkick_safe"
echo ""
echo "Controls:"
echo "  - Select: Switch to Locomotion"
echo "  - Start: Switch to Mimic"
echo "  - R1: Next mimic policy"
echo "  - L1: Previous mimic policy"
echo "  - A: Shutdown"
echo ""
echo "=========================================="
echo ""

python scripts/run_pipeline.py -c "$CONFIG_NAME"

