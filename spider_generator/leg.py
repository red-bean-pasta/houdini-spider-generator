import math

import hou

from . import base_sops, pedipalp
from .leg_builder import LegParam, build_leg
from houkit.attributer import add_prim_attrib, remove_attribs
from houkit.geomath import rotation_to
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
from houkit.parameterizer import add_float_parm, add_heading, get_float_parm, get_parms
from houkit.topology import fill_face, fill_pentagon_with_buffer, points_to_positions
from .helper import prims_by_attr


def build(
    spider: hou.SopNode,
    base: hou.SopNode,
) -> hou.SopNode:
    legs = add_reloadable_subnet(spider, "legs")
    legs.setInput(0, base)
    _add_parameters(legs)
    _add_controls(legs)

    extracted = sopify(legs, legs.indirectInputs()[0], _extract_right_coxa)
    extruded = sopify(legs, extracted, _extrude_legs)

    pedipalp_built = pedipalp.build(legs, extracted)
    merged_legs = add_merge(legs, "merge_legs_and_pedipalp", extruded, pedipalp_built)

    cleaned = sopify(legs, merged_legs, _remove_tmp_attributes)
    fused = add_fuse(legs, "fuse_sockets", cleaned)
    mirrored = add_mirror(legs, "mirror_left_legs", fused, (1, 0, 0), True, False)
    add_output(legs, "OUT_LEGS", mirrored)

    legs.layoutChildren()
    return legs


def _add_parameters(legs: hou.OpNode) -> None:
    add_heading(
        legs,
        "Basic",
    )
    add_float_parm(
        legs,
        "min_flex_angles",
        6,
        (180, 200, 30, 95, 150, 170),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Minimum Flex Angles",
        help="One minimum flex angle per post-coxa segment joint.",
    )
    add_float_parm(
        legs,
        "max_yaw_angles",
        6,
        (25, 0, 0, 0, 0, 20),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Maximum Yaw Angles",
        help="One maximum yaw angle per post-coxa segment joint.",
    )
    add_heading(
        legs,
        "Front Leg",
    )
    add_float_parm(
        legs,
        "front_coxa_width_length_ratios",
        2,
        (0.75, 1.2),
        (0.0, None),
        label="Front Coxa Width / Length",
        help="X scales coxa width and Y scales coxa length from the front socket width.",
    )
    add_float_parm(
        legs,
        "front_segment_length_ratios",
        6,
        (0.33, 1.5, 0.9, 1.2, 1, 0.7),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Front Leg Lengths",
        help="One length ratio per post-coxa segment, measured against front coxa length.",
    )
    add_heading(
        legs,
        "Other Main Legs",
    )
    add_float_parm(
        legs,
        "other_leg_width_ratios",
        3,
        (0.8, 0.7, 0.8),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Other Leg Widths",
        help="Coxa-width scale for legs 2–4 relative to the front coxa.",
    )
    add_float_parm(
        legs,
        "other_leg_length_ratios",
        3,
        (0.88, 0.9, 1.1),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Other Leg Lengths",
        help="Coxa-length scale for legs 2–4 relative to the front coxa.",
    )
    pedipalp.add_parameters(legs)


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_parm(
        control,
        "joint_support_loop_ratio",
        1,
        0.015,
        (0.0, 1.0),
        label="Joint Support Loop",
        help="Inset width at coxa sockets and segment joints, relative to coxa width.",
    )
    add_float_parm(
        control,
        "coxa_trochanter_height_ratio",
        1,
        0.63,
        (0.0, None),
        label="Coxa-Trochanter Height",
        help="Height-to-width proportion of the trochanter segment.",
    )
    add_float_parm(
        control,
        "other_segment_height_ratio",
        1,
        1.15,
        (0.0, None),
        label="Other Segment Height",
        help="Height-to-width proportion of post-trochanter segments.",
    )
    add_float_parm(
        control,
        "segment_bulge_bias_ratio",
        1,
        0.5,
        (0.0, None),
        label="Segment Bulge Bias",
        help="Moves the segment’s fullest area between its upper and lower sides.",
    )
    add_float_parm(
        control,
        "segment_taper_ratios",
        2,
        (0.98, 0.875),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Segment Taper",
        help="X sets taper along a segment; Y sets the size change at each joint.",
    )
    add_float_parm(
        control,
        "joint_clearance_limits",
        2,
        (1.0, 5.0),
        (0.0, 45.0),
        hou.parmNamingScheme.Base1,
        label="Joint Clearance Limits",
        help="X is minimum membrane separation in scene units. Y is minimum flex angle; keep it strictly between 0° and 45°.",
    )
    add_float_parm(
        control,
        "tarsus_wedge_angle",
        1,
        45.0,
        (-60.0, 60.0),
        label="Tarsus Wedge",
        help="Terminal tarsus wedge angle.",
    )
    add_float_parm(
        control,
        "coxa_start_wedge_angle",
        1,
        45.0,
        (0.0, 90.0),
        label="Coxa Start Wedge",
        help="Wedge angle used to place the coxa socket's lower support.",
    )
    return control


def _extract_right_coxa(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = [
        prim for prim in prims_by_attr(geo, "region", base_sops.Region.COXASOCKET, startswith=True)
        if prim.boundingBox().center().x() > 0
    ]
    assert len(socket_prims) == 8, f"Expected 8 right coxa socket prims, got {len(socket_prims)}"

    used_points = (
            {v.point() for prim in socket_prims for v in prim.vertices()}
            | pedipalp.prepare(geo)
    )
    unused_points = [p for p in geo.points() if p not in used_points]
    geo.deletePoints(unused_points)

    socket_corners, socket_midpoints = _get_right_coxa_socket_points(node)
    geo.deletePrims(geo.prims(), keep_points=True)

    flat_corner_nums = [p.number() for group in socket_corners for p in group]
    geo.addArrayAttrib(hou.attribType.Global, "tmp_coxa_corners", hou.attribData.Int)
    geo.setGlobalAttribValue("tmp_coxa_corners", flat_corner_nums)

    flat_midpoint_nums = [p.number() for group in socket_midpoints for p in group]
    geo.addArrayAttrib(hou.attribType.Global, "tmp_coxa_midpoints", hou.attribData.Int)
    geo.setGlobalAttribValue("tmp_coxa_midpoints", flat_midpoint_nums)

def _get_right_coxa_socket_points(
    node: hou.SopNode,
) -> tuple[list[list[hou.Point]], list[list[hou.Point]]]:
    geo = node.geometry()
    prims = prims_by_attr(geo, "region", base_sops.Region.COXASOCKET, startswith=True)
    prims = sorted(prims, key=lambda p: p.boundingBox().center().z())
    assert len(prims) == 8, f"Expected 8 socket prims, got {len(prims)}"

    groups = [prims[i:i + 2] for i in range(0, 8, 2)]
    corner_result = []
    midpoint_result = []
    for group in groups:
        corners, midpoints = _get_socket_group_points(group)
        corner_result.append(corners)
        midpoint_result.append(midpoints)

    return corner_result, midpoint_result


def _get_socket_group_points(
    group: list[hou.Prim],
) -> tuple[list[hou.Point], list[hou.Point]]:
    group_points = {
        vertex.point()
        for prim in group
        for vertex in prim.vertices()
    }
    assert len(group_points) == 6, f"Expected 6 unique points in socket group, got {len(group_points)}"

    first_points = {vertex.point() for vertex in group[0].vertices()}
    second_points = {vertex.point() for vertex in group[1].vertices()}
    shared_points = first_points & second_points
    outer_points = list(group_points - shared_points)
    assert len(outer_points) == 4, f"Expected 4 outer points, got {len(outer_points)}"
    assert len(shared_points) == 2, f"Expected 2 shared points, got {len(shared_points)}"

    mid_y = sum(point.position().y() for point in outer_points) / 4.0
    top_points = [point for point in outer_points if point.position().y() >= mid_y]
    bottom_points = [point for point in outer_points if point.position().y() < mid_y]
    assert len(top_points) == 2 and len(bottom_points) == 2

    top_points.sort(key=lambda point: point.position().z())
    bottom_points.sort(key=lambda point: point.position().z())
    corners = [top_points[0], top_points[1], bottom_points[0], bottom_points[1]]
    midpoints = sorted(shared_points, key=lambda point: point.position().y(), reverse=True)
    return corners, midpoints


def _extrude_legs(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    corners = geo.attribValue("tmp_coxa_corners")
    midpoints = geo.attribValue("tmp_coxa_midpoints")

    for i in range(4):
        pt_nums = corners[i * 4:(i + 1) * 4]
        pts = [geo.iterPoints()[p] for p in pt_nums]
        mid_pt_nums = midpoints[i * 2:(i + 1) * 2]
        mid_pts = [geo.iterPoints()[p] for p in mid_pt_nums]

        # sz: small Z, bz: big Z
        pos_top_sz, pos_top_bz, pos_btm_sz, pos_btm_bz = points_to_positions(pts)

        top_mid = (pos_top_sz + pos_top_bz) / 2.0
        btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
        direction = hou.Vector3(top_mid.x() - btm_mid.x(), 0.0, top_mid.z() - btm_mid.z()).normalized()
        bottom_z_offset = (btm_mid - top_mid).dot(direction)
        origin = top_mid + direction * bottom_z_offset

        param = _get_leg_param(node, i)
        (seg_pts, thickness_pts, mem_pts), warnings = build_leg(geo, param)
        for w in warnings:
            node.addWarning(w)

        q = rotation_to(hou.Vector3(0.0, 0.0, -1.0), direction)
        for pt in seg_pts + thickness_pts + mem_pts:
            pt.setPosition(q.rotate(pt.position()) + origin)

        _adjust_coxa(node, pts, mid_pts, seg_pts[:16])

def _get_leg_param(
    node: hou.SopNode,
    leg_index: int,
) -> LegParam:
    geo = node.geometry()
    parent = get_parent(node)

    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(parent, "CONTROL"), use_tuple=False)

    front_socket_width, _ = get_front_coxa_socket_size(geo)
    front_coxa_width = front_socket_width * params.front_coxa_width_length_ratios.x()
    front_coxa_length = front_socket_width * params.front_coxa_width_length_ratios.y()

    if leg_index == 0:
        coxa_width = front_coxa_width
        coxa_length = front_coxa_length
    else:
        coxa_width = front_coxa_width * params.other_leg_width_ratios[leg_index - 1]
        coxa_length = front_coxa_length * params.other_leg_length_ratios[leg_index - 1]

    coxa_width_length = (coxa_width, coxa_length)

    return LegParam.from_specs(
        coxa_width_length=coxa_width_length,
        length_ratios=tuple(params.front_segment_length_ratios),
        max_segment_yaws=tuple(params.max_yaw_angles),
        min_segment_flexes=tuple(params.min_flex_angles),
        coxa_trochanter_height_ratio=control_params.coxa_trochanter_height_ratio,
        other_segment_height_ratio=control_params.other_segment_height_ratio,
        spine_ratio=control_params.segment_bulge_bias_ratio,
        shrink_ratios=control_params.segment_taper_ratios,
        minimum_membrane=control_params.joint_clearance_limits,
        support_loop_ratio=control_params.joint_support_loop_ratio,
        tarsus_wedge_angle=control_params.tarsus_wedge_angle,
    )


def _adjust_coxa(
    node: hou.SopNode,
    socket_points: list[hou.Point],
    socket_midpoints: list[hou.Point],
    coxa_points: list[hou.Point],
) -> None:
    assert len(coxa_points) == 16, f"Expected 16 coxa points, got {len(coxa_points)}"
    assert len(socket_points) == 4, f"Expected 4 socket points, got {len(socket_points)}"
    assert len(socket_midpoints) == 2, f"Expected 2 socket midpoints, got {len(socket_midpoints)}"

    geo = node.geometry()
    add_prim_attrib(geo, "region", "")

    coxa_start_pts = coxa_points[:4]
    coxa_start_support_pts = coxa_points[4:8]
    coxa_end_pts = coxa_points[12:16]

    coxa_start_wedge_angle = get_float_parm(get_control(node, "CONTROL"), "coxa_start_wedge_angle")
    adjusted_support_positions = _get_adjusted_coxa_support_positions(
        socket_points,
        coxa_end_pts,
        coxa_start_wedge_angle,
    )
    for point, position in zip(coxa_start_support_pts, adjusted_support_positions):
        point.setPosition(position)

    support_loop_ratio = get_float_parm(get_control(node, "CONTROL"), "joint_support_loop_ratio")
    buffer_ratio = _get_coxa_buffer_ratio(
        socket_points,
        coxa_start_pts,
        coxa_start_support_pts,
        support_loop_ratio,
    )
    _build_coxa_socket_faces(
        geo,
        socket_points,
        socket_midpoints,
        coxa_start_support_pts,
        buffer_ratio,
    )

    geo.deletePoints(coxa_start_pts)


def _get_adjusted_coxa_support_positions(
    socket_points: list[hou.Point],
    coxa_end_points: list[hou.Point],
    coxa_start_wedge_angle: float,
) -> tuple[hou.Vector3, hou.Vector3, hou.Vector3, hou.Vector3]:
    # su: socket upper, sb: socket bottom
    pos_su1, pos_su2, pos_sb1, pos_sb2 = points_to_positions(socket_points)
    # pos_bu: base upper, pos_bb: base bottom
    pos_bu2, pos_bu1, pos_bb2, pos_bb1 = points_to_positions(coxa_end_points)

    pos_ab1 = _get_adjusted_bottom_coxa_position(pos_sb1, pos_bb1, coxa_start_wedge_angle)
    pos_ab2 = _get_adjusted_bottom_coxa_position(pos_sb2, pos_bb2, coxa_start_wedge_angle)
    pos_au1 = (pos_su1 + pos_bu1) * 0.5
    pos_au2 = (pos_su2 + pos_bu2) * 0.5
    return pos_au2, pos_au1, pos_ab2, pos_ab1


def _get_adjusted_bottom_coxa_position(
    socket_position: hou.Vector3,
    base_position: hou.Vector3,
    wedge_angle: float,
) -> hou.Vector3:
    y_delta = abs(socket_position.y() - base_position.y())
    xz_delta = math.sqrt(
        (base_position.x() - socket_position.x()) ** 2
        + (base_position.z() - socket_position.z()) ** 2
    )
    ratio = (
        y_delta * math.tan(math.radians(wedge_angle)) / xz_delta
        if xz_delta > 1e-6 else
        0.5
    )
    return hou.Vector3(
        socket_position.x() + (base_position.x() - socket_position.x()) * ratio,
        base_position.y(),
        socket_position.z() + (base_position.z() - socket_position.z()) * ratio,
    )


def _get_coxa_buffer_ratio(
    socket_points: list[hou.Point],
    coxa_start_points: list[hou.Point],
    support_points: list[hou.Point],
    support_loop_ratio: float,
) -> float:
    pos_su1, pos_su2, _, _ = points_to_positions(socket_points)
    pos_au2, pos_au1, _, _ = points_to_positions(support_points)
    coxa_width = coxa_start_points[0].position().distanceTo(coxa_start_points[1].position())
    cut_length = coxa_width * support_loop_ratio
    pos_su_mid = (pos_su1 + pos_su2) * 0.5
    pos_au_mid = (pos_au1 + pos_au2) * 0.5
    dist_socket_to_support = pos_su_mid.distanceTo(pos_au_mid)
    return 1.0 - cut_length / dist_socket_to_support


def _build_coxa_socket_faces(
    geo: hou.Geometry,
    socket_points: list[hou.Point],
    socket_midpoints: list[hou.Point],
    support_points: list[hou.Point],
    buffer_ratio: float,
) -> None:
    # su: socket upper, sb: socket bottom
    su1, su2, sb1, sb2 = socket_points
    # s_mu, s_mb: socket midpoint upper / bottom
    s_mu, s_mb = socket_midpoints
    eu2, eu1, eb2, eb1 = support_points

    # Upper pentagon: su1, s_mu, su2, eu2, eu1
    mid_u, _, b_eu2, b_eu1 = fill_pentagon_with_buffer(
        [su1, s_mu, su2, eu2, eu1],
        (eu2, eu1),
        buffer_ratio,
        (su1, eu1),
    )
    # Bottom pentagon: sb2, s_mb, sb1, eb1, eb2
    mid_b, _, b_eb1, b_eb2 = fill_pentagon_with_buffer(
        [sb2, s_mb, sb1, eb1, eb2],
        (eb1, eb2),
        buffer_ratio,
        (sb1, eb1),
    )

    # Back side (+Z): split into 2 quads by (b_eu2, b_eb2)
    fill_face([sb2, su2, b_eu2, b_eb2])
    fill_face([b_eb2, b_eu2, eu2, eb2])

    # Front side (-Z): split into 3 quads by (mid_u, mid_b) and (b_eu1, b_eu1)
    fill_face([su1, sb1, mid_b, mid_u])
    fill_face([mid_u, mid_b, b_eb1, b_eu1])
    fill_face([b_eu1, b_eb1, eb1, eu1])


def _remove_tmp_attributes(node: hou.SopNode) -> None:
    remove_attribs(node.geometry(), global_attributes=("tmp_coxa_corners", "tmp_coxa_midpoints"))


def get_front_coxa_socket_size(geo: hou.Geometry) -> tuple[float, float]:
    """

    :param geo:
    :return: width, length
    """
    corners = geo.attribValue("tmp_coxa_corners")
    pts = [geo.iterPoints()[p] for p in corners[:4]]

    pos_top_sz, pos_top_bz, pos_btm_sz, pos_btm_bz = points_to_positions(pts)

    width = (pos_top_bz - pos_top_sz).length()
    top_mid = (pos_top_sz + pos_top_bz) / 2.0
    btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
    height = top_mid.y() - btm_mid.y()

    return width, height
