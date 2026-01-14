# Mjlab Sim-to-Real Debugging Guide

## Current Status
Your mjlab `g1_velocity` model:
- ✅ Loads successfully
- ✅ Has correct observation space (99 dims)
- ✅ Has correct action space (29 dims)
- ❌ Doesn't balance on real robot

## What We've Configured

### Observation Space (99 dims) - MATCHES TRAINING
```python
1. base_lin_vel (3)        # Linear velocity in base frame
2. base_ang_vel (3)        # Angular velocity  
3. projected_gravity (3)   # Gravity vector in base frame
4. joint_pos (29)          # Joint positions relative to default
5. joint_vel (29)          # Joint velocities
6. actions (29)            # Previous actions
7. command (3)             # Velocity commands [lin_vel_x, lin_vel_y, ang_vel_z]
```

### Current Settings
```python
action_scale: 0.12         # Very conservative
action_beta: 0.4           # Heavy smoothing
action_clip: 30.0          # Tight limits
commands: ±0.5 m/s linear, ±0.3 rad/s angular
```

## Possible Issues & Solutions

### 1. Observation Mismatch
**Symptom**: Robot doesn't respond or behaves erratically
**Possible causes**:
- `base_lin_vel` might not be estimated correctly on real robot
- Observation scaling might be different than training
- Some observations might have noise/outliers

**Debug**:
```bash
python diagnose_mjlab.py
```

**Try**:
- Check if `base_lin_vel` is reasonable (not all zeros, not huge values)
- Add observation clipping/filtering
- Try setting `base_lin_vel` to zeros if it's noisy

### 2. Action Scale Too Low/High
**Symptom**: 
- Too low: Robot can't stand, collapses
- Too high: Rapid oscillations, shaking

**Current**: 0.12 (very conservative)
**Training**: 0.5

**Try progressively**:
```python
# If robot can't stand:
action_scale: 0.15  # Increase
action_beta: 0.5    # Less smoothing

# If robot oscillates:
action_scale: 0.10  # Decrease
action_beta: 0.3    # More smoothing
```

### 3. PD Gains Too Low
**Symptom**: Robot is "floppy", can't hold position

**Current PD gains** (in `g1_mjlab_policy_cfg.py`):
```python
stiffness: [100, 100, 100, 200, 40, 15, ...]  # Reduced for compliance
damping: [2, 2, 2, 4, 1.5, 0.8, ...]          # Reduced
```

**Try**: Increase stiffness/damping back to original values:
```python
stiffness: [150, 150, 150, 300, 80, 20, ...]
damping: [2, 2, 2, 4, 2, 1, ...]
```

### 4. Domain Randomization Gap
**Symptom**: Works in sim, fails on real robot

**Your training** (from `velocity_env_cfg.py`):
- Friction randomization: (0.3, 1.2)
- Push disturbances: ±0.5 m/s
- Noise on observations

**Issue**: Real robot might have:
- Different friction
- Different mass/inertia
- Sensor noise patterns
- Actuator delays

**Solutions**:
1. **Retrain with better domain randomization**:
   - Add actuator delay simulation
   - Add more aggressive noise
   - Randomize mass/inertia
   - Train on varied terrains

2. **Fine-tune on real robot**:
   - Collect real robot data
   - Use the current model as initialization
   - Fine-tune with real data

3. **Use system identification**:
   - Measure real robot parameters
   - Update sim to match real robot
   - Retrain

### 5. Missing Observations
**Possible**: Model might expect observations we're not providing correctly

**Check**:
- Is `base_lin_vel` being estimated? (Check logs)
- Are all 29 DOFs being read correctly?
- Is IMU data clean?

**Try**: Add logging to see actual observation values:
```python
# In mjlab_policy.py get_observation():
logger.info(f"base_lin_vel: {base_lin_vel}")
logger.info(f"base_ang_vel: {base_ang_vel}")
logger.info(f"projected_gravity: {projected_gravity}")
```

## Systematic Debugging Steps

### Step 1: Run Diagnostics
```bash
python diagnose_mjlab.py
```
Look for:
- NaN/Inf values
- Unreasonable observation ranges
- Model inference errors

### Step 2: Test in Simulation First
If you have access to the training environment:
1. Export the policy
2. Test in the EXACT same sim environment
3. Verify it works there
4. Then try real robot

### Step 3: Gradual Tuning
Start very conservative and build up:

```python
# Step 1: Ultra-safe (current)
action_scale: 0.12, action_beta: 0.4

# Step 2: If stable, increase slightly
action_scale: 0.15, action_beta: 0.5

# Step 3: Keep increasing if stable
action_scale: 0.18, action_beta: 0.6

# Step 4: Approach training values
action_scale: 0.22, action_beta: 0.7

# Goal: Get as close to training as possible
action_scale: 0.5, action_beta: 0.8
```

### Step 4: Compare with Working Policy
Run AMO side-by-side:
1. Note how AMO behaves
2. Compare observation values
3. Compare action magnitudes
4. See what's different

## Quick Fixes to Try Now

### Fix 1: Increase Action Scale
```python
# In g1_mjlab_policy_cfg.py
action_scale: float = 0.16  # Up from 0.12
action_beta: float = 0.5    # Less smoothing
```

### Fix 2: Increase PD Gains
```python
# In g1_mjlab_policy_cfg.py, G1_29MjlabDoF class
stiffness: [150, 150, 150, 300, 60, 20, ...]  # Increase
damping: [2, 2, 2, 4, 2, 1, ...]              # Increase
```

### Fix 3: Zero Out base_lin_vel (if it's noisy)
```python
# In mjlab_policy.py, get_observation()
base_lin_vel = np.zeros(3, dtype=np.float32)  # Force to zero
```

### Fix 4: Add Observation Clipping
```python
# In mjlab_policy.py, get_observation()
obs = np.clip(obs, -100, 100)  # Prevent extreme values
```

## Learning Resources

### Understanding Sim-to-Real
1. **Domain Randomization**: Vary sim parameters during training
2. **System Identification**: Measure real robot, update sim
3. **Residual RL**: Train a correction policy on real robot
4. **Adaptive Control**: Online adaptation to real dynamics

### Key Papers
- "Sim-to-Real Transfer of Robotic Control with Dynamics Randomization"
- "Learning Quadrupedal Locomotion over Challenging Terrain"
- "Learning Agile Robotic Locomotion Skills by Imitating Animals"

### Debugging Philosophy
1. **Start simple**: Get basic standing working first
2. **One change at a time**: Don't change multiple things
3. **Log everything**: Add extensive logging
4. **Compare with baseline**: Use AMO as reference
5. **Iterate quickly**: Small changes, fast tests

## Next Steps

1. **Run diagnostics**: `python diagnose_mjlab.py`
2. **Try Fix 1**: Increase action_scale to 0.16
3. **If still fails**: Try Fix 3 (zero base_lin_vel)
4. **If still fails**: Increase PD gains (Fix 2)
5. **Document findings**: Note what works/doesn't work
6. **Consider retraining**: With better domain randomization

Good luck! Sim-to-real is hard but very rewarding when it works! 🚀
