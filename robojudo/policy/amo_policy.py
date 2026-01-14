from collections import deque
import logging

import numpy as np
import torch

from robojudo.policy import Policy, policy_registry
from robojudo.policy.policy_cfgs import AMOPolicyCfg
from robojudo.utils.util_func import command_remap, quatToEuler

logger = logging.getLogger(__name__)


@policy_registry.register
class AMOPolicy(Policy):
    """
    Only Unitree G1 supported now.
    """

    cfg_policy: AMOPolicyCfg

    def __init__(self, cfg_policy, device):
        # device = "cuda" if torch.cuda.is_available() else "cpu"
        super().__init__(cfg_policy=cfg_policy, device=device)

        # if cpu device:
        if self.device == "cpu":
            for node in self.model.graph.nodes():  # type: ignore
                if node.kind() == "prim::Constant":
                    node: torch.Node
                    if "value" in node.attributeNames():
                        value = node.output().toIValue()
                        if isinstance(value, torch.device):
                            node.removeAttribute("value")
                            node.s_("value", "cpu")

        self.scales_ang_vel = self.cfg_policy.obs_scales.ang_vel
        self.scales_dof_vel = self.cfg_policy.obs_scales.dof_vel
        self.control_dt = 1.0 / self.cfg_policy.freq
        self.commands_map = self.cfg_policy.commands_map

        # TODO: move robot specific to cfg
        self.nj = 23
        self.n_priv = 3
        self.n_proprio = 3 + 2 + 2 + 23 * 3 + 2 + 15
        self.history_len = 10
        self.extra_history_len = 25
        self._n_demo_dof = 8

        self.arm_action = self.default_dof_pos[-self._n_demo_dof :]

        self.demo_obs_template = np.zeros((8 + 3 + 3 + 3,))
        self.demo_obs_template[: self._n_demo_dof] = self.default_dof_pos[-self._n_demo_dof :]
        self.demo_obs_template[self._n_demo_dof + 6 : self._n_demo_dof + 9] = 0.75

        self.target_yaw = 0.0
        self._in_place_stand_flag = True
        self.gait_cycle = np.array([0.25, 0.25])
        self.gait_freq = 1.3

        self.proprio_history_buf = deque(maxlen=self.history_len)
        self.extra_history_buf = deque(maxlen=self.extra_history_len)
        for _ in range(self.history_len):
            self.proprio_history_buf.append(np.zeros(self.n_proprio))
        for _ in range(self.extra_history_len):
            self.extra_history_buf.append(np.zeros(self.n_proprio))

        self.cmd = np.zeros(8, dtype=np.float32)
        # Initialize commands from commands_map (first 4: vel_y, ang_z, vel_x, height)
        if len(self.commands_map) >= 4:
            self.cmd[0:4] = [map[1] for map in self.commands_map[0:4]]
        
        # Height command initialization (default is middle of commands_map[3] range)
        self.height_command = self.commands_map[3][1] if len(self.commands_map) > 3 else 0.75  # Default to middle value

        self.adapter = torch.jit.load(self.cfg_policy.policy_adapter_file, map_location=self.device)
        self.adapter.eval()
        for param in self.adapter.parameters():
            param.requires_grad = False

        norm_stats = torch.load(self.cfg_policy.policy_adapter_norm_file, weights_only=False)
        self.input_mean = torch.tensor(norm_stats["input_mean"], device=self.device, dtype=torch.float32)
        self.input_std = torch.tensor(norm_stats["input_std"], device=self.device, dtype=torch.float32)
        self.output_mean = torch.tensor(norm_stats["output_mean"], device=self.device, dtype=torch.float32)
        self.output_std = torch.tensor(norm_stats["output_std"], device=self.device, dtype=torch.float32)

        self.adapter_input = torch.zeros((1, 8 + 4), device=self.device, dtype=torch.float32)
        self.adapter_output = torch.zeros((1, 15), device=self.device, dtype=torch.float32)

        self.reset()

    def reset(self):
        self.timestep: int = 0
        # Reset height command to default
        self.height_command = self.commands_map[3][1]  # Default to middle value
        # Reset arm positions to default
        self.target_arm_pos = self.default_dof_pos[-self._n_demo_dof :].copy()
        self.current_arm_pos = self.default_dof_pos[-self._n_demo_dof :].copy()

    def post_step_callback(self, commands=None):
        self.timestep += 1

    def _get_commands(self, ctrl_data):
        # if (ref_dof_pos := ctrl_data.get("ref_dof_pos", None)) is not None:
        #     self.arm_action = ref_dof_pos.copy()[-self._n_demo_dof :]

        commands = self.cmd.copy()
        for key in ctrl_data.keys():
            if key in ["JoystickCtrl", "UnitreeCtrl"]:
                axes = ctrl_data[key]["axes"]
                lx, ly, rx, ry = axes["LeftX"], axes["LeftY"], axes["RightX"], axes["RightY"]

                commands[0] = command_remap(ly, self.commands_map[0])
                commands[1] = command_remap(rx, self.commands_map[1])  # ang_z (robot turning)
                commands[2] = command_remap(lx, self.commands_map[2])
                # Height control via Up/Down buttons
                commands[3] = self.height_command

                button_event = ctrl_data[key]["button_event"]
                
                # Process button events for height and arm control
                for event in button_event:
                    if event["type"] == "button" and event["pressed"]:
                        if event["name"] == "Up":
                            # Increase height (clamp to max)
                            height_step = 0.05
                            self.height_command = min(
                                self.height_command + height_step,
                                self.commands_map[3][2]  # max height
                            )
                            commands[3] = self.height_command
                        elif event["name"] == "Down":
                            # Decrease height (clamp to min)
                            height_step = 0.05
                            self.height_command = max(
                                self.height_command - height_step,
                                self.commands_map[3][0]  # min height
                            )
                            commands[3] = self.height_command

                break
        return commands

    def get_observation(self, env_data, ctrl_data):
        self.cmd = self._get_commands(ctrl_data)

        dof_pos = env_data.dof_pos
        dof_vel = env_data.dof_vel
        base_quat = env_data.base_quat
        base_ang_vel = env_data.base_ang_vel
        

        rpy = quatToEuler(base_quat)

        # INFO: legacy code from official repo
        # self._in_place_stand_flag = np.abs(self.cmd[0]) < 0.1
        # self.target_yaw = self.cmd[1]
        # dyaw = rpy[2] - self.target_yaw
        # dyaw = np.remainder(dyaw + np.pi, 2 * np.pi) - np.pi
        # if self._in_place_stand_flag:
        #     dyaw = 0.0

        # INFO: new logic for better control
        self._in_place_stand_flag = np.all(np.abs(self.cmd[0:3]) < 0.1)
        dyaw = -self.cmd[1]
        dyaw = np.remainder(dyaw + np.pi, 2 * np.pi) - np.pi

        obs_dof_vel = dof_vel.copy()
        obs_dof_vel[[4, 5, 10, 11, 13, 14]] = 0.0

        gait_obs = np.sin(self.gait_cycle * 2 * np.pi)

        self.adapter_input = np.concatenate([np.zeros(4), dof_pos[15:]])

        # AMO adapter input format: [height, yaw, pitch, roll, arm_pos_0, ..., arm_pos_7]
        # Based on AMO code: adapter_input[0] = 0.75 + commands[3] where commands[3] is offset
        # Our cmd[3] is already the full height value (0.3-0.9), so use it directly
        # The adapter expects absolute height, and our cmd[3] is already in the right range
        self.adapter_input[0] = self.cmd[3]  # height (absolute, range 0.3-0.9)
        # Torso controls removed - set to 0.0 (default)
        self.adapter_input[1] = 0.0  # torso yaw (disabled)
        self.adapter_input[2] = 0.0  # torso pitch (disabled)
        self.adapter_input[3] = 0.0  # torso roll (disabled)

        self.adapter_input = torch.tensor(self.adapter_input).to(self.device, dtype=torch.float32).unsqueeze(0)

        self.adapter_input = (self.adapter_input - self.input_mean) / (self.input_std + 1e-8)
        self.adapter_output = self.adapter(self.adapter_input.view(1, -1))
        self.adapter_output = self.adapter_output * self.output_std + self.output_mean

        last_action_full = np.concatenate(
            [self.last_action, (dof_pos - self.default_dof_pos)[-self._n_demo_dof :] / self.action_scale]
        )
        obs_prop = np.concatenate(
            [
                base_ang_vel * self.scales_ang_vel,
                rpy[:2],
                (np.sin(dyaw), np.cos(dyaw)),
                (dof_pos - self.default_dof_pos),
                dof_vel * self.scales_dof_vel,
                last_action_full,
                gait_obs,
                self.adapter_output.cpu().numpy().squeeze(),
            ]
        )
        obs_priv = np.zeros((self.n_priv,))
        obs_hist = np.array(self.proprio_history_buf).flatten()

        obs_demo = self.demo_obs_template.copy()
        obs_demo[: self._n_demo_dof] = dof_pos[15:]
        obs_demo[self._n_demo_dof] = self.cmd[0]
        obs_demo[self._n_demo_dof + 1] = self.cmd[2]
        # Torso controls removed - set to 0.0 (default)
        obs_demo[self._n_demo_dof + 3] = 0.0  # torso yaw (disabled)
        obs_demo[self._n_demo_dof + 4] = 0.0  # torso pitch (disabled)
        obs_demo[self._n_demo_dof + 5] = 0.0  # torso roll (disabled)
        obs_demo[self._n_demo_dof + 6 : self._n_demo_dof + 9] = 0.75 + self.cmd[3]

        self.proprio_history_buf.append(obs_prop)
        self.extra_history_buf.append(obs_prop)

        self.gait_cycle = np.remainder(self.gait_cycle + self.control_dt * self.gait_freq, 1.0)
        if self._in_place_stand_flag and (
            (np.abs(self.gait_cycle[0] - 0.25) < 0.05) or (np.abs(self.gait_cycle[1] - 0.25) < 0.05)
        ):
            self.gait_cycle = np.array([0.25, 0.25])
        if (not self._in_place_stand_flag) and (
            (np.abs(self.gait_cycle[0] - 0.25) < 0.05) and (np.abs(self.gait_cycle[1] - 0.25) < 0.05)
        ):
            self.gait_cycle = np.array([0.25, 0.75])
        extras = {
            "commands": self.cmd.copy(),
        }
        return np.concatenate((obs_prop, obs_demo, obs_priv, obs_hist)), extras

    def get_action(self, obs):
        obs_tensor = torch.from_numpy(obs).float().unsqueeze(0).to(self.device)
        with torch.no_grad():
            extra_hist = (
                torch.tensor(np.array(self.extra_history_buf).flatten().copy(), dtype=torch.float)
                .view(1, -1)
                .to(self.device)
            )
            raw_action = self.model(obs_tensor, extra_hist).cpu().numpy().squeeze()

        raw_action = np.clip(raw_action, -40.0, 40.0)
        self.last_action = raw_action.copy()

        scaled_actions = raw_action * self.action_scale
        return scaled_actions
