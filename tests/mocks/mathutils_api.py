"""
Mock for Blender's mathutils module.
"""

from typing import Any

class Matrix:
    def __init__(self, data=None):
        self.data = data or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    
    def copy(self):
        return Matrix(self.data)
    
    def to_translation(self):
        return Vector((self.data[0][3], self.data[1][3], self.data[2][3]))
    
    @property
    def translation(self):
        return self.to_translation()
    
    @translation.setter
    def translation(self, val):
        pass

class Vector:
    def __init__(self, data=None):
        self.data = data or (0.0, 0.0, 0.0)
    
    def __add__(self, other):
        return Vector(tuple(a + b for a, b in zip(self.data, other.data)))
    
    def __repr__(self):
        return f"Vector({self.data})"

def Quaternion(data=None):
    return [1.0, 0.0, 0.0, 0.0]
