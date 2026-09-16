import math
from enum import StrEnum, auto

import hou

from .helper import (
    add_id_attr,
    affix_id,
    points_from_geo,
    positions_from_geo,
    points_by_id,
    set_point_id,
    sopify_chain,
    replace_points,
    set_points_id,
)
from houkit.attributer import add_prim_attrib, deduplicate_point_attribs
from houkit.geomath import is_equal_approx
from houkit.noder import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    get_control,
    get_parent,
    sopify,
)
from houkit.parameterizer import add_float_parm, get_float_parm, get_parms
from houkit.topology import fill_face, outset


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

    midpoints = sopify_chain(sternum, None, (_left_half, _add_midpoints))

    mirror = add_mirror(sternum, "right_mirror", midpoints, (1, 0, 0), True, False)
    point_ids = sopify(sternum, mirror, _add_point_ids)

    spine = sopify(sternum, point_ids, _add_center_spine)

    merge = add_merge(sternum, "merge_boundary_and_spine", point_ids, spine)
    fuse = add_fuse(sternum, "fuse_center_points", merge)

    buffered = sopify_chain(
        sternum,
        fuse,
        (_descend_sternum_spine, _build_sternum_faces, _add_prim_regions, _outset_sternum_loop),
    )

    _ = add_output(sternum, "OUT_STERNUM", buffered)
    sternum.layoutChildren()
    return sternum


def _add_parameters(sternum: hou.SopNode) -> None:
    add_float_parm(
        sternum,
        "front_back_length_ratios",
        2,
        (1.85, 1.6),
        (0.0, None),
        label="Front / Back Length",
        help="X is anterior length; Y is posterior length. Both are relative to sternum half-width.",
    )
    add_float_parm(
        sternum,
        "front_width_ratio",
        1,
        0.455,
        (0.0, 1.0),
        label="Front Width",
        help="Anterior width relative to the sternum’s widest span.",
    )
    add_float_parm(
        sternum,
        "spine_depth_ratio",
        1,
        0.25,
        (0.0, None),
        label="Spine Depth",
        help="Maximum center-spine depression relative to sternum half-width.",
    )
    add_float_parm(
        sternum,
        "spine_descent_power",
        1,
        0.75,
        (0.0, None),
        label="Spine Descent",
        help="1 is linear; lower values deepen sooner and higher values deepen later.",
    )
    add_float_parm(
        sternum,
        "spine_loop_position_ratio",
        1,
        1.0,
        (0.0, 1.0),
        label="Spine Loop Position",
        help="Position from center spine toward rim. At 1, the intermediate loop is omitted.",
    )
    add_float_parm(
        sternum,
        "membrane_ratio",
        1,
        0.02,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_parm(
        control,
        "half_width",
        1,
        100.0,
        label="Half Width",
        help="Scene-unit half-width that establishes the sternum scale.",
    )
    add_float_parm(
        control,
        "posterior_outline_angle",
        1,
        150.0,
        (0.0, 180.0),
        label="Posterior Outline Angle",
        help="Interior angle that shapes the rear sternum outline.",
    )
    return control


def _left_half(node: hou.SopNode) -> None:
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

def _ordered_points(points: list[hou.Point]) -> list[hou.Point]:
    return sorted(points, key=lambda point: (point.position()[2], point.position()[0]))


def _add_center_spine(node: hou.SopNode) -> None:
    input_node = node.inputs()[0]; assert input_node is not None
    source_geo = input_node.geometry()
    right_points = _ordered_points([point for point in source_geo.points() if point.position()[0] >= 0.0])
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


def _descend_sternum_spine(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)

    depth = control_params.half_width * params.spine_depth_ratio
    power = params.spine_descent_power
    points = points_by_id(geo)

    top, middle, bottom = positions_from_geo(
        geo,
        sternumrim(0),
        sternumrim(3),
        sternumrim(5),
    )

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
    t = get_float_parm(parent, "spine_loop_position_ratio")
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
        fill_face([center[index], right[index], right[index + 1], center[index + 1]], True)
        fill_face([center[index], center[index + 1], left[index + 1], left[index]], True)
    fill_face([center[-2], right[-1], center[-1], left[-1]], True)

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
    fill_face([center[1], m1, m2_r, m3_r], True)
    fill_face([m3_r, m2_r, right[0], right[1]], True)
    fill_face([m2_r, m1, center[0], right[0]], True)

    # Front 3 faces (Left)
    fill_face([center[1], m3_l, m2_l, m1], True)
    fill_face([m3_l, left[1], left[0], m2_l], True)
    fill_face([m2_l, left[0], center[0], m1], True)

    # Side quads along spokes
    for i in range(len(loop_r) - 1):
        fill_face([center[i + 1], loop_r[i], loop_r[i + 1], center[i + 2]], True)
        fill_face([loop_r[i], right[i + 1], right[i + 2], loop_r[i + 1]], True)
        fill_face([center[i + 1], center[i + 2], loop_l[i + 1], loop_l[i]], True)
        fill_face([loop_l[i], loop_l[i + 1], left[i + 2], left[i + 1]], True)

    # Rear diamond quads
    fill_face([center[-2], loop_r[-1], loop_c, loop_l[-1]], True)
    fill_face([loop_r[-1], right[-1], center[-1], loop_c], True)
    fill_face([loop_l[-1], loop_c, center[-1], left[-1]], True)


def _add_prim_regions(node: hou.SopNode) -> None:
    geo = node.geometry()

    add_prim_attrib(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", "sternum")


def _outset_sternum_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)

    membrane_width = params.membrane_ratio * control_params.half_width
    support_dist = membrane_width
    dist = membrane_width

    _add_sternum_loop(geo, support_dist)
    _add_sternum_loop(geo, dist)

    _adjust_midpoints_after_outset(geo)

def _add_sternum_loop(geo: hou.Geometry, dist: float) -> list[hou.Point]:
    outset(list(geo.prims()), dist, use_ratio=False)
    deduplicate_point_attribs(geo, "id", (ID.STERNUMSPINE,), keep_first=True)
    deduplicate_point_attribs(geo, "id", outer_loop_ids(), keep_first=False)
    return [
        pt for pt in geo.points()
        if pt.attribValue("id").startswith(outer_loop_ids())
    ]

def _adjust_midpoints_after_outset(geo: hou.Geometry) -> None:
    points = points_by_id(geo)
    rim1, rim_neg1 = points_from_geo(geo, sternumrim(1), sternumrim(-1))
    p0 = (rim1.position() + rim_neg1.position()) / 2.0
    (rim0,) = points_from_geo(geo, sternumrim(0))
    rim0.setPosition(hou.Vector3(0.0, p0[1], p0[2]))
    if sternumrim(5) in points:
        (rim5,) = points_from_geo(geo, sternumrim(5))
        p5 = rim5.position()
        rim5.setPosition(hou.Vector3(0.0, p5[1], p5[2]))
    for side in (1, -1):
        for i in range(1, 5):
            start, end = points_from_geo(
                geo,
                sternumrim(side * i),
                sternumrim(5) if i == 4 else sternumrim(side * (i + 1)),
            )
            start = start.position()
            end = end.position()
            midpoint = (start + end) / 2.0
            (middle_point,) = points_from_geo(geo, sternummiddle(side * i))
            middle_point.setPosition(midpoint)
