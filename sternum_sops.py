import math
from enum import StrEnum, auto

import hou

from utilities.common import (
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_params,
    get_parent,
    is_equal_approx,
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

    params = get_params(parent, use_tuple=False)
    control_params = get_params(control, use_tuple=False)

    front_ratio, back_ratio = params.width_length_ratio
    angle = math.radians(control_params.leg_angle)
    w = control_params.half_width

    forward_height = w * front_ratio
    back_half = w * back_ratio
    length = math.sqrt(back_half * back_half + w * w) / (2.0 * math.sin(angle / 2.0))
    top_width = w * params.top_width_ratio

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

    params = get_params(parent, use_tuple=False)
    control_params = get_params(control, use_tuple=False)

    depth = control_params.half_width * params.width_depth_ratio
    power = params.spine_descend_handle
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
            y = _get_eased_depth(position[2], top[2], middle[2], 0.0, -depth, power)
        else:
            y = _get_eased_depth(position[2], bottom[2], middle[2], 0.0, -depth, power)
        point.setPosition((position[0], y, position[2]))

def _get_eased_depth(
    x: float,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    power: float,
) -> float:
    span = x1 - x0
    assert span != 0.0, "Expected non-zero span for easing interpolation"
    t = max(0.0, min(1.0, (x - x0) / span))
    return y0 + (y1 - y0) * (t ** power)


def build_sternum_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    t = get_float_parm(parent, "spine_loop_ratio")
    assert 0.0 < t <= 1.0

    sort_by_z = lambda p: p.position().z()
    center = sorted((p for p in geo.points() if p.position().x() == 0), key=sort_by_z)
    right = sorted((p for p in geo.points() if p.position().x() > 0), key=sort_by_z)
    left = sorted((p for p in geo.points() if p.position().x() < 0), key=sort_by_z)

    if is_equal_approx(t, 1.0):
        _build_base_faces(geo, center, right, left)
    else:
        _build_subdivided_spine_faces(geo, center, right, left, t)

def _build_base_faces(
    geo: hou.Geometry,
    center: list[hou.Point],
    right: list[hou.Point],
    left: list[hou.Point],
) -> None:
    for index in range(len(center) - 2):
        fill_face(geo, [center[index], right[index], right[index + 1], center[index + 1]], True)
        fill_face(geo, [center[index], center[index + 1], left[index + 1], left[index]], True)
    fill_face(geo, [center[-2], right[-1], center[-1], left[-1]], True)

def _build_subdivided_spine_faces(
    geo: hou.Geometry,
    center: list[hou.Point],
    right: list[hou.Point],
    left: list[hou.Point],
    t: float,
) -> None:
    def _lerp(p1: hou.Point, p2: hou.Point, ratio: float) -> hou.Point:
        pt = geo.createPoint()
        pt.setPosition(p1.position() * (1.0 - ratio) + p2.position() * ratio)
        return pt

    loop_r = [_lerp(c, r, t) for c, r in zip(center[1:-1], right[1:])]
    loop_l = [_lerp(c, l, t) for c, l in zip(center[1:-1], left[1:])]
    loop_c = _lerp(center[-2], center[-1], t)

    m1 = _lerp(center[1], center[0], t)
    m2_r = _lerp(center[1], right[0], t)
    m3_r = loop_r[0]
    m2_l = _lerp(center[1], left[0], t)
    m3_l = loop_l[0]

    # Front 3 faces (Right)
    fill_face(geo, [center[1], m1, m2_r, m3_r], True)
    fill_face(geo, [m3_r, m2_r, right[0], right[1]], True)
    fill_face(geo, [m2_r, m1, center[0], right[0]], True)

    # Front 3 faces (Left)
    fill_face(geo, [center[1], m3_l, m2_l, m1], True)
    fill_face(geo, [m3_l, left[1], left[0], m2_l], True)
    fill_face(geo, [m2_l, left[0], center[0], m1], True)

    # Side quads along spokes
    for i in range(len(loop_r) - 1):
        fill_face(geo, [center[i + 1], loop_r[i], loop_r[i + 1], center[i + 2]], True)
        fill_face(geo, [loop_r[i], right[i + 1], right[i + 2], loop_r[i + 1]], True)
        fill_face(geo, [center[i + 1], center[i + 2], loop_l[i + 1], loop_l[i]], True)
        fill_face(geo, [loop_l[i], loop_l[i + 1], left[i + 2], left[i + 1]], True)

    # Rear diamond quads
    fill_face(geo, [center[-2], loop_r[-1], loop_c, loop_l[-1]], True)
    fill_face(geo, [loop_r[-1], right[-1], center[-1], loop_c], True)
    fill_face(geo, [loop_l[-1], loop_c, center[-1], left[-1]], True)


def add_prim_regions(node: hou.SopNode) -> None:
    geo = node.geometry()

    add_prim_attr(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", "sternum")


def prepare_outer_boundary(node: hou.SopNode) -> None:
    geo = node.geometry()
    grp = geo.createEdgeGroup("tmp_outer_boundary")
    for edge in geo.globEdges("*"):
        if len(edge.prims()) == 1:
            grp.add(edge)


def extrude_sternum_loop(parent: hou.SopNode, input_node: hou.SopNode) -> hou.SopNode:
    extrude = parent.createNode("polyextrude", "extrude_sternum_loop")
    extrude.setInput(0, input_node)
    extrude.parm("group").set("tmp_outer_boundary")
    extrude.parm("dist").setExpression('ch("../membrane_ratio") * ch("../CONTROL/half_width")')
    extrude.parm("outputside").set(1)

    classified = sopify(parent, extrude, _classify_sternum_loop)
    adjusted = sopify(parent, classified, adjust_midpoints_after_extrusion)
    cleanup = sopify(parent, adjusted, _cleanup_loop_attributes)
    return cleanup

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
