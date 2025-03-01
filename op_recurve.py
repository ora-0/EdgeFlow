import math
import bpy
import blf
import bmesh
import mathutils
from itertools import pairwise, chain

class RecurveOP(bpy.types.Operator):
    bl_idname = "mesh.recurve"
    bl_label = "Recurve"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "description"

    resolution = 3

    def execute(self, context):
        self.report({'INFO'}, f"Recurve operation started {self.resolution}")
        context.window_manager.modal_handler_add(self)

        self.obj = context.active_object
        self.bm = bmesh.from_edit_mesh(self.obj.data)

        selected_edges = [e for e in self.bm.edges if e.select]
        if len(selected_edges) == 0:
            return {'FINISHED'}

        bpy.ops.ed.undo_push(message="Recurve")

        endpoint_edges = []
        for edge in selected_edges:
            linked_edges = chain(edge.verts[0].link_edges, edge.verts[1].link_edges)

            count = sum(linked_edge.select for linked_edge in linked_edges)
            # less than 4 because the edge itself is included twice (from both verts)
            if count < 4:
                endpoint_edges.append(edge)
                # currently we only need one, so break
                break

        starting_edge = endpoint_edges[0] if len(endpoint_edges) > 0 else selected_edges[0]
        self.edge_loop, self.is_cyclic = find_edge_loop(starting_edge, selected_edges)
        verts = verts_of_edge_loop(self.edge_loop)
        self.intial_points = [vert.co.copy() for vert in verts]
        self.inital_vert_positions = { vert.index: vert.co.copy().freeze() for vert in verts }

        curve_data = bpy.data.curves.new(name="RecurveCurve", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.resolution_u = 12

        self.curve = curve_data.splines.new('BEZIER')
        self.curve_obj = bpy.data.objects.new("RecurveCurveObj", curve_data)
        bpy.context.collection.objects.link(self.curve_obj)
        self.curve_obj.location = self.obj.location

        bpy.context.view_layer.objects.active = self.curve_obj
        bpy.ops.object.mode_set(mode='EDIT')

        self.update_curve_with_resolution()
        self.map_onto_spline()

        return {'RUNNING_MODAL'}

    def update_curve_with_resolution(self):
        self.curve_obj.data.splines.clear()

        self.curve = self.curve_obj.data.splines.new('BEZIER')
        self.curve.bezier_points.add(self.resolution - 1)
        self.curve.use_cyclic_u = self.is_cyclic

        knot_coords = points_along_linear_spline(self.intial_points, self.is_cyclic, self.resolution)
        for point, knot_co in zip(self.curve.bezier_points, knot_coords):
            point.co = knot_co
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'


    state = 'CHOOSING_RESOLUTION'
    def modal(self, context, event):
        if self.state == 'CHOOSING_RESOLUTION':
            return self.choose_resolution(event)
        elif self.state == 'RECURVE':
            return self.recurve(event)

    def restore(self):
        for vert_index, vert_co in self.inital_vert_positions.items():
            self.bm.verts[vert_index].co = vert_co
        bmesh.update_edit_mesh(self.obj.data)
    
    def recurve(self, event):
        if event.type in {'ESC'}:
            self.restore()

            bpy.context.view_layer.objects.active = self.obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.data.curves.remove(self.curve_obj.data)
            self.bm.free()
            return {'CANCELLED'}
        elif event.type in {'RET', 'TAB'}:
            self.map_onto_spline()
            bpy.context.view_layer.objects.active = self.obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.data.curves.remove(self.curve_obj.data)
            self.bm.free()
            return {'FINISHED'}
        elif event.type in {'MOUSEMOVE', 'LEFTMOUSE'}:
            self.map_onto_spline()
            self.update = True
            return {'PASS_THROUGH'}
        else:
            return {'PASS_THROUGH'}
    
        return {'FINISHED'}

    def choose_resolution(self, event):
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.restore()
            bpy.context.view_layer.objects.active = self.obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.data.curves.remove(self.curve_obj.data)
            return {'CANCELLED'}
        elif event.type in {'RET', 'LEFTMOUSE'}:
            self.state = 'RECURVE'
            return {'RUNNING_MODAL'}
        elif event.type in {'WHEELUPMOUSE', 'NUMPAD_PLUS', 'EQUAL'} and event.value == 'PRESS':
            self.resolution += 1
            self.update_curve_with_resolution()
            self.map_onto_spline()
            return {'RUNNING_MODAL'}
        elif event.type in {'WHEELDOWNMOUSE','NUMPAD_MINUS', 'MINUS'} and event.value == 'PRESS':
            minimum = 3 if self.is_cyclic else 2
            self.resolution = max(self.resolution - 1, minimum)
            self.update_curve_with_resolution()
            self.map_onto_spline()
            return {'RUNNING_MODAL'}
        else:
            return {'PASS_THROUGH'}


    def bezier_to_linear_spline(self, resolution):
        points = []
        curve = self.curve_obj.data.splines[0]
        for point_a, point_b in pairwise(curve.bezier_points):
            points.extend(mathutils.geometry.interpolate_bezier(point_a.co, point_a.handle_right, point_b.handle_left, point_b.co, resolution))
        
        if self.is_cyclic:
            point_a = curve.bezier_points[-1]
            point_b = curve.bezier_points[0]
            points.extend(mathutils.geometry.interpolate_bezier(point_a.co, point_a.handle_right, point_b.handle_left, point_b.co, resolution))
        return points


    def map_onto_spline(self):
        points = self.bezier_to_linear_spline(12)
        points = points_along_linear_spline(points, False, len(self.edge_loop) + 1)
        verts = verts_of_edge_loop(self.edge_loop)

        for vert, point in zip(verts, points):
            vert.co = point
        bmesh.update_edit_mesh(self.obj.data)
        

def verts_of_edge_loop(edge_loop):
    edge = edge_loop[0]
    edge_2 = edge_loop[1]
    previous_vert = starting_vert = edge.verts[0] if edge.verts[0] not in edge_2.verts else edge.verts[1]

    verts = [starting_vert]
    for edge in edge_loop:
        vert = edge.other_vert(previous_vert)
        verts.append(vert)
        previous_vert = vert

    return verts


def points_along_linear_spline(points, is_cyclic, resolution) -> list[mathutils.Vector]:
    lengths = [math.dist(a, b) for a, b in pairwise(points)]
    total_length = sum(lengths) 
    length_per_segment = total_length / (resolution - 1) if not is_cyclic else total_length / resolution

    spaced_points = [points[0]]
    traversed_length = 0

    for (prev_point, point), length in zip(pairwise(points), lengths):
        # the variable names are getting out of hand
        length_with_this_edge = traversed_length + length 
        if length_with_this_edge >= length_per_segment:
            number_of_points_that_fits = math.floor(length_with_this_edge / length_per_segment)

            # add the first point
            length_before_bezier_point = length_per_segment - traversed_length
            spaced_points.append(prev_point.lerp(point, (1 / length) * length_before_bezier_point))

            # ...then the rest
            for _ in range(number_of_points_that_fits - 1):
                length_before_bezier_point += length_per_segment 
                spaced_points.append(prev_point.lerp(point, (1 / length) * length_before_bezier_point))

            # the bit that's left over
            traversed_length = length - length_before_bezier_point  
        else:
            traversed_length += length

    # account for floating point misses (not sure if this is needed)
    if len(spaced_points) != resolution:
        spaced_points.append(points[-1])

    return spaced_points


# returns edges in first return parameter, and if it is cyclic in the second return parameter
def find_edge_loop(starting_edge, selected_edges) -> tuple[list, bool]:
    visited_verts = set()

    def find_connected_edges(edge, edges, depth=0):
        connected = [edge]
        depth += 1

        # find edge on one side
        if edge.verts[0].index not in visited_verts:
            visited_verts.add(edge.verts[0].index)
            for e in edges:
                if edge.verts[0] in e.verts and edge.index != e.index:
                    connected.extend(find_connected_edges(e, selected_edges, depth))
                    break
        
        # find edge on other side
        if edge.verts[1].index not in visited_verts:
            visited_verts.add(edge.verts[1].index)
            for e in edges:
                if edge.verts[1] in e.verts and edge.index != e.index:
                    connected.extend(find_connected_edges(e, selected_edges, depth))
                    break
            
        return connected

    edge_loop = find_connected_edges(starting_edge, selected_edges)
    # when the loop is cyclic, the first edge will be counted twice, so we will need to account for that
    # (this is because the walk is depth first)
    if edge_loop[0] == edge_loop[-1]:
        edge_loop.pop()
        return edge_loop, True

    return edge_loop, False


DEFAULT_FONT = 0
def draw_resolution_text(operation, context):
    height_twelveth = context.region.height / 12
    width_tweltveth = context.region.width / 12

    blf.position(0, width_tweltveth * 7, height_twelveth * 2, 0)
    blf.size(0, 50.0)
    blf.draw(0, f"resolution: {operation.resolution}")