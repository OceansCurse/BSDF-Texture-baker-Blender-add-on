# bsdf_texture_baker/panel.py
import bpy
from bpy.types import Panel

class AUTOBAKE_PT_Panel(Panel):
    bl_label = "Auto Bake Maps"
    bl_idname = "AUTOBAKE_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Auto Bake'

    def draw(self, context):
        layout = self.layout
        props = context.scene.autobake_props

        layout.label(text="Bake Settings")
        layout.prop(props, "texture_size")
        layout.prop(props, "output_folder")
        layout.prop(props, "subfolder_for_size")

        layout.label(text="Maps to Bake")
        layout.prop(props, "bake_diffuse", text="Diffuse")
        layout.prop(props, "bake_roughness")
        layout.prop(props, "bake_normal")
        layout.prop(props, "bake_ao")

        layout.operator("autobake.bake_maps", text="Bake Maps")