# mjlab Training Improvements for Real Robot Deployment

## Issues Found on Real Robot
1. ✅ Waist wobble
2. ✅ Needs heavy action smoothing (0.75)
3. ✅ Conservative movements
4. ✅ Left/right direction was backwards
5. ❌ **Poor turning performance** (NEW)

## Required Changes for Retraining

### 1. INCREASE TURNING REWARD (Critical for your issue)

In `velocity_env_cfg.py`, line ~190:

```python
# BEFORE:
"track_angular_velocity": RewardTermCfg(
    func=mdp.track_angular_velocity,
    weight=2.0,  # Same as linear velocity
    params={"command_name": "twist", "std": math.sqrt(0.5)},
),

# AFTER:
"track_angular_velocity": RewardTermCfg(
    func=mdp.track_angular_velocity,
    weight=3.0,  # INCREASED from 2.0 - prioritize turning!
    params={"command_name": "twist", "std": math.sqrt(0.3)},  # Tighter tolerance
),
```

### 2. ADD WAIST MOVEMENT PENALTY (Fixes wobble)

Add this NEW reward around line 226:

```python
# NEW: Waist movement penalty
"waist_velocity_penalty": RewardTermCfg(
    func=mdp.joint_velocity_l2,
    weight=-0.5,  # Penalize waist movement
    params={
        "asset_cfg": SceneEntityCfg("robot", joint_names=["waist_.*"]),
    },
),
```

### 3. INCREASE ACTION SMOOTHNESS (Fixes jerky movements)

Change line ~226:

```python
# BEFORE:
"action_rate_l2": RewardTermCfg(func=mdp.action_rate_l2, weight=-0.1),

# AFTER:
"action_rate_l2": RewardTermCfg(func=mdp.action_rate_l2, weight=-0.5),
```

### 4. ADD STANDING STABILITY REWARD (Better balance)

Add this NEW reward:

```python
# NEW: Reward staying still when commanded to stand
"standing_stability": RewardTermCfg(
    func=mdp.base_velocity_penalty,
    weight=1.0,  # Reward low velocity when standing
    params={
        "command_name": "twist",
        "command_threshold": 0.1,  # When commands are near zero
    },
),
```

### 5. INCREASE UPRIGHT REWARD (Better standing)

Change line ~196:

```python
# BEFORE:
"upright": RewardTermCfg(
    func=mdp.flat_orientation,
    weight=1.0,
    ...
),

# AFTER:
"upright": RewardTermCfg(
    func=mdp.flat_orientation,
    weight=1.5,  # INCREASED from 1.0
    ...
),
```

### 6. MORE AGGRESSIVE OBSERVATION NOISE (Better sim-to-real)

In the `policy_terms` section (around line 40-68), update:

```python
# BEFORE:
"base_lin_vel": ObservationTermCfg(
    func=mdp.builtin_sensor,
    params={"sensor_name": "robot/imu_lin_vel"},
    noise=Unoise(n_min=-0.5, n_max=0.5),
),
"base_ang_vel": ObservationTermCfg(
    func=mdp.builtin_sensor,
    params={"sensor_name": "robot/imu_ang_vel"},
    noise=Unoise(n_min=-0.2, n_max=0.2),
),

# AFTER:
"base_lin_vel": ObservationTermCfg(
    func=mdp.builtin_sensor,
    params={"sensor_name": "robot/imu_lin_vel"},
    noise=Unoise(n_min=-1.0, n_max=1.0),  # INCREASED
),
"base_ang_vel": ObservationTermCfg(
    func=mdp.builtin_sensor,
    params={"sensor_name": "robot/imu_ang_vel"},
    noise=Unoise(n_min=-0.5, n_max=0.5),  # INCREASED
),
```

### 7. IMPROVE TURNING CURRICULUM (Better turning training)

In the `curriculum` section (around line 301-311), update:

```python
# BEFORE:
"command_vel": CurriculumTermCfg(
    func=mdp.commands_vel,
    params={
        "command_name": "twist",
        "velocity_stages": [
            {"step": 0, "lin_vel_x": (-1.0, 1.0), "ang_vel_z": (-0.5, 0.5)},
            {"step": 5000 * 24, "lin_vel_x": (-1.5, 2.0), "ang_vel_z": (-0.7, 0.7)},
            {"step": 10000 * 24, "lin_vel_x": (-2.0, 3.0)},
        ],
    },
),

# AFTER:
"command_vel": CurriculumTermCfg(
    func=mdp.commands_vel,
    params={
        "command_name": "twist",
        "velocity_stages": [
            # Start with more turning practice
            {"step": 0, "lin_vel_x": (-0.5, 0.5), "ang_vel_z": (-0.8, 0.8)},
            {"step": 3000 * 24, "lin_vel_x": (-1.0, 1.0), "ang_vel_z": (-1.0, 1.0)},
            {"step": 6000 * 24, "lin_vel_x": (-1.5, 2.0), "ang_vel_z": (-1.2, 1.2)},
            {"step": 10000 * 24, "lin_vel_x": (-2.0, 3.0), "ang_vel_z": (-1.5, 1.5)},
        ],
    },
),
```

### 8. INCREASE TRAINING DURATION (More learning time)

In your training script, increase iterations:

```python
# BEFORE:
max_iterations = 10000

# AFTER:
max_iterations = 15000  # 50% more training
```

## Summary of Changes

| Change | Purpose | Impact |
|--------|---------|--------|
| ↑ Angular velocity reward (2.0→3.0) | Better turning | **Fixes your turning issue** |
| ↑ Turning curriculum | More turning practice | **Fixes your turning issue** |
| + Waist velocity penalty (-0.5) | Reduce wobble | Fixes wobble |
| ↑ Action smoothness (-0.1→-0.5) | Smoother actions | Less tuning needed |
| + Standing stability (1.0) | Better standing | Stable when idle |
| ↑ Upright reward (1.0→1.5) | Better balance | More stable |
| ↑ Observation noise | Better sim-to-real | Works on real robot |
| ↑ Training duration | More learning | Better overall |

## Expected Results After Retraining

### Current Model:
- ❌ Poor turning response
- ❌ Waist wobble
- ❌ Needs action_scale=0.18, beta=0.75
- ❌ Needs waist scaling=0.4

### New Model Should:
- ✅ **Good turning** (responsive to angular commands)
- ✅ **No waist wobble** (learned to minimize waist movement)
- ✅ **Smoother actions** (less tuning needed)
- ✅ **Better standing** (stable when idle)
- ✅ Works with action_scale=0.3-0.4, beta=0.6-0.7
- ✅ Waist scaling=0.7-0.8 or not needed

## Quick Checklist

Before retraining, make sure you:
- [ ] Increase angular velocity reward weight to 3.0
- [ ] Add waist velocity penalty (-0.5)
- [ ] Increase action smoothness penalty to -0.5
- [ ] Add standing stability reward (1.0)
- [ ] Increase upright reward to 1.5
- [ ] Increase observation noise (2x)
- [ ] Update turning curriculum (more aggressive)
- [ ] Increase training iterations to 15000

Then retrain and test!

## Files to Modify

1. `velocity_env_cfg.py` - Main changes (rewards, observations, curriculum)
2. `env_cfgs.py` - No changes needed
3. Training script - Increase max_iterations

That's it! These changes should give you a much better policy for real robot deployment.
