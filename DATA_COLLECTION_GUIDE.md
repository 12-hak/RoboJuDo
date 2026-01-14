# Real Robot Data Collection Guide

## Why Collect Data?

Your sprint model has sim-to-real issues:
- ❌ Won't move forward (just tilts)
- ❌ Legs spread when trying to walk
- ❌ Unstable at higher action scales
- ❌ Can't find sweet spot between movement and stability

**Solution**: Collect real robot data to identify what's different from simulation.

## Quick Start

### 1. Integrate Logger into Your Policy

Add to `robojudo/policy/sprint_policy.py`:

```python
from robot_data_logger import RobotDataLogger

class SprintLocoPolicy(Policy):
    def __init__(self, cfg_policy, device):
        # ... existing init ...
        self.data_logger = RobotDataLogger() if cfg_policy.log_data else None
    
    def get_action(self, obs: np.ndarray) -> np.ndarray:
        # ... existing code ...
        
        # Log data if enabled
        if self.data_logger:
            self.data_logger.log_step(
                env_data=self.last_env_data,  # Store this in get_observation
                policy_output={'raw_action': actions, 'final_action': processed_actions},
                commands=[self.lin_vel_command[0], self.lin_vel_command[1], self.ang_vel_command[0]],
                config={
                    'action_scale': self.action_scale,
                    'action_beta': self.action_beta,
                    'action_clip': self.action_clip,
                }
            )
        
        return processed_actions
```

### 2. Enable Logging in Config

Add to `g1_sprint_policy_cfg.py`:

```python
class G1SprintLocoPolicyCfg(MjlabLocoPolicyCfg):
    # ... existing config ...
    log_data: bool = True  # Enable data logging
```

### 3. Run and Collect Data

```bash
# Run robot for 30-60 seconds
# Try different movements:
# - Standing still
# - Forward command
# - Backward command
# - Left/right
# - Turning

./scripts/run_beyondmimic_real.sh

# When done (Ctrl+C), data auto-saves to robot_data_logs/
```

### 4. Analyze Data

```bash
python analyze_robot_data.py

# Or specify file:
python analyze_robot_data.py robot_data_logs/robot_data_20260106_080000.h5
```

## What the Analysis Will Tell You

### Issue 1: Not Moving Forward
```
⚠️  ISSUE: Commanded forward but robot not moving!
→ Action scale too low OR model not learned forward walking

RECOMMENDATION:
1. INCREASE forward walking reward in training
   - Add specific reward for forward velocity tracking
```

### Issue 2: Legs Spreading
```
⚠️  ISSUE: Legs spreading too much!
→ Model learned different hip behavior in sim

RECOMMENDATION:
2. ADD hip roll penalty in training
   - Penalize hip_roll joint movement
```

### Issue 3: Actions Too Small/Large
```
⚠️  ISSUE: Actions very small!
→ Action scale might be too low

RECOMMENDATION:
3. TRAIN with lower action scale in sim
   - Real robot needs action_scale=0.40
   - Train with action_scale=0.3-0.4 instead of 0.5
```

### Issue 4: Instability
```
⚠️  ISSUE: High angular velocity (unstable)
→ Action scale too high OR smoothing too low

RECOMMENDATION:
4. ADD base stability penalty
   - Penalize high angular velocity
   - Increase upright reward weight
```

## Next Steps After Analysis

### Option 1: Fix Training Config (Recommended)

Based on analysis, update `velocity_env_cfg.py`:

```python
# If legs spreading:
rewards["hip_roll_penalty"] = RewardTermCfg(
    func=mdp.joint_velocity_l2,
    weight=-1.0,
    params={"joint_names": [".*hip_roll.*"]},
)

# If not moving forward:
rewards["track_linear_velocity"].weight = 3.0  # Increase from 2.0

# If unstable:
rewards["upright"].weight = 2.0  # Increase from 1.5
```

Then retrain!

### Option 2: System Identification (Advanced)

Use the data to measure:
- Actual PD gains (stiffness/damping)
- Actuator response time
- Friction coefficients

Update MuJoCo model to match, then retrain.

### Option 3: Fine-tuning (Quick Fix)

Use collected data to fine-tune existing model:
- Collect 100+ episodes
- Fine-tune with real data
- Much faster than full retraining

## Files Created

1. `robot_data_logger.py` - Data collection class
2. `analyze_robot_data.py` - Analysis script
3. This guide

## Summary

You've done great work getting this far! The model is:
- ✅ Better than original (no waist wobble)
- ✅ Better turning (trained with higher reward)
- ✅ More stable standing

But has sim-to-real gaps:
- ❌ Forward walking
- ❌ Leg spreading
- ❌ Action scale mismatch

**Collecting real data will tell you exactly what to fix in training!**

Good luck! 🚀
