# bsdf_texture_baker/properties.py

import bpy
from bpy.types import PropertyGroup
from bpy.props import IntProperty, StringProperty, BoolProperty

class AutoBakeProperties(PropertyGroup):
    texture_size: IntProperty(
        name="Texture Size",
        description="Size of the baked textures (square)",
        default=1024,
        min=64,
        max=8192,
        subtype='PIXEL'
    )
    output_folder: StringProperty(
        name="Output Folder",
        description="Folder to save baked textures",
        default="//baked_maps/",
        subtype='DIR_PATH'
    )
    subfolder_for_size: BoolProperty(name="Create subfolder for size", default=True)
    bake_diffuse: BoolProperty(name="Diffuse", default=True)
    bake_roughness: BoolProperty(name="Roughness", default=True)
    bake_normal: BoolProperty(name="Normal", default=True)
    bake_ao: BoolProperty(name="AO", default=True)