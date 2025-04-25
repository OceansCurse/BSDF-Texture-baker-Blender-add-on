# bsdf_texture_baker/bake_operator.py

import bpy
import os
import traceback # Import for detailed error logging
from bpy.types import Operator

class AUTOBAKE_OT_BakeMaps(Operator):
    """Bakes selected maps for the active model using its active Principled BSDF material"""
    bl_idname = "autobake.bake_maps"
    bl_label = "Bake Selected Maps"
    bl_description = "Bakes Diffuse, Roughness, Normal, and AO maps from the active object's material"
    bl_options = {'REGISTER', 'UNDO'} 

    @classmethod
    def poll(cls, context):
        # Basic check: Is there an active object?
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        # --- Get Properties from Scene (assuming they are set elsewhere by UI) ---
        # Placeholder if props don't exist:
        class MockProps:
            bake_diffuse = True
            bake_roughness = True
            bake_normal = True
            bake_ao = True
            texture_size = 1024
            output_folder = "//baked_textures" # Default to a relative path 'baked_textures' in the blend file's dir

        props = getattr(context.scene, "autobake_props", MockProps()) # Use mock props if real ones aren't registered

        print("Starting bake process...")

        # --- Validate Requirements ---
        validRequirements = self.validateRequirements(context)
        if validRequirements['status'] != {'FINISHED'}:
            # Report should have been called in validateRequirements
            return validRequirements['status']
        print("Requirements validated successfully.")

        # Get validated objects
        model = validRequirements['model']
        original_material = validRequirements['material'] # The material to bake from

        # --- Store Original Settings ---
        original_engine = context.scene.render.engine
        original_render_samples = context.scene.cycles.samples # Use Render samples for 4.x+
        original_use_selected_to_active = context.scene.render.bake.use_selected_to_active
        original_active_object = context.view_layer.objects.active
        original_selected_objects = context.selected_objects[:] # Store list copy

        # --- Apply Bake Settings ---
        try:
            context.scene.render.engine = 'CYCLES'
            # Set sample count for baking
            bake_sample_count = 32 # Or props.bake_samples if made a property option later
            context.scene.cycles.samples = bake_sample_count
            print(f"Set Cycles Render Samples to {bake_sample_count} for baking.")

            # We are baking the active object's own material
            context.scene.render.bake.use_selected_to_active = False

            # Ensure the correct object is selected and active
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = model
            model.select_set(True)

            # Prepare output path
            output_path = bpy.path.abspath(props.output_folder)
            if props.subfolder_for_size:
                output_path = os.path.join(output_path, f"{props.texture_size}")
                
            if not os.path.exists(output_path):
                print(f"Creating output directory: {output_path}")
                os.makedirs(output_path)

            # Ensure the original material is assigned and active on the object
            if model.active_material != original_material:
                found_material = False
                for i, mat_slot in enumerate(model.material_slots):
                    if mat_slot.material == original_material:
                        model.active_material_index = i
                        found_material = True
                        print(f"Set active material index to {i} for '{original_material.name}'")
                        break
                if not found_material:
                    # This should ideally not happen if validation passed
                    self.report({'ERROR'}, f"Original material '{original_material.name}' not found in object slots.")
                    raise RuntimeError(f"Material '{original_material.name}' missing from object.")

            if not model.active_material or model.active_material != original_material:
                 self.report({'ERROR'}, f"Could not set original material '{original_material.name}' active on model.")
                 raise RuntimeError("Failed to set active material.")

            # --- Bake Maps ---
            map_types = [
                ('Diffuse', props.bake_diffuse, self.bake_diffuse),
                ('Roughness', props.bake_roughness, self.bake_roughness),
                ('Normal', props.bake_normal, self.bake_normal),
                ('AO', props.bake_ao, self.bake_ao),
            ]

            bake_successful = True
            baked_images = [] # Keep track of images to save/remove

            for map_type, should_bake, bake_method in map_types:
                if not should_bake:
                    continue

                image = None # Ensure image is defined in this scope
                try:
                    # Create image
                    image_name = f"{model.name}_{map_type}"
                    # Ensure unique name if script run multiple times without reloading blend
                    if image_name in bpy.data.images:
                        bpy.data.images.remove(bpy.data.images[image_name])

                    image = self.create_image(image_name, props.texture_size, map_type)
                    baked_images.append(image) # Add to list for later processing

                    # Call the specific bake method - pass original material
                    print(f"\n--- Starting Bake: {map_type} ---")
                    bake_method(image, map_type, original_material)
                    print(f"--- Finished Bake: {map_type} ---")

                    # Optional: Check if the Normal map is a solid color
                    if map_type == "Normal":
                        if self.is_image_solid_color(image):
                             self.report({'WARNING'}, f"Normal map '{image.name}' may be solid color. Check geometry, normals, or material's Normal input.")

                except Exception as e:
                    self.report({'ERROR'}, f"Failed during {map_type} bake: {str(e)}")
                    traceback.print_exc() # Print detailed error to console
                    if image and image.name in bpy.data.images: # Check if image exists before removing
                        bpy.data.images.remove(image)
                        if image in baked_images:
                            baked_images.remove(image) # Remove from our tracking list
                    bake_successful = False
                    break # Stop baking further maps if one fails

            # --- Save Baked Images ---
            if bake_successful and baked_images:
                print("\nSaving baked images...")
                for image in baked_images:
                     if image.name in bpy.data.images: # Check it still exists
                        image_filepath = os.path.join(output_path, f"{image.name}.png")
                        image.filepath_raw = image_filepath
                        image.file_format = 'PNG'
                        # Color space should be set correctly during creation/baking
                        # but double check before saving Normal map
                        if image.name.endswith("_Normal"):
                             if image.colorspace_settings.name != 'Non-Color':
                                 print(f"Warning: Correcting colorspace to Non-Color for {image.name} before saving.")
                                 image.colorspace_settings.name = 'Non-Color'

                        try:
                            image.save()
                            print(f"Saved: {image_filepath}")
                        except Exception as e:
                             self.report({'ERROR'}, f"Failed to save image {image.name} to {image_filepath}: {e}")
                             traceback.print_exc()
                             bake_successful = False # Mark as failed if saving fails
                     else:
                        print(f"Warning: Image '{image.name}' not found for saving (already removed?).")


        except Exception as e:
             # Catch errors during setup phase
             self.report({'ERROR'}, f"Error during bake setup: {str(e)}")
             traceback.print_exc()
             bake_successful = False

        finally:
            # --- Clean up Blender Image Data ---
            print("Cleaning up baked images from Blender session...")
            for image in baked_images:
                if image and image.name in bpy.data.images:
                     try:
                         print(f"Removed image '{image.name}' from .blend data.")
                         bpy.data.images.remove(image)
                     except Exception as e:
                         print(f"Warning: Could not remove image {image}: {e}")


            # --- Restore Original Settings ---
            print("Restoring original settings...")
            context.scene.render.engine = original_engine
            context.scene.cycles.samples = original_render_samples # Restore render samples
            context.scene.render.bake.use_selected_to_active = original_use_selected_to_active
            print(f"Restored Render Engine to '{original_engine}', Samples to {original_render_samples}.")

            # Reselect originally selected objects and activate the original active object
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selected_objects:
                if obj and obj.name in context.view_layer.objects: # Check if object still exists
                    obj.select_set(True)
            if original_active_object and original_active_object.name in context.view_layer.objects:
                context.view_layer.objects.active = original_active_object
            print("Restored selection and active object.")


            # --- Final Report ---
            if bake_successful:
                self.report({'INFO'}, f"Baking process finished. Maps saved to: {output_path}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Baking process failed or was interrupted. Check console/log.")
                return {'CANCELLED'}

    # --- Helper Functions ---
    def validateRequirements(self, context):
        """Checks if the active object and material are suitable for baking."""
        # ... (previous checks for active_object, type, selection) ...
        if not context.active_object:
             self.report({'ERROR'}, "No active object selected.")
             return {'status': {'CANCELLED'}}

        model = context.active_object
        if model.type != 'MESH':
             self.report({'ERROR'}, f"Active object '{model.name}' is not a Mesh.")
             return {'status': {'CANCELLED'}}

        if len(context.selected_objects) > 1 :
             self.report({'WARNING'}, "More than one object selected. Baking only the active object.")
             # Allow proceeding, as active_object is the focus

        # --- CORRECTED UV MAP CHECK ---
        # Ensure UV map exists
        if not model.data.uv_layers:
            self.report({'ERROR'}, f"Model '{model.name}' has no UV maps.")
            return {'status': {'CANCELLED'}}

        # Find the UV layer marked for rendering
        render_uv_layer = None
        for layer in model.data.uv_layers:
            if layer.active_render:
                render_uv_layer = layer
                break # Found the one used for rendering

        # If no layer is marked for rendering, try to set the first one
        if not render_uv_layer:
            if len(model.data.uv_layers) > 0:
                first_layer = model.data.uv_layers[0]
                try:
                    # Set the first layer to be active for rendering
                    first_layer.active_render = True
                    render_uv_layer = first_layer
                    self.report({'WARNING'}, f"No UV map was active for render on '{model.name}'. Automatically set '{render_uv_layer.name}' as active for render.")
                except Exception as e:
                    # This might happen if the layer is invalid somehow
                    self.report({'ERROR'}, f"Failed to set active_render on UV layer '{first_layer.name}': {e}")
                    traceback.print_exc()
                    return {'status': {'CANCELLED'}}
            else:
                # This case should be caught by the `if not model.data.uv_layers:` check, but for safety:
                self.report({'ERROR'}, f"Model '{model.name}' has uv_layers collection but it is empty.")
                return {'status': {'CANCELLED'}}

        # Also ensure *an* active UV layer is selected in general (for UV editor display, etc.)
        # This doesn't strictly need to be the 'render_uv_layer', but it's often helpful.
        if not model.data.uv_layers.active:
            try:
                # Try to activate the render layer, otherwise default to the first layer (index 0)
                model.data.uv_layers.active = render_uv_layer
            except Exception:
                 try:
                     # Fallback if setting directly fails
                     model.data.uv_layers.active_index = 0
                 except IndexError:
                      self.report({'ERROR'}, f"Failed to set any active UV layer for '{model.name}'.")
                      return {'status': {'CANCELLED'}}
            print(f"Ensured active UV layer is: {model.data.uv_layers.active.name}")

        # Report the layer that will be used for rendering/baking
        print(f"Using UV Map (marked active for render): {render_uv_layer.name}")
        # --- END CORRECTED UV MAP CHECK ---


        # ... (rest of the validation: material checks, principled node check) ...
        if not model.active_material:
             self.report({'ERROR'}, f"Model '{model.name}' has no active material.")
             return {'status': {'CANCELLED'}}

        material = model.active_material
        if not material.use_nodes:
            self.report({'ERROR'}, f"Active material '{material.name}' on '{model.name}' must have nodes enabled.")
            return {'status': {'CANCELLED'}}

        principled_node = None
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                principled_node = node
            # Keep the output node check simple or remove if not strictly needed
            # if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            #      output_node = node
        
        if not principled_node:
            self.report({'ERROR'}, f"Active material '{material.name}' must contain a Principled BSDF node.")
            return {'status': {'CANCELLED'}}

        print(f"Validated: Model='{model.name}', Material='{material.name}', Principled='{principled_node.name}', Render UV='{render_uv_layer.name}'")


        return {
            'status': {'FINISHED'},
            'model': model,
            'material': material,
            'principled_node': principled_node
            # Removed render_uv_layer from here as it's not directly used later,
            # we just need to ensure one *is* set for render.
        }
        
    def create_image(self, name, size, map_type):
        """Creates a new image buffer for baking with appropriate settings."""
        print(f"Creating image: {name} ({size}x{size})")
        # Ensure size is int
        size = int(size)
        image = bpy.data.images.new(name=name, width=size, height=size, alpha=True)

        # Set color space based on map type (Crucial!)
        if map_type == 'Normal':
            # Normals need non-color data and 32-bit float for precision if possible
            image.generated_color = (0.5, 0.5, 1.0, 1.0) # Neutral normal
            image.colorspace_settings.name = 'Non-Color'
            image.use_generated_float = True # Use 32-bit float for normals
            print(f"Image '{name}': Set colorspace=Non-Color, use_float=True")
        elif map_type in ['Roughness', 'Metallic', 'AO']:
             image.generated_color = (0.5, 0.5, 0.5, 1.0) # Mid-grey for data maps
             image.colorspace_settings.name = 'Non-Color' # Data maps are linear
             print(f"Image '{name}': Set colorspace=Non-Color")
        else: # Diffuse, Emission etc.
             image.generated_color = (0.0, 0.0, 0.0, 1.0) # Black
             image.colorspace_settings.name = 'sRGB' # Color maps are usually sRGB
             print(f"Image '{name}': Set colorspace=sRGB")

        return image

    def is_image_solid_color(self, image):
        """Checks if all pixels in the image have roughly the same color."""
        print("Checking if image is solid color...")
        print(f"Image '{image.name}': Size={image.size}, Channels={image.channels}, Has Data={image.has_data}")
        width, height = image.size
        print(f"Image '{image.name}': Width={width}, Height={height}")
        
        if not image or not image.has_data or not image.pixels or width == 0 or height == 0:
            print(f"Image '{image.name}' has no pixel data to check.")
            return False # Cannot determine or empty

        try:
            pixels = image.pixels[:] # Get a copy of the pixel data
            if not pixels:
                print(f"Image '{image.name}' pixels list is empty.")
                return True # Empty image is technically solid?

            channels = image.channels
            if channels == 0: return True

            first_pixel_color = pixels[0:channels]
            tolerance = 0.01 # Allow slight floating point variations

            # Compare every pixel's color to the first one
            for i in range(channels, len(pixels), channels):
                current_pixel_color = pixels[i:i + channels]
                if len(current_pixel_color) != channels: continue # Should not happen

                # Compare channel by channel with tolerance
                is_different = False
                for j in range(channels):
                    if abs(first_pixel_color[j] - current_pixel_color[j]) > tolerance:
                        is_different = True
                        break # This pixel is different
                if is_different:
                     # print(f"Debug: Pixel {i//channels} differs. First={first_pixel_color}, Current={current_pixel_color}")
                     return False # Found a different pixel

            print(f"Image '{image.name}' appears to be a solid color ({first_pixel_color}).")
            return True # All pixels matched the first one within tolerance
        except Exception as e:
             print(f"Error checking if image '{image.name}' is solid color: {e}")
             traceback.print_exc()
             return False # Assume not solid if check fails

    def add_bake_image_node(self, nodes, image):
        """Adds, selects, and activates an Image Texture node for baking."""
        bake_node_name = "BakeTargetNode"
        # Remove any pre-existing nodes with the same name
        for node in nodes:
             if node.type == 'TEX_IMAGE' and node.name == bake_node_name:
                 print(f"Removing pre-existing node '{bake_node_name}'")
                 nodes.remove(node)

        image_node = nodes.new("ShaderNodeTexImage")
        image_node.name = bake_node_name
        image_node.label = f"Bake Target ({image.name})" # Set label for clarity in UI
        image_node.image = image
        # Important: Set interpolation to closest for data maps to avoid blurring pixels
        # Or leave as linear? Linear is default. Maybe check map_type here if needed.
        # image_node.interpolation = 'Closest'
        image_node.select = True
        nodes.active = image_node # Make it the active node
        print(f"Added/Activated Image Texture node '{image_node.name}' for image '{image.name}'")
        return image_node

    def remove_bake_image_node(self, nodes):
         """Removes the specifically named bake target node."""
         bake_node_name = "BakeTargetNode"
         node_to_remove = nodes.get(bake_node_name)
         if node_to_remove:
             print(f"Removing bake target node '{node_to_remove.name}'")
             nodes.remove(node_to_remove)
         # else:
             # print(f"Bake target node '{bake_node_name}' not found for removal.")

    # --- Specific Bake Methods ---
    # Note: Passing 'self' to these methods now

    def bake_diffuse(self, image, map_type, material):
        """Bakes the Diffuse Color map."""
        nodes = material.node_tree.nodes
        image_node = None
        try:
            image_node = self.add_bake_image_node(nodes, image) # Use helper

            # Configure Diffuse bake settings
            bake_type = 'DIFFUSE'
            bpy.context.scene.render.bake.use_pass_direct = False   # Don't include direct light
            bpy.context.scene.render.bake.use_pass_indirect = False # Don't include indirect light
            bpy.context.scene.render.bake.use_pass_color = True     # Only bake the color info

            # Perform bake
            print(f"Baking {map_type} with type {bake_type} (Color only)")
            bpy.ops.object.bake(type=bake_type)

        finally:
            # Clean up the added image node
            if image_node:
                self.remove_bake_image_node(nodes) # Use helper

    def bake_normal(self, image, map_type, material):
        """Bakes the Tangent Space Normal map."""
        nodes = material.node_tree.nodes
        image_node = None
        try:
            # Ensure color space is correct *before* adding node/baking
            if image.colorspace_settings.name != 'Non-Color':
                 print(f"Warning: Setting colorspace to Non-Color for Normal map '{image.name}'")
                 image.colorspace_settings.name = 'Non-Color'
            if not image.use_generated_float:
                 print(f"Warning: Enabling 32-bit float for Normal map '{image.name}'")
                 image.use_generated_float = True

            image_node = self.add_bake_image_node(nodes, image)

            # Configure Normal bake settings
            bake_type = 'NORMAL'
            bpy.context.scene.render.bake.normal_space = 'TANGENT' # Standard for game engines
            bpy.context.scene.render.bake.normal_r = 'POS_X'
            bpy.context.scene.render.bake.normal_g = 'POS_Y'
            bpy.context.scene.render.bake.normal_b = 'POS_Z'

            # Perform bake
            print(f"Baking {map_type} with type {bake_type} (Tangent Space)")
            bpy.ops.object.bake(type=bake_type)

        finally:
            # Clean up the added image node
            if image_node:
                self.remove_bake_image_node(nodes)

    def bake_roughness(self, image, map_type, material):
        """Bakes the Roughness map."""
        nodes = material.node_tree.nodes
        image_node = None
        try:
             # Ensure non-color data
            if image.colorspace_settings.name != 'Non-Color':
                 print(f"Warning: Setting colorspace to Non-Color for Roughness map '{image.name}'")
                 image.colorspace_settings.name = 'Non-Color'

            image_node = self.add_bake_image_node(nodes, image)

            # Configure Roughness bake settings
            bake_type = 'ROUGHNESS'

            # Perform bake
            print(f"Baking {map_type} with type {bake_type}")
            bpy.ops.object.bake(type=bake_type)

        finally:
            # Clean up the added image node
            if image_node:
                self.remove_bake_image_node(nodes)

    def bake_ao(self, image, map_type, material):
        """Bakes the Ambient Occlusion map."""
        nodes = material.node_tree.nodes
        image_node = None
        try:
             # Ensure non-color data
            if image.colorspace_settings.name != 'Non-Color':
                 print(f"Warning: Setting colorspace to Non-Color for AO map '{image.name}'")
                 image.colorspace_settings.name = 'Non-Color'

            image_node = self.add_bake_image_node(nodes, image)

            # Configure AO bake settings
            bake_type = 'AO'
            # Optional: AO settings in World properties might influence this bake
            # e.g., context.scene.world.light_settings.distance for AO distance

            # Perform bake
            print(f"Baking {map_type} with type {bake_type}")
            bpy.ops.object.bake(type=bake_type)

        finally:
            # Clean up the added image node
            if image_node:
                 self.remove_bake_image_node(nodes)
