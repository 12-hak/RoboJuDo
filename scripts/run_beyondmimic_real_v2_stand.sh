#!/bin/bash
# Script to run g1_locomimic_beyondmimic_real_v2_stand config on real robot
# This version automatically returns the robot to sport mode and stands up on exit.

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

# Run the pipeline
echo "Running g1_locomimic_beyondmimic_real_v2_stand (V2 Pipeline + Auto-Stand)..."
echo "The robot will automatically return to sport mode standing on exit."
echo ""
echo "Available beyondmimic policies: Dance_wose, Jump_wose, Violin, Waltz, spinkick_safe, g1_run"
echo "Controls:"
echo "  - Select: Switch to Locomotion"
echo "  - Start: Switch to Mimic"
echo "  - R1: Next mimic policy"
echo "  - L1: Previous mimic policy"
echo "  - A: Return to Stand & Exit"
echo ""

python scripts/run_pipeline.py -c g1_locomimic_beyondmimic_real_v2_stand
