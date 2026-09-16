import math

import hou

from houkit.noder import get_control, get_parent
from houkit.parameterizer import get_parms
from .attributes import sternummiddle, sternumrim, sternumspine
from ..helper import add_id_attr, replace_points, set_point_id


def left_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)

    front_ratio, back_ratio = params.front_back_length_ratios
    angle = math.radians(control_params.posterior_outline_angle)
    w = control_params.half_width

    forward_height = w * front_ratio
    back_half = w * back_ratio
    back_length = math.sqrt(back_half * back_half + w * w) / (2.0 * math.sin(angle / 2.0))
    top_width = w * params.front_width_ratio

    p0 = hou.Vector3(0.0, 0.0, -forward_height)
    p1 = hou.Vector3(top_width, 0.0, -forward_height)
    p3 = hou.Vector3(w, 0.0, 0.0)
    p5 = hou.Vector3(0.0, 0.0, back_half)

    p3_p5_p4 = (math.pi - angle) / 2.0
    o_p3_p5 = math.atan2(back_half, w)
    o_p3_p4 = p3_p5_p4 + o_p3_p5
    p4 = p3 + back_length * hou.Vector3(-math.cos(o_p3_p4), 0.0, math.sin(o_p3_p4))

    p1_p3_x = p3[0] - p1[0]
    p1_p3_z = p3[2] - p1[2]
    p1_p3_length = math.sqrt(p1_p3_x * p1_p3_x + p1_p3_z * p1_p3_z)
    front_length = p1_p3_length / (2.0 * math.sin(angle / 2.0))

    midpoint_x = (p1[0] + p3[0]) / 2.0
    midpoint_z = (p1[2] + p3[2]) / 2.0
    midpoint_p2 = math.sqrt(front_length * front_length - p1_p3_length * p1_p3_length / 4.0)

    p2 = hou.Vector3(
        midpoint_x + p1_p3_z / p1_p3_length * midpoint_p2,
        0.0,
        midpoint_z - p1_p3_x / p1_p3_length * midpoint_p2,
    )

    for position in (p0, p1, p2, p3, p4, p5):
        point = geo.createPoint()
        point.setPosition(position)


def add_midpoints(node: hou.SopNode) -> None:
    geo = node.geometry()
    positions = [point.position() for point in geo.points()]
    assert len(positions) >= 2

    result: list[hou.Vector3] = []
    for index, position in enumerate(positions):
        result.append(position)
        if 0 < index < len(positions) - 1:
            result.append((position + positions[index + 1]) / 2.0)
    geo.clear()
    for position in result:
        point = geo.createPoint()
        point.setPosition(position)


def add_point_ids(node: hou.SopNode) -> None:
    geo = node.geometry()
    right_points = ordered_points([point for point in geo.points() if point.position()[0] >= 0.0])
    left_points = ordered_points([point for point in geo.points() if point.position()[0] < 0.0])
    assert len(right_points) == 10
    assert len(left_points) == len(right_points) - 2

    add_id_attr(geo)

    set_point_id(right_points[0], sternumrim(0))

    for index in range(1, len(right_points)):
        point_id = (
            sternumrim((index + 1) // 2)
            if index % 2
            else sternummiddle(index // 2)
        )
        set_point_id(right_points[index], point_id)

    for index, point in enumerate(left_points):
        id_index = index // 2 + 1
        point_id = (
            sternumrim(-id_index)
            if index % 2 == 0
            else sternummiddle(-id_index)
        )
        set_point_id(point, point_id)

def ordered_points(points: list[hou.Point]) -> list[hou.Point]:
    return sorted(points, key=lambda point: (point.position()[2], point.position()[0]))


def add_center_spine(node: hou.SopNode) -> None:
    input_node = node.inputs()[0]; assert input_node is not None
    source_geo = input_node.geometry()
    right_points = ordered_points([point for point in source_geo.points() if point.position()[0] >= 0.0])
    assert len(right_points) == 10
    positions = [point.position() for point in right_points[2:-1]]

    geo = node.geometry()
    replace_points(
        geo,
        [
            (sternumspine(index), hou.Vector3(0.0, 0.0, position[2]))
            for index, position in enumerate(positions, start=1)
        ],
    )


