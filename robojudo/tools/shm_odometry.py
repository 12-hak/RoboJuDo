import mmap
import ctypes
import numpy as np
import logging
from robojudo.utils.util_func import quat_rotate_inverse_np

logger = logging.getLogger(__name__)

class RobotStateSHM(ctypes.Structure):
    """
    Structure matching the C++ StatePublisher.hpp PolicyInput struct.
    Used for reading high-frequency, filtered state estimates from shared memory.
    """
    _fields_ = [
        ("pos", ctypes.c_double * 3),
        ("quat", ctypes.c_double * 4), # w, x, y, z
        ("vel", ctypes.c_double * 3),
        ("vel_body", ctypes.c_double * 3),
        ("omega", ctypes.c_double * 3),
        ("grav", ctypes.c_double * 3),
        ("q", ctypes.c_double * 35),
        ("dq", ctypes.c_double * 35),
        ("raw_acc", ctypes.c_double * 3),
        ("raw_quat", ctypes.c_double * 4),
    ]

class ShmOdometry:
    def __init__(self, shm_path="/dev/shm/g1_state_shm"):
        self.shm_path = shm_path
        self.mm = None
        self.shm_size = ctypes.sizeof(RobotStateSHM)
        self.is_valid = False
        
        try:
            # We don't use 'with' here because we want to keep it open
            self.f = open(self.shm_path, "r+b")
            self.mm = mmap.mmap(self.f.fileno(), self.shm_size)
            self.is_valid = True
            logger.info(f"Connected to State Estimator via SHM: {shm_path}")
        except FileNotFoundError:
            logger.error(f"Shared memory '{shm_path}' not found. State estimator may not be running.")
        except Exception as e:
            logger.error(f"Failed to open SHM: {e}")

    def get_data(self):
        if not self.is_valid:
            return None
        
        state = RobotStateSHM.from_buffer(self.mm)
        
        # Position and Velocity are in WORLD frame from the estimator
        # But policies often expect Linear Velocity in BODY frame
        pos = np.array(state.pos, dtype=np.float32)
        vel_world = np.array(state.vel, dtype=np.float32)
        quat = np.array(state.quat, dtype=np.float32) # [w, x, y, z]
        
        # RoboJuDo utilities usually expect [x, y, z, w] for quaternions
        # Convert [w, x, y, z] to [x, y, z, w]
        quat_xyzw = np.array([quat[1], quat[2], quat[3], quat[0]], dtype=np.float32)
        
        # Use pre-calculated body velocity from SHM
        vel_body = np.array(state.vel_body, dtype=np.float32)
        
        return {
            "pos": pos,
            "vel_world": vel_world,
            "vel_body": vel_body,
            "quat": quat_xyzw,
            "omega": np.array(state.omega, dtype=np.float32),
            "grav": np.array(state.grav, dtype=np.float32),
        }

    def __del__(self):
        if self.mm:
            self.mm.close()
        if hasattr(self, 'f'):
            self.f.close()
