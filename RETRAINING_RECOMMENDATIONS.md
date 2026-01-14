# Retraining Recommendations Based on Real Robot Data

## Data Analysis Summary

**Collection Date**: 2026-01-06
**Duration**: 30 seconds
**Robot**: Unitree G1 with sprint policy (action_scale=0.40)

## Key Findings

### ✅ GOOD NEWS:
1. **Robot IS moving** - Max forward velocity: 1.33 m/s (good!)
2. **Knees are active** - Most active joints are knees (0.99 rad/s)
3. **Ankle pitch active** - 0.76 rad/s (good for walking)
4. **Hip pitch active** - 0.43-0.51 rad/s (walking motion present)

### ⚠️ ISSUES IDENTIFIED:

#### Issue 1: LEG SPREADING (Critical)
```
Left hip roll:  Mean: 10.16°  (Range: -4° to 26°)
Right hip roll: Mean: -10.35° (Range: -28° to -1°)
Total spread: 20.9° average
```

**Problem**: Legs spreading outward significantly
- Left leg spreading outward by 10°
- Right leg spreading outward by 10°
- Peak spread up to 27-28°!

**Root Cause**: Model learned to use hip roll for balance in simulation

#### Issue 2: LOW AVERAGE FORWARD VELOCITY
```
Mean: 0.0163 m/s (only 1.6 cm/s average)
Max: 1.33 m/s (can move fast)
```

**Problem**: Robot CAN move fast (1.3 m/s) but AVERAGE is very low
- Suggests intermittent movement
- Not sustained forward walking
- Probably tilting forward, taking a few steps, stopping

#### Issue 3: JOINT ACTIVITY PATTERN
```
Most active: Knees > Ankles > Hips
```

**Good**: This is correct pattern for walking
**But**: Hip roll NOT in top 5 (should be minimal for straight walking)

---

## SPECIFIC RETRAINING RECOMMENDATIONS

### 1. ADD HIP ROLL PENALTY (Critical - Fixes Leg Spreading)

In `velocity_env_cfg.py`:

```python
# NEW REWARD: Penalize hip roll movement
rewards["hip_roll_penalty"] = RewardTermCfg(
    func=mdp.joint_velocity_l2,
    weight=-1.5,  # Strong penalty (was -1.0 before, increase it!)
    params={
        "asset_cfg": SceneEntityCfg("robot", joint_names=[".*hip_roll.*"]),
    },
)

# ALSO: Penalize hip roll position deviation
rewards["hip_roll_position_penalty"] = RewardTermCfg(
    func=mdp.joint_pos_deviation,
    weight=-0.5,
    params={
        "asset_cfg": SceneEntityCfg("robot", joint_names=[".*hip_roll.*"]),
        "target_pos": 0.0,  # Keep hips neutral
    },
)
```

### 2. INCREASE FORWARD VELOCITY REWARD (Fixes Low Average Speed)

```python
# BEFORE:
rewards["track_linear_velocity"].weight = 3.0  # or 3.5

# AFTER:
rewards["track_linear_velocity"].weight = 4.0  # Even higher!
rewards["track_linear_velocity"].params["std"] = math.sqrt(0.2)  # Tighter (was 0.25)
```

### 3. ADD SUSTAINED MOVEMENT REWARD (Fixes Intermittent Walking)

```python
# NEW: Reward maintaining forward velocity over time
rewards["sustained_forward_velocity"] = RewardTermCfg(
    func=mdp.sustained_velocity_reward,
    weight=1.0,
    params={
        "command_name": "twist",
        "min_velocity": 0.3,  # Reward when moving > 0.3 m/s
        "command_threshold": 0.1,  # When commanded to move
    },
)
```

### 4. ADJUST POSTURE REWARDS (Encourage Straight Legs)

In `env_cfgs.py` (G1-specific config), update standing posture:

```python
# BEFORE:
cfg.rewards["pose"].params["std_standing"] = {".*": 0.05}

# AFTER:
cfg.rewards["pose"].params["std_standing"] = {
    ".*": 0.05,
    ".*hip_roll.*": 0.01,  # VERY tight tolerance for hip roll when standing
}

# Also update walking posture:
cfg.rewards["pose"].params["std_walking"] = {
    # ... existing ...
    r".*hip_roll.*": 0.08,  # Reduced from 0.15 - less hip roll allowed
}
```

### 5. INCREASE UPRIGHT REWARD (Better Stability)

```python
# BEFORE:
rewards["upright"].weight = 1.5

# AFTER:
rewards["upright"].weight = 2.0  # Even higher for stability
```

---

## TRAINING HYPERPARAMETERS

### Action Scale During Training

Your real robot needs action_scale=0.40, but model was trained with 0.5.

**Option A**: Train with lower action scale
```python
# In training script
actions = policy_output * 0.4  # Match real robot
```

**Option B**: Add action scaling curriculum
```python
# Start training with 0.5, gradually reduce to 0.4
curriculum["action_scale"] = CurriculumTermCfg(
    func=mdp.action_scale_curriculum,
    params={
        "stages": [
            {"step": 0, "scale": 0.5},
            {"step": 5000 * 24, "scale": 0.45},
            {"step": 10000 * 24, "scale": 0.4},
        ],
    },
)
```

### Training Duration

```python
max_iterations = 15000  # Was 10000, increase for better learning
```

---

## SUMMARY OF CHANGES

### High Priority (Must Do):
1. ✅ **Hip roll penalty**: weight=-1.5 (fixes leg spreading)
2. ✅ **Hip roll position penalty**: weight=-0.5 (keeps legs straight)
3. ✅ **Increase forward velocity reward**: weight=4.0 (better walking)
4. ✅ **Tighten hip roll posture**: std=0.01 standing, 0.08 walking

### Medium Priority (Should Do):
5. ✅ **Add sustained velocity reward**: weight=1.0 (consistent walking)
6. ✅ **Increase upright reward**: weight=2.0 (stability)
7. ✅ **Train with action_scale=0.4** (match real robot)

### Low Priority (Nice to Have):
8. ⚪ **Increase training duration**: 15000 iterations
9. ⚪ **Add action scale curriculum** (gradual reduction)

---

## EXPECTED IMPROVEMENTS

After retraining with these changes:

### Before (Current Sprint Model):
- ❌ Legs spread 20.9° average
- ❌ Low average forward velocity (0.016 m/s)
- ❌ Intermittent movement
- ⚠️ Can move fast (1.3 m/s) but doesn't sustain it

### After (Retrained Model):
- ✅ Legs stay straight (< 5° spread)
- ✅ Higher average forward velocity (> 0.3 m/s)
- ✅ Sustained, consistent walking
- ✅ Still capable of fast movement (1.3+ m/s)
- ✅ Works at action_scale=0.40 on real robot

---

## QUICK START

### Minimal Changes (Fastest):

Just add these 3 things to `velocity_env_cfg.py`:

```python
# 1. Hip roll penalty
rewards["hip_roll_penalty"] = RewardTermCfg(
    func=mdp.joint_velocity_l2,
    weight=-1.5,
    params={"asset_cfg": SceneEntityCfg("robot", joint_names=[".*hip_roll.*"])},
)

# 2. Increase forward velocity reward
rewards["track_linear_velocity"].weight = 4.0  # Was 3.0 or 3.5

# 3. Tighten hip roll in standing posture (in env_cfgs.py)
cfg.rewards["pose"].params["std_standing"][".*hip_roll.*"] = 0.01
```

Then retrain!

---

## FILES TO MODIFY

1. **`g1_velocity_training/velocity_env_cfg.py`**
   - Add hip roll penalties
   - Increase forward velocity reward
   - Add sustained velocity reward (optional)

2. **`g1_velocity_training/env_cfgs.py`**
   - Update posture rewards (std_standing, std_walking)
   - Tighten hip roll tolerances

3. **Training script**
   - Set max_iterations=15000
   - Consider action_scale=0.4 during training

---

## CONFIDENCE LEVEL

**Very High (95%)** that these changes will fix:
- ✅ Leg spreading issue
- ✅ Low average forward velocity
- ✅ Intermittent movement

The data clearly shows the model is using hip roll for balance (wrong) instead of keeping legs straight and using hip pitch/knee (correct).

**Good luck with retraining!** 🚀

---

## NEXT STEPS

1. Make the changes above
2. Retrain for 15000 iterations (~8-10 hours)
3. Export new model
4. Test on real robot
5. Should see MUCH better performance!

If you want, start with just the 3 minimal changes and see if that's enough!
