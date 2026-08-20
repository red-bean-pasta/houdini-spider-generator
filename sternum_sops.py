import math
from enum import StrEnum, auto

import hou

from hom_helper import fill_face, points_by_id, set_id, get_parent, get_float_parm, add_id_attr, affix_id


class ID(StrEnum):
    STERNUMRIM = auto()
    STERNUMMIDDLE = auto()
    STERNUMSPINE = auto()

def sternumrim(i: int) -> str:
    return affix_id(ID.STERNUMRIM, i)
def sternummiddle(i: int) -> str:
    return affix_id(ID.STERNUMMIDDLE, i)
def sternumspine(i: int) -> str:
    return affix_id(ID.STERNUMSPINE, i)


def left_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    control = parent.node("CONTROL")
    assert control

    ratio_x = get_float_parm(parent, "width_length_ratiox")
    ratio_y = get_float_parm(parent, "width_length_ratioy")
    ratio_z = get_float_parm(parent, "width_length_ratioz")
    angle = math.radians(get_float_parm(control, "leg_angle"))
    w = get_float_parm(control, "half_width")

    forward_height = w / ratio_x * ratio_y
    back_half = w / ratio_x * ratio_z
    length = math.sqrt(back_half * back_half + w * w) / (2.0 * math.sin(angle / 2.0))
    top_width = w * get_float_parm(parent, "top_width_ratio")

    p0 = hou.Vector3(0.0, 0.0, -forward_height)
    p1 = hou.Vector3(top_width, 0.0, -forward_height)
    p3 = hou.Vector3(w, 0.0, 0.0)
    p5 = hou.Vector3(0.0, 0.0, back_half)

    p3_p5_p4 = (math.pi - angle) / 2.0
    o_p3_p5 = math.atan2(back_half, w)
    o_p3_p4 = p3_p5_p4 + o_p3_p5
    p4 = p3 + length * hou.Vector3(-math.cos(o_p3_p4), 0.0, math.sin(o_p3_p4))

    p1_p3_x = p3[0] - p1[0]
    p1_p3_z = p3[2] - p1[2]
    p1_p3_length = math.sqrt(p1_p3_x * p1_p3_x + p1_p3_z * p1_p3_z)

    midpoint_x = (p1[0] + p3[0]) / 2.0
    midpoint_z = (p1[2] + p3[2]) / 2.0
    midpoint_p2 = math.sqrt(length * length - p1_p3_length * p1_p3_length / 4.0)

    p2 = hou.Vector3(
        midpoint_x + p1_p3_z / p1_p3_length * midpoint_p2,
        0.0,
        midpoint_z - p1_p3_x / p1_p3_length * midpoint_p2,
    )

    points = []
    for position in (p0, p1, p2, p3, p4, p5):
        point = geo.createPoint()
        point.setPosition(position)
        points.append(point)


def add_midpoints(node: hou.SopNode) -> None:
    geo = node.geometry()
    primitives = geo.prims()
    assert len(primitives) == 1

    primitive = primitives[0]
    original = list(primitive.points())
    assert len(original) >= 2

    points: list[hou.Point] = []
    for index in range(len(original) - 1):
        points.append(original[index])
        if index == 0:
            continue
        a = original[index].position()
        b = original[index + 1].position()
        midpoint = geo.createPoint()
        midpoint.setPosition((a + b) / 2.0)
        points.append(midpoint)
    points.append(original[-1])


def add_point_ids(node: hou.SopNode) -> None:
    geo = node.geometry()
    primitives = geo.prims(); assert len(primitives) == 2

    add_id_attr(geo)
    right_points = list(primitives[0].points())
    left_points = list(primitives[1].points())

    set_id([right_points[0]], [sternumrim(0)])

    for index in range(1, len(right_points)):
        point_id = (
            sternumrim((index + 1) // 2)
            if index % 2
            else sternummiddle(index // 2)
        )
        set_id([right_points[index]], [point_id])

    for index in range(1, len(left_points) - 1):
        # The mirrored primitive runs from sternumrim5 back toward sternumrim0.
        id_index = (len(left_points) - index) // 2
        point_id = (
            sternummiddle(-id_index)
            if index % 2
            else sternumrim(-id_index)
        )
        set_id([left_points[index]], [point_id])


def add_center_spine(node: hou.SopNode) -> None:
    input_node = node.inputs()[0]; assert input_node
    source_geo = input_node.geometry()
    primitives = source_geo.prims(); assert primitives

    right_points = list(primitives[0].points())
    positions = [point.position() for point in right_points[2:-1]]

    geo = node.geometry()
    geo.clear()
    add_id_attr(geo)

    spine_points: list[hou.Point] = []
    for position in positions:
        point = geo.createPoint()
        point.setPosition(hou.Vector3(0.0, 0.0, position[2]))
        spine_points.append(point)

    ids = [sternumspine(index) for index in range(1, len(spine_points) + 1)]
    set_id(spine_points, ids)


def descend_sternum_spine(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    control = parent.node("CONTROL")
    if control is None:
        raise hou.NodeError("Expected CONTROL node")

    depth = get_float_parm(control, "half_width") * get_float_parm(parent, "width_depth_ratio")
    points = points_by_id(geo)

    top = points[sternumrim(0)].position()
    middle = points[sternumrim(3)].position()
    bottom = points[sternumrim(5)].position()

    upper_span = abs(middle[2] - top[2])
    lower_span = abs(bottom[2] - middle[2])
    assert upper_span != 0.0 and lower_span != 0.0
    for point_id, point in points.items():
        if not point_id.startswith(ID.STERNUMSPINE):
            continue
        position = point.position()
        if position[2] <= middle[2]:
            y = -abs(position[2] - top[2]) / upper_span * depth
        else:
            y = -abs(bottom[2] - position[2]) / lower_span * depth
        point.setPosition((position[0], y, position[2]))


def build_sternum_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    sort_by_z = lambda point: -point.position().z()
    center = sorted(
        (point for point in geo.points() if point.position().x() == 0),
        key=sort_by_z,
    )
    right = sorted(
        (point for point in geo.points() if point.position().x() > 0),
        key=sort_by_z,
    )
    left = sorted(
        (point for point in geo.points() if point.position().x() < 0),
        key=sort_by_z,
    )
    for index in range(len(center) - 2):
        fill_face(geo, [center[index], right[index], right[index + 1], center[index + 1]])
        fill_face(geo, [center[index], center[index + 1], left[index + 1], left[index]])
    fill_face(geo, [center[-2], right[-1], center[-1], left[-1]])