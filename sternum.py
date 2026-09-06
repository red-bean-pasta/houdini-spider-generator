import math
from enum import StrEnum, auto

import hou

from helper import (
    add_id_attr,
    affix_id,
    point_from_geo,
    points_by_id,
    set_points_id,
)
from utilities.common import (
    add_float_param,
    add_prim_attr,
    fill_face,
    get_control,
    get_float_parm,
    get_params,
    get_parent,
    is_equal_approx,
)
from utilities.identifying import deduplicate_point_attributes
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import outset


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


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    sternum = add_reloadable_subnet(cephalothorax, "sternum")
    _add_parameters(sternum)
    _add_controls(sternum)

    half = sopify(sternum, None, _left_half)
    midpoints = sopify(sternum, half, _add_midpoints)

    mirror = add_mirror(sternum, "right_mirror", midpoints, (1, 0, 0), True, False)
    point_ids = sopify(sternum, mirror, _add_point_ids)

    spine = sopify(sternum, point_ids, _add_center_spine)

    merge = add_merge(sternum, "merge_boundary_and_spine", point_ids, spine)
    fuse = add_fuse(sternum, "fuse_center_points", merge)

    depth = sopify(sternum, fuse, _descend_sternum_spine)
    faces = sopify(sternum, depth, _build_sternum_faces)
    regions = sopify(sternum, faces, _add_prim_regions)
    buffered = sopify(sternum, regions, _outset_sternum_loop)

    _ = add_output(sternum, "OUT_STERNUM", buffered)
    sternum.layoutChildren()
    return sternum


def _add_parameters(sternum: hou.SopNode) -> None:
    add_float_param(
        sternum,
        "width_length_ratio",
        2,
        (2.0, 1.825),
        (0.0, None),
        help="Front (anterior) length ratio and back (posterior) length ratio relative to half-width",
    )
    add_float_param(
        sternum,
        "top_width_ratio",
        1,
        0.5,
        (0.0, 1.0),
    )
    add_float_param(
        sternum,
        "width_depth_ratio",
        1,
        0.5,
        (0.0, None),
    )
    add_float_param(
        sternum,
        "spine_descend_handle",
        1,
        0.75,
        (0.0, None),
    )
    add_float_param(
        sternum,
        "spine_loop_ratio",
        1,
        1.0,
        (0.0, 1.0),
        help="Ratio along radial spokes from spine to rim for the intermediate spine loop",
    )
    add_float_param(
        sternum,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_param(
        control,
        "half_width",
        1,
        100.0,
    )
    add_float_param(
        control,
        "leg_angle",
        1,
        165.0,
        (0.0, 180.0),
    )
    return control


def _left_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    params = get_params(parent, use_tuple=False)
    control_params = get_params(get_control(node), use_tuple=False)

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


def _add_midpoints(node: hou.SopNode) -> None:
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


def _add_point_ids(node: hou.SopNode) -> None:
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

def _ordered_points(points: list[hou.Point]) -> list[hou.Point]:
    return sorted(points, key=lambda point: (point.position()[2], point.position()[0]))


def _add_center_spine(node: hou.SopNode) -> None:
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


def _descend_sternum_spine(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    params = get_params(parent, use_tuple=False)
    control_params = get_params(get_control(node), use_tuple=False)

    depth = control_params.half_width * params.width_depth_ratio
    power = params.spine_descend_handle
    points = points_by_id(geo)

    top, middle, bottom = point_from_geo(
        geo,
        sternumrim(0),
        sternumrim(3),
        sternumrim(5),
    )
    top = top.position()
    middle = middle.position()
    bottom = bottom.position()

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


def _build_sternum_faces(node: hou.SopNode) -> None:
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


def _add_prim_regions(node: hou.SopNode) -> None:
    geo = node.geometry()

    add_prim_attr(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", "sternum")


def _outset_sternum_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    params = get_params(parent, use_tuple=False)
    control_params = get_params(get_control(node), use_tuple=False)

    membrane_width = params.membrane_ratio * control_params.half_width
    support_dist = membrane_width
    dist = membrane_width
    dy = membrane_width

    _add_sternum_loop(geo, support_dist)
    intermediate_points = _add_sternum_loop(geo, dist)
    _add_sternum_loop(geo, dist)

    _adjust_midpoints_after_outset(geo)

    for pt in intermediate_points:
        pos = pt.position()
        pt.setPosition((pos[0], pos[1] + dy, pos[2]))

def _add_sternum_loop(geo: hou.Geometry, dist: float) -> list[hou.Point]:
    outset(list(geo.prims()), dist, use_ratio=False)
    deduplicate_point_attributes(geo, "id", (ID.STERNUMSPINE,), keep_first=True)
    deduplicate_point_attributes(geo, "id", outer_loop_ids(), keep_first=False)
    return [
        pt for pt in geo.points()
        if pt.attribValue("id").startswith(outer_loop_ids())
    ]

def _adjust_midpoints_after_outset(geo: hou.Geometry) -> None:
    points = points_by_id(geo)
    rim1, rim_neg1 = point_from_geo(geo, sternumrim(1), sternumrim(-1))
    p0 = (rim1.position() + rim_neg1.position()) / 2.0
    (rim0,) = point_from_geo(geo, sternumrim(0))
    rim0.setPosition(hou.Vector3(0.0, p0[1], p0[2]))
    if sternumrim(5) in points:
        (rim5,) = point_from_geo(geo, sternumrim(5))
        p5 = rim5.position()
        rim5.setPosition(hou.Vector3(0.0, p5[1], p5[2]))
    for side in (1, -1):
        for i in range(1, 5):
            start, end = point_from_geo(
                geo,
                sternumrim(side * i),
                sternumrim(5) if i == 4 else sternumrim(side * (i + 1)),
            )
            start = start.position()
            end = end.position()
            midpoint = (start + end) / 2.0
            (middle_point,) = point_from_geo(geo, sternummiddle(side * i))
            middle_point.setPosition(midpoint)
