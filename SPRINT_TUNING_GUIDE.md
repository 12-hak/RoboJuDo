# G1 Sprint Policy Tuning Guide

## Your New Model: g1_sprint.onnx

Trained with improvements:
- ✅ Waist movement penalty → Should have minimal wobble
- ✅ Action smoothness penalty → Should need less smoothing
- ✅ Better turning rewards → Should turn better!
- ✅ Standing stability → Should balance well when idle

## Starting Configuration (Conservative)

```python
action_scale: 0.25      # Start at 50% of training (0.5)
action_beta: 0.6        # Moderate smoothing
commands: ±0.8/±0.6/±0.6  # Conservative speeds
PD gains: Normal        # No special waist treatment
```

## Progressive Tuning Steps

### Step 1: Test Basic Standing (Current Config)
```bash
python scripts/run_pipeline.py -c g1_locomimic_beyondmimic_real_sprint
```

**What to check:**
- [ ] Robot stands without falling
- [ ] Minimal/no waist wobble
- [ ] Stable when idle

**If unstable:**
- Reduce action_scale to 0.20
- Increase action_beta to 0.65

**If too stiff/slow:**
- Increase action_scale to 0.28
- Reduce action_beta to 0.65

---

### Step 2: Increase Action Scale (If Step 1 Good)

Edit `g1_sprint_policy_cfg.py`:
```python
action_scale: 0.30  # Increase from 0.25
action_beta: 0.65   # Slightly less smoothing
```

**What to check:**
- [ ] Still stable standing
- [ ] Better response to commands
- [ ] No new wobble

---

### Step 3: Test Turning (Critical!)

Keep robot standing, test turning with right stick.

**What to check:**
- [ ] Turns left when stick right
- [ ] Turns right when stick left
- [ ] Smooth, controlled turning
- [ ] No excessive waist movement

**If turning is poor:**
- This means training didn't work as expected
- Increase angular velocity command range
- Or retrain with even higher turning reward

**If turning is good:**
- Celebrate! The training improvements worked!

---

### Step 4: Increase Command Speeds

Edit `g1_sprint_policy_cfg.py`:
```python
commands_map: [
    [-1.0, 0.0, 1.0],   # Forward/back
    [0.8, 0.0, -0.8],   # Left/right
    [-0.8, 0.0, 0.8],   # Turning
]
```

**What to check:**
- [ ] Faster forward/back movement
- [ ] Good lateral movement
- [ ] Responsive turning

---

### Step 5: Approach Training Values

Edit `g1_sprint_policy_cfg.py`:
```python
action_scale: 0.35  # Getting closer to 0.5
action_beta: 0.7    # Less smoothing
commands_map: [
    [-1.2, 0.0, 1.2],
    [1.0, 0.0, -1.0],
    [-1.0, 0.0, 1.0],
]
```

---

### Step 6: Maximum Performance (If All Good)

```python
action_scale: 0.4   # 80% of training
action_beta: 0.75   # Minimal smoothing
commands_map: [
    [-1.5, 0.0, 1.5],
    [1.0, 0.0, -1.0],
    [-1.0, 0.0, 1.0],
]
```

---

## Expected vs Old Model

| Metric | Old (g1_velocity) | New (g1_sprint) Expected |
|--------|-------------------|-------------------------|
| Action scale | 0.18 | 0.30-0.40 |
| Action smoothing | 0.75 | 0.60-0.70 |
| Waist scaling | 0.4 (40%) | 1.0 (none needed!) |
| Waist wobble | Yes | Minimal/none |
| Turning | Poor | Good |
| Standing | Needs tuning | Stable |

---

## Troubleshooting

### Waist Still Wobbles
- Model might need more training iterations
- Try adding small waist scaling (0.8) in policy
- Check if waist PD gains are too low

### Poor Turning
- Training might not have emphasized it enough
- Increase angular velocity command range
- Consider retraining with even higher turning reward (4.0)

### Too Aggressive
- Reduce action_scale
- Increase action_beta
- This is normal - tune down from training values

### Too Conservative
- Increase action_scale toward 0.5
- Reduce action_beta toward 0.8
- Increase command speeds

---

## Quick Reference

**File to edit**: `robojudo/config/g1/policy/g1_sprint_policy_cfg.py`

**Key parameters**:
- Line ~90: `action_scale`
- Line ~93: `action_beta`
- Lines ~99-103: `commands_map`

**To run**:
```bash
python scripts/run_pipeline.py -c g1_locomimic_beyondmimic_real_sprint
```

Good luck! The new model should be significantly better! 🚀
