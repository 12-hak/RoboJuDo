# Rebuild unitree_cpp Extension

The C++ extension needs to be rebuilt for the `delay_mode_release` changes to take effect.

## On Linux (robot):

**First, install scikit-build-core if missing:**
```bash
python -m pip install scikit-build-core
```

**Then rebuild:**
```bash
cd /home/unitree/development/RoboJuDo/packages/unitree_cpp
rm -rf build/ dist/ *.egg-info/
python -m pip install -e . --no-build-isolation --no-deps --force-reinstall
```

**Or use the rebuild script:**
```bash
cd /home/unitree/development/RoboJuDo
./scripts/rebuild_unitree_cpp_fix.sh
```

## On Windows (if you have WSL or cross-compile):

Use the same commands in WSL or your Linux environment.

## Verify the rebuild worked:

After rebuilding, when you run the pipeline, you should see:
- `[UnitreeController] delay_mode_release = true`
- `[UnitreeController] delay_mode_release is TRUE - Mode release DELAYED...`
- `[UnitreeController] NOT releasing mode during initialization...`

If you still see "Motion control service shutdown successfully" without the `[UnitreeController]` prefix, the rebuild didn't work or the extension wasn't reloaded.

