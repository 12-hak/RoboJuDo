#!/bin/bash
# Script to rebuild the unitree_cpp extension

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROBOJUDO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROBOJUDO_DIR" || exit 1

echo "Rebuilding unitree_cpp extension..."
echo ""

cd packages/unitree_cpp || exit 1

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/

# Rebuild
echo "Building unitree_cpp..."
python -m pip install -e . --no-build-isolation --no-deps --force-reinstall

echo ""
echo "✓ Rebuild complete!"
echo ""
echo "You should now see [UnitreeController] debug messages in the logs."
echo "If delay_mode_release=True, you should see:"
echo "  [UnitreeController] delay_mode_release is TRUE - Mode release DELAYED..."

