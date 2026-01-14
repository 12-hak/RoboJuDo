#!/bin/bash
# Script to rebuild the unitree_cpp extension with proper dependencies
# This ensures a COMPLETE clean rebuild to pick up C++ changes

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROBOJUDO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROBOJUDO_DIR" || exit 1

echo "=========================================="
echo "Rebuilding unitree_cpp Extension"
echo "=========================================="
echo ""

# Check if we're in the right conda environment
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "WARNING: Not in a conda environment. Please activate robojudo first:"
    echo "  conda activate robojudo"
    exit 1
fi

echo "Current conda environment: $CONDA_DEFAULT_ENV"
echo ""

# Install build dependencies
echo "Step 1: Installing build dependencies..."
echo "  - scikit-build-core..."
python -m pip install scikit-build-core --quiet
echo "  - pybind11 (must match Python version)..."
python -m pip install pybind11 --quiet
echo "✓ Build dependencies installed"
echo ""

# Verify pybind11 is installed and get its path
echo "Step 1.5: Verifying pybind11 installation..."
PYBIND11_PATH=$(python -c "import pybind11; print(pybind11.get_cmake_dir())" 2>/dev/null || echo "")
if [ -z "$PYBIND11_PATH" ]; then
    echo "ERROR: pybind11 not found in Python environment!"
    echo "Trying to install again..."
    python -m pip install pybind11 --force-reinstall
    PYBIND11_PATH=$(python -c "import pybind11; print(pybind11.get_cmake_dir())" 2>/dev/null || echo "")
    if [ -z "$PYBIND11_PATH" ]; then
        echo "ERROR: Failed to install pybind11!"
        exit 1
    fi
fi
echo "✓ pybind11 found at: $PYBIND11_PATH"
echo ""

cd packages/unitree_cpp || exit 1

# AGGRESSIVE clean - remove ALL build artifacts
echo "Step 2: Cleaning ALL previous builds..."
rm -rf build/
rm -rf dist/
rm -rf *.egg-info/
rm -rf __pycache__/
rm -rf src/__pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.so" -delete 2>/dev/null || true
echo "✓ Clean complete"
echo ""

# Rebuild
echo "Step 3: Building unitree_cpp extension..."
echo "This may take a few minutes..."
echo ""

# Set environment variables to help CMake find the right Python/pybind11
export CMAKE_ARGS="-DPython_EXECUTABLE=$(which python)"
export CMAKE_PREFIX_PATH="${CONDA_PREFIX:-}:${PYBIND11_PATH:-}"

# Build with verbose output to see what's happening
python -m pip install -e . --no-build-isolation --no-deps --force-reinstall 2>&1 | tee /tmp/unitree_cpp_build.log | grep -E "(Building|Compiling|Linking|Installing|Successfully|error|Error|ERROR|Using|Found|STATUS)" || true

# Check if build succeeded
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✓ Build completed successfully!"
else
    echo ""
    echo "✗ Build failed! Check /tmp/unitree_cpp_build.log for details."
    echo "Common issues:"
    echo "  - pybind11 version mismatch: Make sure pybind11 matches Python version"
    echo "  - Missing headers: Check that Python development headers are installed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Rebuild complete!"
echo "=========================================="
echo ""
echo "IMPORTANT: Restart your Python process to load the new extension!"
echo ""
echo "After restarting, you should see these messages when delay_mode_release=True:"
echo "  [UnitreeController] delay_mode_release = true"
echo "  [UnitreeController] delay_mode_release is TRUE - Mode release DELAYED..."
echo "  [UnitreeController] NOT releasing mode during initialization..."
echo ""
echo "If you still see 'Motion control service shutdown successfully' without"
echo "the [UnitreeController] prefix, the extension wasn't reloaded."
echo "=========================================="

