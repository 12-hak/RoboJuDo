#!/bin/bash
# Script to run g1_locomimic_beyondmimic_real config on real robot

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

# 1. START STATE ESTIMATOR (if not running)
ESTIMATOR_BIN="/home/unitree/development/state_e/build/g1_state_estimator"
LIVOX_CONFIG="/home/unitree/development/state_e/livox_config.json"

if [ ! -f "/dev/shm/g1_state_shm" ]; then
    echo "Starting State Estimator in background..."
    "$ESTIMATOR_BIN" eth0 "$LIVOX_CONFIG" > /dev/null 2>&1 &
    ESTIMATOR_PID=$!
    # Wait for shared memory to initialize
    sleep 2
    echo "✓ State Estimator started (PID: $ESTIMATOR_PID)"
else
    echo "✓ State Estimator is already running."
fi


# 2. RUN PIPELINE
echo "Running g1_locomimic_beyondmimic_real_sprint config..."
python scripts/run_pipeline.py -c g1_locomimic_beyondmimic_real_sprint

# 3. CLEANUP on exit
if [ -n "$ESTIMATOR_PID" ]; then
    echo "Cleaning up state estimator..."
    sudo kill $ESTIMATOR_PID
fi

