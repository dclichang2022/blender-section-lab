bl_info = {
    "name": "立体截面实验室",
    "author": "Kimi",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D 视图 > N 面板 > 截面实验",
    "description": "用真实平面剖切实体并显示截线",
    "category": "3D View",
}

import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


SCENE_NAME = "立体截面实验室"
MODEL_NAME = "SECTION_当前模型"
FILL_NAME = "SECTION_橙色截面"
LINE_NAME = "SECTION_红色截线"
PLANE_NAME = "SECTION_刀面"
CAMERA_NAME = "SECTION_预览相机"
N = 128
UPDATING = False

MODEL_SPECS = {
    "original": ("本题：空心圆锥＋圆台", 1.15, 0.95, 0.65),
    "cone": ("实心圆锥", 0.85, 0.65, 0.65),
    "cylinder": ("实心圆柱", 1.00, 0.55, 0.70),
    "frustum": ("实心圆台", 0.75, 0.60, 0.55),
    "tube": ("空心圆柱", 1.00, 0.90, 0.70),
    "cube": ("正方体（对照）", 0.00, 0.60, 0.25),
}


def model_items(self, context):
    return [(key, spec[0], "") for key, spec in MODEL_SPECS.items()]


def ring(radius, z, n=N):
    return [
        Vector((radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n), z))
        for i in range(n)
    ]


def mesh_from_faces(name, faces, material):
    bm = bmesh.new()
    vertices = {}
    vertex_list = []

    def vertex_index(co):
        key = tuple(round(v, 7) for v in co)
        if key not in vertices:
            vertices[key] = len(vertex_list)
            vertex_list.append(Vector(co))
        return vertices[key]

    indexed_faces = [[vertex_index(co) for co in face] for face in faces]
    bmverts = [bm.verts.new(co) for co in vertex_list]
    bm.verts.ensure_lookup_table()
    for face in indexed_faces:
        if len(set(face)) >= 3:
            try:
                bm.faces.new([bmverts[i] for i in face])
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = abs(polygon.normal.z) < 0.98
    return mesh


def cone_faces(radius, z_base, z_apex, cap=True):
    base = ring(radius, z_base)
    apex = Vector((0, 0, z_apex))
    center = Vector((0, 0, z_base))
    faces = []
    for i in range(N):
        j = (i + 1) % N
        faces.append((base[i], base[j], apex))
        if cap:
            faces.append((center, base[j], base[i]))
    return faces


def frustum_faces(r_bottom, z_bottom, r_top, z_top, bottom=True, top=True):
    lower = ring(r_bottom, z_bottom)
    upper = ring(r_top, z_top)
    faces = []
    for i in range(N):
        j = (i + 1) % N
        faces.append((lower[i], lower[j], upper[j], upper[i]))
        if bottom:
            faces.append((Vector((0, 0, z_bottom)), lower[j], lower[i]))
        if top:
            faces.append((Vector((0, 0, z_top)), upper[i], upper[j]))
    return faces


def hollow_cylinder_faces(r_outer, r_inner, z_bottom, z_top):
    outer_lower = ring(r_outer, z_bottom)
    outer_upper = ring(r_outer, z_top)
    inner_lower = ring(r_inner, z_bottom)
    inner_upper = ring(r_inner, z_top)
    faces = []
    for i in range(N):
        j = (i + 1) % N
        faces.append((outer_lower[i], outer_lower[j], outer_upper[j], outer_upper[i]))
        faces.append((inner_lower[j], inner_lower[i], inner_upper[i], inner_upper[j]))
        faces.append((outer_upper[i], outer_upper[j], inner_upper[j], inner_upper[i]))
        faces.append((outer_lower[j], outer_lower[i], inner_lower[i], inner_lower[j]))
    return faces


def cube_faces(size=1.8):
    s = size / 2
    v = [
        Vector((-s, -s, -s)), Vector((s, -s, -s)), Vector((s, s, -s)), Vector((-s, s, -s)),
        Vector((-s, -s, s)), Vector((s, -s, s)), Vector((s, s, s)), Vector((-s, s, s)),
    ]
    return [
        (v[0], v[3], v[2], v[1]), (v[4], v[5], v[6], v[7]),
        (v[0], v[1], v[5], v[4]), (v[1], v[2], v[6], v[5]),
        (v[2], v[3], v[7], v[6]), (v[3], v[0], v[4], v[7]),
    ]


def source_faces(key):
    if key == "original":
        return (
            cone_faces(1.35, 0.8, 2.4, cap=False)
            + frustum_faces(0.75, -1.0, 1.35, 0.8, bottom=True, top=False)
            + cone_faces(0.65, 0.8, 1.65, cap=True)
        )
    if key == "cone":
        return cone_faces(1.25, 0.0, 2.0)
    if key == "cylinder":
        return frustum_faces(1.1, 0.0, 1.1, 2.0)
    if key == "frustum":
        return frustum_faces(1.25, 0.0, 0.65, 1.6)
    if key == "tube":
        return hollow_cylinder_faces(1.15, 0.52, 0.0, 2.0)
    if key == "cube":
        return cube_faces()
    raise ValueError(key)


def create_material(name, color):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
    return material


def link_object(scene, name, data):
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.hide_select = True
    return obj


def normal_from_angles(scene):
    tilt = math.radians(scene.section_tilt)
    azimuth = math.radians(scene.section_azimuth)
    return Vector((
        math.sin(tilt) * math.cos(azimuth),
        math.sin(tilt) * math.sin(azimuth),
        math.cos(tilt),
    ))


def plane_basis(normal):
    if abs(normal.z) > 0.95:
        u = Vector((1, 0, 0))
    else:
        u = Vector((0, 0, 1)).cross(normal).normalized()
    v = normal.cross(u).normalized()
    return u, v


def plane_matrix(normal, offset):
    u, v = plane_basis(normal)
    basis = Matrix((u, v, normal)).transposed()
    matrix = basis.to_4x4()
    matrix.translation = normal * offset
    return matrix


def extract_loops(cut_edges):
    unused = set(cut_edges)
    adjacency = {}
    for edge in unused:
        a, b = edge.verts
        adjacency.setdefault(a, []).append(edge)
        adjacency.setdefault(b, []).append(edge)
    closed = []
    opened = []
    while unused:
        first = next(iter(unused))
        unused.remove(first)
        start = first.verts[0]
        current = first.verts[1]
        points = [start.co.copy(), current.co.copy()]
        is_closed = False
        while current != start:
            candidates = [edge for edge in adjacency.get(current, []) if edge in unused]
            if not candidates:
                break
            edge = candidates[0]
            unused.remove(edge)
            a, b = edge.verts
            current = b if a == current else a
            points.append(current.co.copy())
        if current == start:
            is_closed = True
            points.pop()
        if len(points) >= 3:
            (closed if is_closed else opened).append(points)
    return closed, opened


def signed_area(loop):
    return 0.5 * sum(
        loop[i][0] * loop[(i + 1) % len(loop)][1]
        - loop[(i + 1) % len(loop)][0] * loop[i][1]
        for i in range(len(loop))
    )


def inside_loop(point, loop):
    x, y = point
    inside = False
    j = len(loop) - 1
    for i in range(len(loop)):
        xi, yi = loop[i]
        xj, yj = loop[j]
        if (yi > y) != (yj > y):
            crossing = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < crossing:
                inside = not inside
        j = i
    return inside


def oriented_loops(loops2d):
    result = []
    for i, original in enumerate(loops2d):
        loop = list(original)
        depth = sum(
            1 for j, other in enumerate(loops2d)
            if i != j and inside_loop(loop[0], other)
        )
        area = signed_area(loop)
        if (depth % 2 == 0 and area < 0) or (depth % 2 == 1 and area > 0):
            loop.reverse()
        result.append(loop)
    return result


def replace_splines(curve, loops, cyclic):
    curve.splines.clear()
    for loop in loops:
        spline = curve.splines.new("POLY")
        spline.points.add(len(loop) - 1)
        for point, co in zip(spline.points, loop):
            point.co = (co[0], co[1], 0.0, 1.0)
        spline.use_cyclic_u = cyclic


def description(scene, loop_count):
    key = scene.section_model
    tilt = scene.section_tilt
    offset = scene.section_offset
    if key == "original" and abs(tilt) < 0.01:
        if 0.8 < offset < 1.65:
            return [
                "对应 B：外圆锥截出大圆，空心圆锥截出小圆。",
                "橙色材料是圆环；把刀升到 1.65 以上，内圆消失。",
            ]
        if 1.65 <= offset < 2.4:
            return ["刀已高于空腔顶点，只切到实体：截面是实心圆。"]
        if -1.0 < offset < 0.8:
            return ["这里只切到下方圆台：截面是实心圆。", "圆环只出现在空心圆锥所在的高度。"]
        return ["这是接合处或体外的临界位置。", "把刀移回 0.8～1.65，可看到最清楚的圆环。"]
    if key == "original" and abs(tilt - 90) < 0.01 and abs(offset) < 0.01:
        return ["过轴竖切：外轮廓五边形，中间有三角形空白孔。", "A 项没有画出这个孔。点“正视截面”观察。"]
    if key == "original" and abs(tilt - 90) < 0.01:
        return ["偏心竖切避开了空腔，但圆锥顶部变成曲线。", "它不再是 A 项那种尖顶直线。点“正视截面”观察。"]
    if key == "cylinder" and abs(tilt - 90) < 0.01 and loop_count:
        return ["圆柱的母线彼此平行，竖切可得到矩形。", "这就是圆柱与圆锥、圆台的关键差别。"]
    if key == "cone" and abs(tilt - 90) < 0.01 and abs(offset) < 0.01:
        return ["带平底面的实心圆锥，过顶点竖切是三角形。", "本题还须考虑下方圆台和内部空腔。"]
    if key == "frustum" and abs(tilt - 90) < 0.01 and abs(offset) < 0.01:
        return ["圆台过轴竖切是梯形，两腰不平行。", "它不能像圆柱那样得到矩形。"]
    if key == "tube" and abs(tilt - 90) < 0.01 and abs(offset) < 0.01:
        return ["空心圆柱过轴竖切：两个分离的矩形。", "中间贯通的孔没有材料。"]
    if loop_count >= 2:
        return [f"当前有 {loop_count} 个闭合轮廓。", "孔洞或分离部分都要画，不能只画最外圈。"]
    if loop_count == 1:
        return ["当前只有一个闭合外轮廓。", "慢慢改变刀的位置和倾角，观察直边与曲线。"]
    return ["刀目前没有切到实体。", "移动“刀的位置”，让刀面与模型相交。"]


def update_section(scene):
    global UPDATING
    if UPDATING or not scene.get("section_built"):
        return
    UPDATING = True
    try:
        model = bpy.data.objects[MODEL_NAME]
        source = bpy.data.meshes[f"SOURCE_{scene.section_model}"]
        old_mesh = model.data
        mesh = source.copy()
        model.data = mesh
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)

        normal = normal_from_angles(scene)
        offset = scene.section_offset
        origin = normal * offset
        bm = bmesh.new()
        bm.from_mesh(mesh)
        result = bmesh.ops.bisect_plane(
            bm,
            geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            dist=0.00001,
            plane_co=origin,
            plane_no=normal,
            clear_outer=scene.section_cutaway,
            clear_inner=False,
        )
        cut_edges = [element for element in result["geom_cut"] if isinstance(element, bmesh.types.BMEdge)]
        loops3d, opened3d = extract_loops(cut_edges)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        for polygon in mesh.polygons:
            polygon.use_smooth = abs(polygon.normal.z) < 0.98

        u, v = plane_basis(normal)
        loops2d = [[(point.dot(u), point.dot(v)) for point in loop] for loop in loops3d]
        opened2d = [[(point.dot(u), point.dot(v)) for point in loop] for loop in opened3d]
        fill_obj = bpy.data.objects[FILL_NAME]
        line_obj = bpy.data.objects[LINE_NAME]
        matrix = plane_matrix(normal, offset)
        fill_obj.matrix_world = matrix
        line_obj.matrix_world = matrix
        replace_splines(fill_obj.data, oriented_loops(loops2d), True)
        replace_splines(line_obj.data, loops2d + opened2d, True)
        bpy.data.objects[PLANE_NAME].matrix_world = matrix
        bpy.data.objects[PLANE_NAME].hide_render = not scene.section_show_plane
        bpy.data.objects[PLANE_NAME].hide_set(not scene.section_show_plane)
        scene["section_loop_count"] = len(loops2d)
        scene["section_info"] = "\n".join(description(scene, len(loops2d)))
        bpy.context.view_layer.update()
    finally:
        UPDATING = False


def property_changed(self, context):
    update_section(context.scene)


def model_changed(self, context):
    global UPDATING
    if UPDATING:
        return
    UPDATING = True
    spec = MODEL_SPECS[self.section_model]
    self.section_offset = spec[1]
    self.section_tilt = 0
    self.section_azimuth = 0
    UPDATING = False
    update_section(self)


class SECTION_OT_preset(bpy.types.Operator):
    bl_idname = "section.preset"
    bl_label = "切换剖切预设"
    bl_options = {"REGISTER", "UNDO"}

    preset: bpy.props.StringProperty()

    def execute(self, context):
        global UPDATING
        scene = context.scene
        spec = MODEL_SPECS[scene.section_model]
        if self.preset == "horizontal":
            values = (spec[1], 0, 0)
        elif self.preset == "vertical":
            values = (0.0, 90, 0)
        elif self.preset == "eccentric":
            values = (spec[2], 90, 0)
        else:
            values = (spec[3], 35, 25)
        UPDATING = True
        scene.section_offset = values[0]
        scene.section_tilt = values[1]
        scene.section_azimuth = values[2]
        UPDATING = False
        update_section(scene)
        return {"FINISHED"}


class SECTION_OT_view(bpy.types.Operator):
    bl_idname = "section.view"
    bl_label = "切换观察视角"

    mode: bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        normal = normal_from_angles(scene)
        origin = normal * scene.section_offset
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                region = space.region_3d
                region.view_perspective = "ORTHO"
                if self.mode == "section":
                    region.view_rotation = plane_matrix(normal, scene.section_offset).to_quaternion()
                    region.view_location = origin
                    region.view_distance = 4.2
                else:
                    region.view_rotation = Matrix.Rotation(math.radians(62), 3, "X").to_quaternion() @ Matrix.Rotation(math.radians(-32), 3, "Z").to_quaternion()
                    region.view_location = Vector((0, 0, 0.65))
                    region.view_distance = 6.4
        return {"FINISHED"}


class SECTION_OT_build(bpy.types.Operator):
    bl_idname = "section.build"
    bl_label = "创建截面实验室"

    def execute(self, context):
        build_scene()
        return {"FINISHED"}


class SECTION_PT_lab(bpy.types.Panel):
    bl_label = "一刀平面 · 截面实验"
    bl_idname = "SECTION_PT_lab"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "截面实验"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if not scene.get("section_built"):
            layout.label(text="在一个独立场景中创建模型，不影响当前场景。")
            layout.operator("section.build", text="创建截面实验室", icon="MOD_BEVEL")
            return
        layout.prop(scene, "section_model", text="模型")
        layout.separator()
        row = layout.row(align=True)
        for value, label in (("horizontal", "①水平"), ("vertical", "②过轴")):
            row.operator("section.preset", text=label).preset = value
        row = layout.row(align=True)
        for value, label in (("eccentric", "③偏心"), ("oblique", "④斜切")):
            row.operator("section.preset", text=label).preset = value
        layout.separator()
        layout.prop(scene, "section_offset", text="刀的位置", slider=True)
        layout.prop(scene, "section_tilt", text="刀的倾角", slider=True)
        layout.prop(scene, "section_azimuth", text="水平转向", slider=True)
        layout.prop(scene, "section_cutaway", text="剖开显示（去掉刀正侧）")
        layout.prop(scene, "section_show_plane", text="显示网格刀面")
        layout.separator()
        row = layout.row(align=True)
        row.operator("section.view", text="正视截面").mode = "section"
        row.operator("section.view", text="立体斜视").mode = "solid"
        box = layout.box()
        for line in scene.get("section_info", "正在生成截面……").split("\n"):
            box.label(text=line)
        layout.label(text="左键拖动旋转，滚轮缩放。", icon="MOUSE_MOVE")


CLASSES = (SECTION_OT_preset, SECTION_OT_view, SECTION_OT_build, SECTION_PT_lab)


def register():
    for cls in CLASSES:
        old = getattr(bpy.types, cls.__name__, None)
        if old:
            bpy.utils.unregister_class(old)
        bpy.utils.register_class(cls)
    bpy.types.Scene.section_model = bpy.props.EnumProperty(
        name="模型", items=model_items, update=model_changed
    )
    bpy.types.Scene.section_offset = bpy.props.FloatProperty(
        name="刀的位置", default=1.15, min=-2.0, max=3.0, precision=2, update=property_changed
    )
    bpy.types.Scene.section_tilt = bpy.props.FloatProperty(
        name="刀的倾角", default=0, min=0, max=90, precision=0, update=property_changed
    )
    bpy.types.Scene.section_azimuth = bpy.props.FloatProperty(
        name="水平转向", default=0, min=0, max=180, precision=0, update=property_changed
    )
    bpy.types.Scene.section_cutaway = bpy.props.BoolProperty(
        name="剖开显示", default=True, update=property_changed
    )
    bpy.types.Scene.section_show_plane = bpy.props.BoolProperty(
        name="显示刀面", default=True, update=property_changed
    )


def unregister():
    for name in (
        "section_model", "section_offset", "section_tilt",
        "section_azimuth", "section_cutaway", "section_show_plane",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        old = getattr(bpy.types, cls.__name__, None)
        if old:
            bpy.utils.unregister_class(old)


def create_section_curve(name, material, filled):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "2D" if filled else "3D"
    curve.resolution_u = 1
    curve.materials.append(material)
    if filled:
        curve.fill_mode = "BOTH"
    else:
        curve.bevel_depth = 0.012
        curve.bevel_resolution = 2
    return curve


def create_plane_grid(material):
    mesh = bpy.data.meshes.new(PLANE_NAME)
    extent = 2.2
    vertices = []
    edges = []
    for i in range(-4, 5):
        p = i * 0.5
        index = len(vertices)
        vertices.extend([(-extent, p, 0), (extent, p, 0), (p, -extent, 0), (p, extent, 0)])
        edges.extend([(index, index + 1), (index + 2, index + 3)])
    mesh.from_pydata(vertices, edges, [])
    mesh.materials.append(material)
    return mesh


def configure_scene(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studiolight_rotate_z = 0.4
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.2
    scene.display.shading.curvature_valley_factor = 1.0
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.055, 0.055, 0.055)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.shading.type = "SOLID"
                space.shading.color_type = "MATERIAL"
                space.shading.light = "STUDIO"
                space.shading.show_shadows = True
                space.shading.show_cavity = True
                space.shading.cavity_type = "BOTH"
                space.overlay.show_floor = False
                space.overlay.show_axis_x = False
                space.overlay.show_axis_y = False
                space.overlay.show_extras = False
                space.show_region_ui = True
                space.region_3d.view_distance = 6.4
                space.region_3d.view_location = Vector((0, 0, 0.65))
                space.region_3d.view_rotation = Matrix.Rotation(math.radians(62), 3, "X").to_quaternion() @ Matrix.Rotation(math.radians(-32), 3, "Z").to_quaternion()
                space.region_3d.view_perspective = "ORTHO"


def add_guide_text():
    text = bpy.data.texts.get("先看我：实验路线") or bpy.data.texts.new("先看我：实验路线")
    text.clear()
    text.write(
        "立体截面实验室\n\n"
        "1. 按 N 打开右侧栏，选择“截面实验”。\n"
        "2. 先点“①水平”：刀高 0.8～1.65 时是圆环，对应 B；高于 1.65 时内圆消失。\n"
        "3. 点“②过轴”，再点“正视截面”：外轮廓五边形，中间必须留下三角形孔。\n"
        "4. 点“③偏心”：避开空腔后，圆锥顶部变成曲线，不再是 A 的尖顶。\n"
        "5. 切换实心圆柱并过轴竖切，可看到矩形；圆锥和圆台则分别是三角形和梯形。\n"
        "6. 点“④斜切”，慢慢调三个滑块，观察曲线如何连续变化。\n\n"
        "刀的位置是平面沿法线的距离，不是刀片的动画位置。\n"
        "倾角 0° 为水平刀；90° 为竖直刀。水平转向只在倾角大于 0° 时有意义。\n"
        "橙色表示实体材料，红色表示截线，青色网格表示无限平面的局部。\n"
    )


def build_scene():
    scene = bpy.data.scenes.get(SCENE_NAME)
    if scene and scene.get("section_built"):
        bpy.context.window.scene = scene
        configure_scene(scene)
        update_section(scene)
        return scene
    if scene is None:
        scene = bpy.data.scenes.new(SCENE_NAME)
    bpy.context.window.scene = scene
    scene.world = bpy.data.worlds.new("SECTION_世界")
    model_material = create_material("SECTION_模型蓝", (0.26, 0.55, 0.82))
    fill_material = create_material("SECTION_截面橙", (1.0, 0.43, 0.08))
    line_material = create_material("SECTION_截线红", (0.85, 0.025, 0.02))
    plane_material = create_material("SECTION_刀面青", (0.03, 0.65, 0.72))
    for key in MODEL_SPECS:
        name = f"SOURCE_{key}"
        old = bpy.data.meshes.get(name)
        if old:
            bpy.data.meshes.remove(old)
        source = mesh_from_faces(name, source_faces(key), model_material)
        source.use_fake_user = True
    model = link_object(scene, MODEL_NAME, bpy.data.meshes["SOURCE_original"].copy())
    model.color = (0.26, 0.55, 0.82, 1)
    fill = link_object(scene, FILL_NAME, create_section_curve(FILL_NAME, fill_material, True))
    line = link_object(scene, LINE_NAME, create_section_curve(LINE_NAME, line_material, False))
    plane = link_object(scene, PLANE_NAME, create_plane_grid(plane_material))
    plane.display_type = "WIRE"
    camera_data = bpy.data.cameras.new(CAMERA_NAME)
    camera = link_object(scene, CAMERA_NAME, camera_data)
    camera.location = (4.5, -6.5, 4.2)
    direction = Vector((0, 0, 0.65)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 5.6
    camera.hide_set(True)
    scene.camera = camera
    scene.section_model = "original"
    scene.section_offset = 1.15
    scene.section_tilt = 0
    scene.section_azimuth = 0
    scene.section_cutaway = True
    scene.section_show_plane = True
    scene["section_built"] = True
    configure_scene(scene)
    add_guide_text()
    update_section(scene)
    return scene


def set_geometry(scene, key, normal, offset, cutaway=True):
    global UPDATING
    UPDATING = True
    scene.section_model = key
    scene.section_tilt = math.degrees(math.acos(max(-1, min(1, normal[2]))))
    scene.section_azimuth = math.degrees(math.atan2(normal[1], normal[0])) % 180
    if normal[2] < 0:
        scene.section_azimuth = 0
    scene.section_offset = offset
    scene.section_cutaway = cutaway
    UPDATING = False
    update_section(scene)


def evaluated_section_area():
    obj = bpy.data.objects[FILL_NAME]
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    area = sum(polygon.area for polygon in mesh.polygons)
    evaluated.to_mesh_clear()
    return area


def run_self_test():
    bpy.ops.section.build()
    scene = bpy.context.scene
    set_geometry(scene, "original", Vector((0, 0, 1)), 1.15)
    assert scene["section_loop_count"] == 2, "本题水平切应有两个闭合轮廓"
    outer_r = 1.35 * (2.4 - 1.15) / 1.6
    inner_r = 0.65 * (1.65 - 1.15) / 0.85
    expected = math.pi * (outer_r**2 - inner_r**2)
    area = evaluated_section_area()
    assert math.isclose(area, expected, rel_tol=0.003), f"圆环面积错误: {area}, 应为 {expected}"

    set_geometry(scene, "original", Vector((1, 0, 0)), 0.0)
    assert scene["section_loop_count"] == 2, "本题过轴竖切应有外轮廓和三角形孔"

    set_geometry(scene, "cylinder", Vector((1, 0, 0)), 0.0)
    assert scene["section_loop_count"] == 1, "圆柱过轴竖切应为单个矩形"
    area = evaluated_section_area()
    assert math.isclose(area, 4.4, rel_tol=0.001), f"圆柱矩形面积错误: {area}"

    set_geometry(scene, "cone", Vector((1, 0, 0)), 0.0)
    assert scene["section_loop_count"] == 1
    assert math.isclose(evaluated_section_area(), 2.5, rel_tol=0.001), "实心圆锥轴截面应为三角形"

    set_geometry(scene, "frustum", Vector((1, 0, 0)), 0.0)
    assert scene["section_loop_count"] == 1
    assert math.isclose(evaluated_section_area(), 3.04, rel_tol=0.001), "圆台轴截面应为梯形"

    set_geometry(scene, "tube", Vector((0, 0, 1)), 1.0)
    assert scene["section_loop_count"] == 2, "空心圆柱水平切应为圆环"
    set_geometry(scene, "tube", Vector((1, 0, 0)), 0.0)
    assert scene["section_loop_count"] == 2, "空心圆柱过轴竖切应为两个矩形"
    assert math.isclose(evaluated_section_area(), 2.52, rel_tol=0.001), "空心圆柱轴截面面积错误"

    set_geometry(scene, "cube", Vector((0, 0, 1)), 0.0)
    assert scene["section_loop_count"] == 1
    assert math.isclose(evaluated_section_area(), 3.24, rel_tol=0.001), "正方体水平截面应为正方形"

    set_geometry(scene, "original", Vector((0, 0, 1)), 1.15)
    print("SELF_TEST_OK: 圆环及孔洞面积、三角形、矩形、梯形、双矩形、正方形均通过。")


def render_preview():
    scene = build_scene()
    set_geometry(scene, "original", Vector((0, 0, 1)), 1.15)
    scene.render.filepath = str(Path(__file__).with_name("section_lab_preview.png"))
    bpy.ops.render.render(write_still=True)
    set_geometry(scene, "original", Vector((1, 0, 0)), 0.0)
    scene.render.filepath = str(Path(__file__).with_name("section_lab_vertical.png"))
    bpy.ops.render.render(write_still=True)
    set_geometry(scene, "original", Vector((0, 0, 1)), 1.15)


def main():
    register()
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--self-test" in argv:
        run_self_test()
    elif "--preview" in argv:
        render_preview()
    else:
        build_scene()
    if "--build" in argv:
        embedded = bpy.data.texts.get("section_lab_blender.py") or bpy.data.texts.new("section_lab_blender.py")
        embedded.from_string(Path(__file__).read_text(encoding="utf-8"))
        path = Path(__file__).with_name("section_lab.blend")
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        print(f"SAVED: {path}")


if __name__ == "__main__":
    main()
