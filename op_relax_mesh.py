import bpy
from bpy.props import FloatProperty, IntProperty

class RelaxMeshOP(bpy.types.Operator):
    bl_idname = "mesh.relax_mesh"
    bl_label = "Relax Mesh"
    bl_description = "Relaxes the mesh while keeping the form"
    bl_options = {'REGISTER', 'UNDO'}

    strength : FloatProperty(name="Strength", default=1.0, description="Controls the strength of the operation")
    repeat : IntProperty(name="Repeat", default=1, min=1, soft_max=100, description="Repeat the operation multiple times")

    def execute(self, context):
        bpy.ops.ed.undo_push(message="Relax Mesh")

        bpy.ops.object.mode_set(mode='SCULPT')
        bpy.ops.paint.mask_flood_fill(mode='VALUE', value=1)

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.hide(unselected=True)

        bpy.ops.object.mode_set(mode='SCULPT')
        bpy.ops.paint.mask_flood_fill(mode='VALUE', value=0)
        bpy.ops.paint.hide_show_all(action='SHOW')

        bpy.ops.sculpt.mesh_filter(
            strength=self.strength,
            iteration_count=self.repeat,
            type='RELAX'
        )

        bpy.ops.paint.mask_flood_fill(mode='VALUE', value=0)
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

    def invoke(self, context, event):
        if event and not event.alt:
            self.strength = 1.0
            self.repeat = 1

        return self.execute(context)