import math
from enum import StrEnum, auto

import hou

from utilities.common import (
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_parent,
    remove_groups,
)
from utilities.helper import (
    add_id_attr,
    affix_id,
    points_by_id,
    set_points_id,
)
from utilities.identifying import deduplicate_point_attributes
from utilities.nodes import sopify


class ID(StrEnum):
    STERNUMRIM = auto()
    STERNUMMIDDLE = auto()
    STERNUMSPINE = auto()

def sternumrim(*i: int | str) -> str:
    return affix_id(ID.STERNUMRIM, *i)
def sternummiddle(*i: int | str) -> str:
    return affix_id(ID.STERNUMMIDDLE, *i)
def sternumspine(*i: int | str) -> str:
    return affix_id(ID.STERNUMSPINE, *i)

def outer_loop_ids() -> tuple[str, str]:
    return ID.STERNUMRIM, ID.STERNUMMIDDLE


def _ordered_points(points: list[hou.Point]) -> list[hou.Point]:
    return sorted(points, key=lambda point: (point.position()[2], point.position()[0]))


def left_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    control = parent.node("CONTROL"); assert control is not None

    front_ratio = get_float_parm(parent, "width_length_ratiox")
    back_ratio = get_float_parm(parent, "width_length_ratioy")
    angle = math.radians(get_float_parm(control, "leg_angle"))
    w = get_float_parm(control, "half_width")

    forward_height = w * front_ratio
    back_half = w * back_ratio
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
    right_points = _ordered_points([point for point in geo.points() if point.position()[0] >= 0.0])
    left_points = _ordered_points([point for point in geo.points() if point.position()[0] < 0.0])
    assert len(right_points) == 10
    assert len(left_points) == len(right_points) - 2

    add_id_attr(geo)

    set_points_id([right_points[0]], [sternumrim(0)])

    for index in range(1, len(right_points)):
        point_id = (
            sternumrim((index + 1) // 2)
            if index % 2
            else sternummiddle(index // 2)
        )
        set_points_id([right_points[index]], [point_id])

    for index, point in enumerate(left_points):
        id_index = index // 2 + 1
        point_id = (
            sternumrim(-id_index)
            if index % 2 == 0
            else sternummiddle(-id_index)
        )
        set_points_id([point], [point_id])


def add_center_spine(node: hou.SopNode) -> None:
    input_node = node.inputs()[0]; assert input_node is not None
    source_geo = input_node.geometry()
    right_points = _ordered_points([point for point in source_geo.points() if point.position()[0] >= 0.0])
    assert len(right_points) == 10
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
    set_points_id(spine_points, ids)


def descend_sternum_spine(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    control = parent.node("CONTROL")
    assert control is not None, "Expected CONTROL node"

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
    sort_by_z = lambda point: point.position().z()
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
        fill_face(geo, [center[index], right[index], right[index + 1], center[index + 1]], True)
        fill_face(geo, [center[index], center[index + 1], left[index + 1], left[index]], True)
    fill_face(geo, [center[-2], right[-1], center[-1], left[-1]], True)


def add_prim_regions(node: hou.SopNode) -> None:
    geo = node.geometry()

    add_prim_attr(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", "sternum")


def extrude_sternum_loop(parent: hou.SopNode, faces: hou.SopNode) -> hou.SopNode:
    boundary_prepared = sopify(parent, faces, _prepare_outer_boundary)

    extrude = parent.createNode("polyextrude", "extrude_sternum_loop")
    extrude.setInput(0, boundary_prepared)
    extrude.parm("group").set("tmp_outer_boundary")
    extrude.parm("dist").setExpression('ch("../membrane_ratio") * ch("../CONTROL/half_width")')
    extrude.parm("outputside").set(1)

    classified = sopify(parent, extrude, _classify_sternum_loop)
    adjusted = sopify(parent, classified, adjust_midpoints_after_extrusion)
    cleanup = sopify(parent, adjusted, _cleanup_loop_attributes)
    return cleanup

def _prepare_outer_boundary(node: hou.SopNode) -> None:
    geo = node.geometry()
    grp = geo.createEdgeGroup("tmp_outer_boundary")
    outer_ids = outer_loop_ids()
    for edge in geo.globEdges("*"):
        if all(pt.stringAttribValue("id").startswith(outer_ids) for pt in edge.points()):
            grp.add(edge)

def _classify_sternum_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    for prim in geo.prims():
        if not prim.stringAttribValue("region"):
            prim.setAttribValue("region", "sternum")
    deduplicate_point_attributes(geo, "id", outer_loop_ids(), keep_first=False)

def adjust_midpoints_after_extrusion(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    points[sternumrim(0)].setPosition((points[sternumrim(1)].position() + points[sternumrim(-1)].position()) / 2.0)
    for side in (1, -1):
        for i in range(1, 5):
            start = points[sternumrim(side * i)].position()
            end = points[sternumrim(5) if i == 4 else sternumrim(side * (i + 1))].position()
            midpoint = (start + end) / 2.0
            points[sternummiddle(side * i)].setPosition(midpoint)

def _cleanup_loop_attributes(node: hou.SopNode) -> None:
    geo = node.geometry()
    remove_groups(geo, edge_groups="tmp_outer_boundary")
