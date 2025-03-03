import bpy

class ConformOp(bpy.types.Operator):
    bl_idname = "mesh.conform_op"
    bl_label = "Conform"
    bl_description = "Adds a shrinkwrap modifier to a copy of this mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')

        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return {'CANCELLED'}

        bpy.ops.object.duplicate()
        duplicate = context.active_object
        duplicate.name = obj.name + "_target"
        context.view_layer.objects.active = obj
        duplicate.hide_set(True)    

        shrinkwrap = obj.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
        shrinkwrap.target = duplicate
        shrinkwrap.wrap_method = 'TARGET_PROJECT'
        shrinkwrap.wrap_mode = 'ON_SURFACE'    

        shrinkwrap.name = "Conform Shrinkwrap"
        shrinkwrap.show_on_cage = True

        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class LatticeDeformOp(bpy.types.Operator):
    bl_idname = "mesh.lattice_deform_op"
    bl_label = "Lattice Deform"
    bl_description = "Adds a lattice around the bounding box of the selected verts"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}
        selected_verts = [v for v in obj.data.vertices if v.select]
        if not selected_verts:
            bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}

        vertex_group = obj.vertex_groups.new(name="LatticeGroup")
        vertex_group.add([v.index for v in selected_verts], 1.0, 'ADD')

        bpy.ops.object.add(type='LATTICE')
        lattice = context.active_object
        lattice.name = obj.name + "_lattice"

        min_co = [min([v.co[i] for v in selected_verts]) for i in range(3)]
        max_co = [max([v.co[i] for v in selected_verts]) for i in range(3)]
        lattice.scale = [(max_co[i] - min_co[i]) for i in range(3)]
        lattice.location = [(max_co[i] + min_co[i]) / 2 for i in range(3)]
        lattice.location += obj.location

        lattice_mod = obj.modifiers.new(name="LatticeDeform", type='LATTICE')
        lattice_mod.object = lattice

        bpy.ops.object.mode_set(mode='EDIT')
        lattice_mod.vertex_group = vertex_group.name

        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}