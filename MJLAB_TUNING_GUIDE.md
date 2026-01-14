# Mjlab Locomotion Policy Tuning Guide

## Current Settings (VERY CONSERVATIVE)
Located in: `robojudo/config/g1/policy/g1_mjlab_policy_cfg.py`

### Action Processing
- `action_scale: 0.15` - How much to scale the neural network outputs
- `action_beta: 0.5` - Action smoothing (0=max smooth, 1=no smooth)
- `action_clip: 40.0` - Maximum action magnitude

### Command Velocities (Joystick Mapping)
- Forward/Back: ±0.6 m/s
- Turning: ±0.4 rad/s
- Lateral: ±0.5 m/s

---

## Progressive Tuning Steps

### Step 1: VERY CONSERVATIVE (Current - Start Here!)
```python
action_scale: 0.15
action_beta: 0.5
commands_map: [[-0.6, 0.0, 0.6], [0.4, 0.0, -0.4], [0.5, 0.0, -0.5]]
```
**Goal**: Robot should be very stable, slow but controlled

---

### Step 2: CONSERVATIVE (If Step 1 is stable)
```python
action_scale: 0.18
action_beta: 0.6
commands_map: [[-0.8, 0.0, 0.8], [0.5, 0.0, -0.5], [0.6, 0.0, -0.6]]
```
**Goal**: Slightly faster, still very safe

---

### Step 3: MODERATE (If Step 2 is stable)
```python
action_scale: 0.20
action_beta: 0.7
commands_map: [[-1.0, 0.0, 1.0], [0.6, 0.0, -0.6], [0.8, 0.0, -0.8]]
```
**Goal**: Normal walking speed, good stability

---

### Step 4: NORMAL (If Step 3 is stable)
```python
action_scale: 0.22
action_beta: 0.75
commands_map: [[-1.2, 0.0, 1.2], [0.8, 0.0, -0.8], [1.0, 0.0, -1.0]]
```
**Goal**: Good performance, approaching sim speed

---

### Step 5: AGGRESSIVE (Only if Step 4 is very stable!)
```python
action_scale: 0.25
action_beta: 0.8
commands_map: [[-1.5, 0.0, 1.5], [1.0, 0.0, -1.0], [1.0, 0.0, -1.0]]
```
**Goal**: Maximum performance, sim-like behavior

---

## Troubleshooting

### Robot is shaking/oscillating:
- **Decrease** `action_scale` by 0.02
- **Decrease** `action_beta` by 0.1 (more smoothing)
- **Reduce** PD gains (stiffness/damping) in the DoF config

### Robot is too slow/sluggish:
- **Increase** `action_scale` by 0.02
- **Increase** `action_beta` by 0.1 (less smoothing)
- **Increase** command velocities by 0.1-0.2

### Robot falls when turning:
- **Reduce** turning command (middle value in commands_map)
- **Decrease** `action_scale`
- Check ankle stiffness isn't too low

### Robot doesn't respond to commands:
- **Increase** command velocities
- Check observation scales are reasonable
- Verify model is getting correct inputs (check logs)

---

## Quick Edit Instructions

1. Open: `robojudo/config/g1/policy/g1_mjlab_policy_cfg.py`
2. Find the section: `# ===== VERY CONSERVATIVE SETTINGS FOR INITIAL TESTING =====`
3. Edit the three main parameters
4. Save and restart: `python scripts/run_pipeline.py -c g1_locomimic_beyondmimic_real_mjlab`

---

## Safety Notes

- **Always** test in a safe, open area
- **Always** have emergency stop ready (A button)
- **Never** skip tuning steps - build up gradually
- **Monitor** joint temperatures during testing
- **Stop immediately** if you hear unusual sounds or see erratic behavior
