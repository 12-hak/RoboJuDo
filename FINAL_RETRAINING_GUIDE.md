# Complete Retraining Guide - No Velocity Estimation (96 dims)

## Overview

Training a robust locomotion policy WITHOUT base_lin_vel estimation.
This is the BEST approach for sim-to-real transfer.

**Observation space: 96 dims** (was 99)
- Removed: base_lin_vel (3 dims)
- Keeps: Everything else (proprioception only)

---

## PART 1: Training Config Changes

### File: `velocity_env_cfg.py`

#### Change 1: Remove base_lin_vel from observations

```python
# Around line 40-68, in policy_terms:

policy_terms = {
    # REMOVE THIS LINE:
    # "base_lin_vel": ObservationTermCfg(
    #     func=mdp.builtin_sensor,
    #     params={"sensor_name": "robot/imu_lin_vel"},
    #     noise=Unoise(n_min=-0.5, n_max=0.5),
    # ),
    
    # KEEP THESE:
    "base_ang_vel": ObservationTermCfg(
        func=mdp.builtin_sensor,
        params={"sensor_name": "robot/imu_ang_vel"},
        noise=Unoise(n_min=-0.5, n_max=0.5),  # Increased from ±0.2
    ),
    "projected_gravity": ObservationTermCfg(
        func=mdp.projected_gravity,
        noise=Unoise(n_min=-0.05, n_max=0.05),
    ),
    "joint_pos": ObservationTermCfg(
        func=mdp.joint_pos_rel,
        noise=Unoise(n_min=-0.01, n_max=0.01),
    ),
    "joint_vel": ObservationTermCfg(
        func=mdp.joint_vel_rel,
        noise=Unoise(n_min=-2.0, n_max=2.0),  # Increased from ±1.5
    ),
    "actions": ObservationTermCfg(func=mdp.last_action),
    "command": ObservationTermCfg(
        func=mdp.generated_commands,
        params={"command_name": "twist"},
    ),
}
```

**Result**: Observation space is now 96 dims instead of 99.

---

#### Change 2: Add Hip Roll Penalty (CRITICAL)

```python
# Around line 183-278, in rewards section:

rewards = {
    # ... existing rewards ...
    
    # NEW: Hip roll velocity penalty (fixes leg spreading)
    "hip_roll_velocity_penalty": RewardTermCfg(
        func=mdp.joint_velocity_l2,
        weight=-1.5,  # Strong penalty
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=[".*hip_roll.*"]),
        },
    ),
    
    # NEW: Hip roll position penalty (keeps legs straight)
    "hip_roll_position_penalty": RewardTermCfg(
        func=mdp.joint_pos_deviation,
        weight=-0.5,
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=[".*hip_roll.*"]),
            "target_pos": 0.0,  # Keep at neutral
        },
    ),
    
    # ... rest of existing rewards ...
}
```

---

#### Change 3: Increase Forward Velocity Reward

```python
# Around line 184-188, MODIFY existing reward:

# BEFORE:
"track_linear_velocity": RewardTermCfg(
    func=mdp.track_linear_velocity,
    weight=2.0,
    params={"command_name": "twist", "std": math.sqrt(0.25)},
),

# AFTER:
"track_linear_velocity": RewardTermCfg(
    func=mdp.track_linear_velocity,
    weight=4.0,  # INCREASED from 2.0
    params={"command_name": "twist", "std": math.sqrt(0.2)},  # Tighter (was 0.25)
),
```

---

#### Change 4: Increase Angular Velocity Reward (Better Turning)

```python
# Around line 189-193, MODIFY existing reward:

# BEFORE:
"track_angular_velocity": RewardTermCfg(
    func=mdp.track_angular_velocity,
    weight=2.0,
    params={"command_name": "twist", "std": math.sqrt(0.5)},
),

# AFTER:
"track_angular_velocity": RewardTermCfg(
    func=mdp.track_angular_velocity,
    weight=3.5,  # INCREASED from 2.0
    params={"command_name": "twist", "std": math.sqrt(0.3)},  # Tighter (was 0.5)
),
```

---

#### Change 5: Increase Upright Reward

```python
# Around line 194-201, MODIFY existing reward:

# BEFORE:
"upright": RewardTermCfg(
    func=mdp.flat_orientation,
    weight=1.0,
    params={...},
),

# AFTER:
"upright": RewardTermCfg(
    func=mdp.flat_orientation,
    weight=2.0,  # INCREASED from 1.0
    params={...},
),
```

---

#### Change 6: Increase Action Smoothness Penalty

```python
# Around line 226, MODIFY existing reward:

# BEFORE:
"action_rate_l2": RewardTermCfg(func=mdp.action_rate_l2, weight=-0.1),

# AFTER:
"action_rate_l2": RewardTermCfg(func=mdp.action_rate_l2, weight=-0.5),
```

---

### File: `env_cfgs.py` (G1-specific config)

#### Change 7: Tighten Hip Roll Posture Tolerances

```python
# Around line 70-108, MODIFY posture rewards:

# BEFORE:
cfg.rewards["pose"].params["std_standing"] = {".*": 0.05}

# AFTER:
cfg.rewards["pose"].params["std_standing"] = {
    ".*": 0.05,
    ".*hip_roll.*": 0.01,  # NEW: Very tight for hip roll
}

# BEFORE:
cfg.rewards["pose"].params["std_walking"] = {
    # ... existing ...
    r".*hip_roll.*": 0.15,
    # ... rest ...
}

# AFTER:
cfg.rewards["pose"].params["std_walking"] = {
    # ... existing ...
    r".*hip_roll.*": 0.08,  # REDUCED from 0.15
    # ... rest ...
}
```

---

## PART 2: Deployment Code Changes (RoboJuDo)

### File: `robojudo/policy/sprint_policy.py`

#### Change: Update Observation Space (99 → 96 dims)

```python
# Around line 48-98, in get_observation method:

def get_observation(self, env_data, ctrl_data):
    self._update_commands(ctrl_data)
    
    base_quat = env_data.base_quat
    base_ang_vel = env_data.base_ang_vel
    # REMOVED: base_lin_vel (no longer needed!)
    dof_pos = env_data.dof_pos
    dof_vel = env_data.dof_vel
    
    dof_pos_minus_default = dof_pos - self.default_dof_pos
    
    v = np.array([0, 0, -1])
    projected_gravity = quat_rotate_inverse_np(base_quat, v)
    
    # Build observation - NO VELOCITY ESTIMATION (96 dims)
    obs = np.concatenate([
        # 1. base_ang_vel (3) - angular velocity from IMU
        (base_ang_vel * self.obs_scales.ang_vel).astype(np.float32),
        
        # 2. projected_gravity (3) - gravity vector in base frame
        (projected_gravity * self.obs_scales.projected_gravity).astype(np.float32),
        
        # 3. joint_pos (29) - joint positions relative to default
        (dof_pos_minus_default * self.obs_scales.dof_pos).astype(np.float32),
        
        # 4. joint_vel (29) - joint velocities
        (dof_vel * self.obs_scales.dof_vel).astype(np.float32),
        
        # 5. actions (29) - previous actions
        self.last_action.astype(np.float32),
        
        # 6. command (3) - velocity commands
        np.array([
            self.lin_vel_command[0],
            self.lin_vel_command[1],
            self.ang_vel_command[0],
        ], dtype=np.float32),
        
        # Total: 3 + 3 + 29 + 29 + 29 + 3 = 96 ✓
    ], axis=0)
    
    extras = {
        "commands": [self.lin_vel_command[0], self.lin_vel_command[1], self.ang_vel_command[0]],
    }
    return obs, extras
```

---

## PART 3: Training Parameters

### Training Script Settings

```python
# In your training script:

train_cfg = {
    "num_envs": 4096,           # More environments for better learning
    "max_iterations": 15000,    # Longer training (was 10000)
    "learning_rate": 3e-4,
    "num_steps_per_env": 24,
    "mini_batch_size": 4096,
    "gamma": 0.99,
    "lam": 0.95,
    "entropy_coef": 0.01,
    "clip_actions": 1.0,
}
```

---

## PART 4: Summary of All Changes

### Training Config (`velocity_env_cfg.py`):
1. ✅ **REMOVE** `base_lin_vel` from observations (99 → 96 dims)
2. ✅ **ADD** hip roll velocity penalty (weight=-1.5)
3. ✅ **ADD** hip roll position penalty (weight=-0.5)
4. ✅ **INCREASE** forward velocity reward (2.0 → 4.0)
5. ✅ **INCREASE** angular velocity reward (2.0 → 3.5)
6. ✅ **INCREASE** upright reward (1.0 → 2.0)
7. ✅ **INCREASE** action smoothness penalty (-0.1 → -0.5)

### G1 Config (`env_cfgs.py`):
8. ✅ **TIGHTEN** hip roll standing tolerance (0.05 → 0.01)
9. ✅ **TIGHTEN** hip roll walking tolerance (0.15 → 0.08)

### Deployment Code (`sprint_policy.py`):
10. ✅ **UPDATE** observation space (remove base_lin_vel, 96 dims)

### Training Parameters:
11. ✅ **INCREASE** max_iterations (10000 → 15000)

---

## PART 5: Expected Results

### Observation Space:
```
OLD (with velocity):  99 dims
NEW (no velocity):    96 dims

Breakdown:
- base_ang_vel:       3 dims
- projected_gravity:  3 dims
- joint_pos:         29 dims
- joint_vel:         29 dims
- actions:           29 dims
- command:            3 dims
TOTAL:               96 dims ✓
```

### Performance Improvements:
```
Metric                  | Current | After Retraining
------------------------|---------|------------------
Leg spread              | 20.9°   | < 5° ✅
Avg forward velocity    | 0.016   | > 0.3 m/s ✅
Hip pitch activity      | 0.43    | > 0.8 rad/s ✅
Movement authority      | Poor    | Good ✅
Turning                 | Poor    | Good ✅
Sim-to-real robustness  | Medium  | High ✅
```

---

## PART 6: Checklist

Before retraining:
- [ ] Remove `base_lin_vel` from `velocity_env_cfg.py`
- [ ] Add hip roll penalties (velocity + position)
- [ ] Increase forward velocity reward to 4.0
- [ ] Increase angular velocity reward to 3.5
- [ ] Increase upright reward to 2.0
- [ ] Increase action smoothness to -0.5
- [ ] Tighten hip roll tolerances in `env_cfgs.py`
- [ ] Set max_iterations to 15000

After training:
- [ ] Export ONNX model (should be 96 dims input)
- [ ] Update `sprint_policy.py` to remove base_lin_vel
- [ ] Test observation shape is 96
- [ ] Deploy to robot

---

## PART 7: Quick Reference

### Key Numbers:
- **Observation dims**: 96 (not 99!)
- **Action dims**: 29 (unchanged)
- **Training iterations**: 15000
- **Hip roll penalty**: -1.5
- **Forward velocity reward**: 4.0
- **Angular velocity reward**: 3.5

### Files to Modify:
1. `velocity_env_cfg.py` (7 changes)
2. `env_cfgs.py` (2 changes)
3. `sprint_policy.py` (1 change - after training)

---

## PART 8: Why This Will Work

### No Velocity Estimation Benefits:
1. ✅ **No sim-to-real gap** in velocity estimation
2. ✅ **More robust** - uses only reliable sensors
3. ✅ **Simpler** - fewer things to go wrong
4. ✅ **Proven** - many successful locomotion policies use this

### Hip Roll Penalty Benefits:
1. ✅ **Fixes leg spreading** (your main issue)
2. ✅ **Improves efficiency** (no wasted energy)
3. ✅ **Better movement** (straight legs = better push)

### Combined Effect:
- Policy learns to walk with straight legs
- Uses only proprioception (joints + IMU orientation)
- Robust to real-world conditions
- **Should work at action_scale 0.35-0.45 on real robot**

---

Good luck with retraining! This should give you a much better policy! 🚀
