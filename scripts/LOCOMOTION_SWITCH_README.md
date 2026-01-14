# Locomotion Method Switching

This directory contains scripts to easily switch between different locomotion methods when running BeyondMimic on the real robot.

## Available Locomotion Methods

1. **AMO** (Adaptive Motion Optimization) - Default, good balance of speed and stability
2. **ASAP** (Adaptive Skill-based Agile Policies) - Fast and agile movements
3. **Smooth** - Smooth and stable movements
4. **Unitree** - Standard Unitree default locomotion policy
5. **Unitree (without gait)** - Alternative Unitree mode without gait

## Usage

### Bash Script

```bash
# Run with AMO (default)
./run_locomotion_switch.sh amo

# Run with ASAP
./run_locomotion_switch.sh asap

# Run with Smooth
./run_locomotion_switch.sh smooth

# Run with Unitree
./run_locomotion_switch.sh unitree

# Run with Unitree (without gait)
./run_locomotion_switch.sh unitree-wogait
```

### Python Script

```bash
# Run with AMO (default)
python scripts/run_locomotion_switch.py amo

# Run with ASAP
python scripts/run_locomotion_switch.py asap

# List all available methods
python scripts/run_locomotion_switch.py --list
```

## Controls (Same for all methods)

- **Select**: Switch to Locomotion mode
- **Start**: Switch to Mimic mode
- **R1**: Next mimic policy
- **L1**: Previous mimic policy
- **A**: Emergency shutdown

## Available Mimic Policies

- Dance_wose
- Jump_wose
- Violin
- Waltz
- spinkick_safe

## Configuration Files

The locomotion method configs are defined in:
`robojudo/config/g1/g1_loco_mimic_cfg.py`

Config classes:
- `g1_locomimic_beyondmimic_real_amo`
- `g1_locomimic_beyondmimic_real_asap`
- `g1_locomimic_beyondmimic_real_smooth`
- `g1_locomimic_beyondmimic_real_unitree`
- `g1_locomimic_beyondmimic_real_unitree_wogait`

Each config extends `g1_locomimic_beyondmimic_real` and only changes the `loco_policy` parameter.

