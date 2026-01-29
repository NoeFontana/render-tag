"""
Mock for BlenderProc module.
"""

from typing import Any, List, Optional

import numpy as np

# Re-use MockObject from blender_api for consistency if needed,
# or define simple stubs here.
# BlenderProc usually wraps blender objects.
# Import MockObject from blender_api
from tests.mocks.blender_api import MockMesh, MockObject


class MockBProcObject:
    def __init__(self, blender_obj=None):
        if blender_obj is None:
            self.blender_obj = MockObject()
        elif isinstance(blender_obj, dict):
            # Convert dict to MockObject for attribute access
            self.blender_obj = MockObject(name=blender_obj.get("name", "MockObject"))
            # Transfer other properties if needed
        else:
            self.blender_obj = blender_obj

        # Ensure name reflects the inner object
        self.name = self.blender_obj.name

    def get_location(self):
        return [0, 0, 0]

    def set_location(self, loc):
        pass

    def set_rotation_euler(self, rot):
        self.blender_obj.rotation_euler = list(rot)

    def set_scale(self, scale):
        self.blender_obj.scale = list(scale)

    def persist_transformation_into_mesh(self):
        pass

    def set_cp(self, key, value):
        # Set custom property on the blender object
        self.blender_obj[key] = value

    def enable_rigidbody(self, active: bool):
        pass

    def get_local2world_mat(self):
        return np.eye(4)


class MockLoader:
    def load_obj(self, filepath: str):
        return [MockBProcObject(blender_obj={"name": "LoadedObject"})]


class MockObjectModule:
    def create_primitive(self, shape, **kwargs):
        mesh = MockMesh(name=f"{shape}_Mesh")
        obj = MockObject(name=f"{shape}_primitive", data=mesh)
        return MockBProcObject(blender_obj=obj)

    def simulate_physics_and_fix_final_poses(self, **kwargs):
        pass


class MockCamera:
    def get_intrinsics_as_K_matrix(self):
        return np.eye(3)

    def add_camera_pose(self, transform):
        pass


class MockRenderer:
    def render(self):
        return {"colors": [np.zeros((480, 640, 3))], "depth": []}

    def enable_depth_output(self, **kwargs):
        pass


def init():
    pass


# Singleton instances
object = MockObjectModule()
loader = MockLoader()
camera = MockCamera()
renderer = MockRenderer()
