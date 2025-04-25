# bsdf_texture_baker/__init__.py

bl_info = {
    "name": "Principled BSDF texture map exporter",
    "author": "OceansCurse",
    "version": (1, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Auto Bake",
    "description": "Automates baking of Base Color, Roughness, Normal, and AO maps from Principled BSDF for game models",
    "category": "Render",
}

import sys
import importlib

# Import the classes from their respective modules
from .bake_operator import AUTOBAKE_OT_BakeMaps 
from .panel import AUTOBAKE_PT_Panel
from .properties import AutoBakeProperties

# List of classes to register
classes = (
    AUTOBAKE_OT_BakeMaps,
    AUTOBAKE_PT_Panel,
    AutoBakeProperties,
)

def register():
    from bpy.utils import register_class
    # Register all classes
    for cls in classes:
        register_class(cls)
    # Register the custom property group
    from bpy.types import Scene
    from bpy.props import PointerProperty
    Scene.autobake_props = PointerProperty(type=AutoBakeProperties)

def unregister():
    from bpy.utils import unregister_class
    # Unregister all classes
    for cls in reversed(classes):
        unregister_class(cls)
    # Remove the custom property group
    from bpy.types import Scene
    del Scene.autobake_props

    # Clear module cache to ensure fresh imports on reload
    modules = [key for key in sys.modules if key.startswith('bsdf_texture_baker')]
    for module in modules:
        del sys.modules[module]

if __name__ == "__main__":
    register()