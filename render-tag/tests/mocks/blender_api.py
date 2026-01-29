"""
Mock for Blender's bpy module.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockObject:
    name: str = "MockObject"
    location: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation_euler: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    dimensions: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    data: Any = None
    pass_index: int = 0

    # Custom properties simulation
    _properties: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key):
        return self._properties.get(key)

    def __setitem__(self, key, value):
        self._properties[key] = value

    def get(self, key, default=None):
        return self._properties.get(key, default)

    def get_location(self):
        return self.location

    def set_location(self, loc):
        self.location = list(loc)

    def set_rotation_euler(self, rot):
        self.rotation_euler = list(rot)

    def set_scale(self, scale):
        self.scale = list(scale)

    def enable_rigidbody(self, active: bool):
        pass


class MockCollection:
    def __init__(self):
        self._objects = {}

    def new(self, *args: Any, **kwargs: Any) -> Any:
        name = args[0] if args else kwargs.get("name", "MockObject")
        obj = MockObject(name=name)
        self._objects[name] = obj
        return obj

    def get(self, name: str, default=None):
        return self._objects.get(name, default)

    def __iter__(self):
        return iter(self._objects.values())

    def __getitem__(self, key):
        if key in self._objects:
            return self._objects[key]
        raise KeyError(f"Key '{key}' not found in MockCollection")

    def __len__(self):
        return len(self._objects)

    def clear(self):
        self._objects.clear()

    def append(self, obj):
        # Allow appending objects (mostly for materials list)
        # Use object name as key or a generated one
        name = getattr(obj, "name", f"Appended_{len(self)}")
        self._objects[name] = obj


class MockContext:
    def __init__(self):
        self.scene = MockScene()
        self.view_layer = MockViewLayer()
        self.selected_objects = []


class MockScene:
    def __init__(self):
        self.camera = MockObject(name="Camera")
        self.render = MockRender()
        self.collection = MockCollection()


class MockRender:
    def __init__(self):
        self.resolution_x = 640
        self.resolution_y = 480


class MockViewLayer:
    def update(self):
        pass


class MockOps:
    def __getattr__(self, name):
        return MockOps()

    def __call__(self, *args, **kwargs):
        # Absorb calls to operators
        return {"FINISHED"}


class MockImages(MockCollection):
    def load(self, filepath: str):
        return MockObject(name="LoadedImage")


class MockCollections(MockCollection):
    def new(self, name: str):
        # Override to return specialized mocks if needed, or handle in MockData
        return super().new(name)


class MockSocket(MockObject):
    pass


class MockNode(MockObject):
    def __init__(self, name="MockNode"):
        super().__init__(name=name)
        self.inputs = MockCollection()
        self.outputs = MockCollection()
        # Pre-populate common sockets to avoid key errors
        self.inputs._objects["Base Color"] = MockSocket(name="Base Color")
        self.inputs._objects["Alpha"] = MockSocket(name="Alpha")
        self.inputs._objects["Roughness"] = MockSocket(name="Roughness")
        self.inputs._objects["Specular"] = MockSocket(name="Specular")
        self.inputs._objects["Specular IOR Level"] = MockSocket(name="Specular IOR Level")
        self.inputs._objects["Emission"] = MockSocket(name="Emission")
        self.inputs._objects["Emission Strength"] = MockSocket(name="Emission Strength")
        self.outputs._objects["Color"] = MockSocket(name="Color")
        self.outputs._objects["Alpha"] = MockSocket(name="Alpha")
        self.outputs._objects["BSDF"] = MockSocket(name="BSDF")
        self.image = None  # For texture nodes


class MockNodes(MockCollection):
    def new(self, name: str, **kwargs: Any) -> Any:
        type_name = name
        node = MockNode(name=type_name)

        # Default sockets
        default_inputs = [
            "Base Color",
            "Alpha",
            "Roughness",
            "Specular",
            "Specular IOR Level",
            "Emission",
            "Emission Strength",
            "Color",
            "Strength",
        ]
        default_outputs = ["Color", "Alpha", "BSDF"]

        if type_name == "ShaderNodeOutputMaterial":
            # Override for Output node
            default_inputs = ["Surface", "Volume", "Displacement"]
            default_outputs = []
        elif type_name == "ShaderNodeTexImage":
            default_inputs = ["Vector"]
            default_outputs = ["Color", "Alpha"]
        elif type_name == "ShaderNodeEmission":
            default_inputs = ["Color", "Strength"]
            default_outputs = ["Emission"]

        # Clear generic defaults from __init__ if any (MockNode creates some)
        node.inputs._objects.clear()
        node.outputs._objects.clear()

        for name in default_inputs:
            node.inputs._objects[name] = MockSocket(name=name)
        for name in default_outputs:
            node.outputs._objects[name] = MockSocket(name=name)

        self._objects[type_name] = node
        return node


class MockLinks(MockCollection):
    def new(self, input_socket: Any, output_socket: Any) -> Any:
        link = MockObject(name="Link")
        self._objects["Link"] = link
        return link


class MockNodeTree:
    def __init__(self):
        self.nodes = MockNodes()
        self.links = MockLinks()


class MockMaterial(MockObject):
    def __init__(self, name="MockMaterial"):
        super().__init__(name=name)
        self.use_nodes = False
        self.node_tree = MockNodeTree()
        self.diffuse_color = [1, 1, 1, 1]


class MockMaterials(MockCollection):
    def new(self, name: str):
        mat = MockMaterial(name=name)
        self._objects[name] = mat
        return mat


class MockUVLayers(MockCollection):
    def new(self, name: str = "UVLayer", **kwargs: Any) -> Any:
        obj = MockObject(name=name)
        self._objects[name] = obj
        return obj


class MockMesh(MockObject):
    def __init__(self, name="MockMesh"):
        super().__init__(name=name)
        self.materials = MockCollection()
        self.uv_layers = MockUVLayers()


class MockData:
    def __init__(self):
        self.objects = MockCollection()
        self.materials = MockMaterials()
        self.images = MockImages()
        self.meshes = MockCollection()


# Singleton instances
context = MockContext()
data = MockData()
ops = MockOps()
