import math

import hou

import base_sops
from base_sops import basemaxillamembrane
from helper import point_from_geo
from leg_builder import LegParam, build_leg
from pedipalp import build_pedipalp, position_pedipalp, adjust_pedipalp_coxa
from utilities.common import (
    add_float_param,
    add_heading,
    add_prim_attr,
    fill_face,
    get_control,
    get_float_parm,
    get_params,
    get_parent,
    points_to_positions,
    remove_attrs,
    rotation_to,
)
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import fill_pentagon_with_buffer


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

    built_pedipalp = sopify(legs, extracted, build_pedipalp)
    positioned_pedipalp = sopify(legs, built_pedipalp, position_pedipalp)
    adjusted_pedipalp = sopify(legs, positioned_pedipalp, adjust_pedipalp_coxa)
    merged_legs = add_merge(legs, "merge_legs_and_pedipalp", extruded, adjusted_pedipalp)

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
    add_float_param(
        legs,
        "min_segment_flexes",
        7,
        (140, 180, 200, 30, 95, 150, 170),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_float_param(
        legs,
        "max_segment_yaws",
        7,
        (15, 25, 0, 0, 0, 0, 20),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_heading(
        legs,
        "Front Leg",
    )
    add_float_param(
        legs,
        "front_coxa_size_ratio",
        2,
        (0.75, 0.7),
        (0.0, None),
        help="Width and length relative to the base sockets' size.",
    )
    add_float_param(
        legs,
        "front_segment_length_ratios",
        6,
        (0.8, 3.75, 3, 2.5, 2.25, 1.5),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Ratio relative to coxa length.",
    )
    add_heading(
        legs,
        "Other Main Legs",
    )
    add_float_param(
        legs,
        "leg_width_ratios",
        3,
        (0.9, 0.9, 0.95),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_float_param(
        legs,
        "leg_length_ratios",
        3,
        (0.85, 0.85, 1.1),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_heading(
        legs,
        "Pedipalp",
    )
    add_float_param(
        legs,
        "pedipalp_segment_length_ratios",
        5,
        (0.8, 3.75, 3, 2.5, 1.5),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Ratio relative to pedipalp's own coxa length.",
    )


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_param(
        control,
        "support_loop_ratio",
        1,
        0.015,
        (0.0, 1.0),
        help="Ratio relative to coxa width, fixed across segments.",
    )
    add_float_param(
        control,
        "segment_height_ratio",
        1,
        1.15,
        (0.0, None),
    )
    add_float_param(
        control,
        "segment_lateral_ratio",
        1,
        0.5,
        (0.0, None),
        help="The top to the thickest part : the thickest part to the bottom",
    )
    add_float_param(
        control,
        "segment_shrink_ratios",
        2,
        (0.95, 0.875),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="1 for in-segment section shrinking; 2 for between-section.",
    )
    add_float_param(
        control,
        "minimum_membrane_spec",
        2,
        (1.0, 5.0),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Membrane distance in ratio to the latter segment's width; Wedge angle in degrees",
    )
    add_float_param(
        control,
        "tarsus_wedge_angle",
        1,
        45.0,
        (-60.0, 60.0),
    )
    return control


def _extract_right_coxa(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = [
        prim for prim in geo.prims()
        if prim.boundingBox().center().x() > 0 and prim.stringAttribValue("region").startswith(base_sops.Region.COXASOCKET)
    ]
    assert len(socket_prims) == 8, f"Expected 8 right coxa socket prims, got {len(socket_prims)}"

    pedipalp_points = point_from_geo(
        geo,
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        basemaxillamembrane(3),
        basemaxillamembrane(4),
    )

    used_points = {v.point() for prim in socket_prims for v in prim.vertices()} | set(pedipalp_points)
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
    prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith(base_sops.Region.COXASOCKET)
    ]
    prims = sorted(prims, key=lambda p: p.boundingBox().center().z())
    assert len(prims) == 8, f"Expected 8 socket prims, got {len(prims)}"

    groups = [prims[i:i + 2] for i in range(0, 8, 2)]
    corner_result = []
    midpoint_result = []
    for group in groups:
        p_set = set()
        for prim in group:
            for v in prim.vertices():
                p_set.add(v.point())
        assert len(p_set) == 6, f"Expected 6 unique points in socket group, got {len(p_set)}"

        pts_prim0 = {v.point() for v in group[0].vertices()}
        pts_prim1 = {v.point() for v in group[1].vertices()}
        shared_pts = pts_prim0 & pts_prim1
        outer_pts = list(p_set - shared_pts)
        assert len(outer_pts) == 4, f"Expected 4 outer points, got {len(outer_pts)}"
        assert len(shared_pts) == 2, f"Expected 2 shared points, got {len(shared_pts)}"

        mid_y = sum(p.position().y() for p in outer_pts) / 4.0
        top_pts = [p for p in outer_pts if p.position().y() >= mid_y]
        btm_pts = [p for p in outer_pts if p.position().y() < mid_y]
        assert len(top_pts) == 2 and len(btm_pts) == 2

        top_pts.sort(key=lambda p: p.position().z())
        btm_pts.sort(key=lambda p: p.position().z())
        corner_result.append([top_pts[0], top_pts[1], btm_pts[0], btm_pts[1]])

        shared_list = sorted(list(shared_pts), key=lambda p: p.position().y(), reverse=True)
        midpoint_result.append([shared_list[0], shared_list[1]])

    return corner_result, midpoint_result


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
        origin = top_mid
        direction = hou.Vector3(top_mid.x() - btm_mid.x(), 0.0, top_mid.z() - btm_mid.z()).normalized()

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

    params = get_params(parent, use_tuple=False)
    control_params = get_params(get_control(parent), use_tuple=False)

    front_socket_width, _ = get_front_coxa_socket_size(geo)
    front_coxa_width = front_socket_width * params.front_coxa_size_ratio.x()
    front_coxa_length = front_socket_width * params.front_coxa_size_ratio.y()

    if leg_index == 0:
        coxa_width = front_coxa_width
        coxa_length = front_coxa_length
    else:
        coxa_width = front_coxa_width * params.leg_width_ratios[leg_index - 1]
        coxa_length = front_coxa_length * params.leg_length_ratios[leg_index - 1]

    coxa_height = coxa_width
    coxa_size = (coxa_width, coxa_height, coxa_length)
    segment_specs = tuple(zip(params.max_segment_yaws[1:], params.min_segment_flexes[1:]))

    return LegParam(
        coxa_size=coxa_size,
        length_ratios=tuple(params.front_segment_length_ratios),
        yaw_flex_specs=segment_specs,
        height_ratio=control_params.segment_height_ratio,
        spine_ratio=control_params.segment_lateral_ratio,
        shrink_ratios=control_params.segment_shrink_ratios,
        minimum_membrane=control_params.minimum_membrane_spec,
        support_loop_ratio=control_params.support_loop_ratio,
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
    add_prim_attr(geo, "region", "")

    # su: socket upper, sb: socket bottom
    su1, su2, sb1, sb2 = socket_points
    pos_su1, pos_su2, pos_sb1, pos_sb2 = points_to_positions(socket_points)
    # s_mu, s_mb: socket midpoint upper / bottom
    s_mu, s_mb = socket_midpoints

    coxa_start_pts = coxa_points[:4]
    coxa_start_support_pts = coxa_points[4:8]
    coxa_end_pts = coxa_points[12:16]

    # pos_bu: base upper, pos_bb: base bottom
    pos_bu2, pos_bu1, pos_bb2, pos_bb1 = points_to_positions(coxa_end_pts)

    y_d1 = abs(pos_sb1.y() - pos_bb1.y())
    xz_d1 = math.sqrt((pos_bb1.x() - pos_sb1.x()) ** 2 + (pos_bb1.z() - pos_sb1.z()) ** 2)
    ratio1 = (y_d1 / xz_d1) if xz_d1 > 1e-6 else 0.5
    # pos_ab: adjusted bottom, pos_au: adjusted upper
    pos_ab1 = hou.Vector3(
        pos_sb1.x() + (pos_bb1.x() - pos_sb1.x()) * ratio1,
        pos_bb1.y(),
        pos_sb1.z() + (pos_bb1.z() - pos_sb1.z()) * ratio1,
    )
    y_d2 = abs(pos_sb2.y() - pos_bb2.y())
    xz_d2 = math.sqrt((pos_bb2.x() - pos_sb2.x()) ** 2 + (pos_bb2.z() - pos_sb2.z()) ** 2)
    ratio2 = (y_d2 / xz_d2) if xz_d2 > 1e-6 else 0.5
    pos_ab2 = hou.Vector3(
        pos_sb2.x() + (pos_bb2.x() - pos_sb2.x()) * ratio2,
        pos_bb2.y(),
        pos_sb2.z() + (pos_bb2.z() - pos_sb2.z()) * ratio2,
    )
    pos_au1 = (pos_su1 + pos_bu1) * 0.5
    pos_au2 = (pos_su2 + pos_bu2) * 0.5

    coxa_start_support_pts[0].setPosition(pos_au2)
    coxa_start_support_pts[1].setPosition(pos_au1)
    coxa_start_support_pts[2].setPosition(pos_ab2)
    coxa_start_support_pts[3].setPosition(pos_ab1)

    # eu: end upper, eb: end bottom
    eu2 = coxa_start_support_pts[0]
    eu1 = coxa_start_support_pts[1]
    eb2 = coxa_start_support_pts[2]
    eb1 = coxa_start_support_pts[3]

    support_loop_ratio = get_float_parm(get_control(node), "support_loop_ratio")

    coxa_width = coxa_start_pts[0].position().distanceTo(coxa_start_pts[1].position())
    cut_length = coxa_width * support_loop_ratio
    pos_su_mid = (pos_su1 + pos_su2) * 0.5
    pos_au_mid = (pos_au1 + pos_au2) * 0.5
    dist_socket_to_support = pos_su_mid.distanceTo(pos_au_mid)
    buffer_ratio = 1.0 - cut_length / dist_socket_to_support

    # Upper pentagon: su1, s_mu, su2, eu2, eu1
    mid_u, _, b_eu2, b_eu1 = fill_pentagon_with_buffer(
        geo,
        [su1, s_mu, su2, eu2, eu1],
        (eu2, eu1),
        buffer_ratio,
        (su1, eu1),
    )
    # Bottom pentagon: sb2, s_mb, sb1, eb1, eb2
    mid_b, _, b_eb1, b_eb2 = fill_pentagon_with_buffer(
        geo,
        [sb2, s_mb, sb1, eb1, eb2],
        (eb1, eb2),
        buffer_ratio,
        (sb1, eb1),
    )

    # Back side (+Z): split into 2 quads by (b_eu2, b_eb2)
    fill_face(geo, [sb2, su2, b_eu2, b_eb2])
    fill_face(geo, [b_eb2, b_eu2, eu2, eb2])

    # Front side (-Z): split into 3 quads by (mid_u, mid_b) and (b_eu1, b_eu1)
    fill_face(geo, [su1, sb1, mid_b, mid_u])
    fill_face(geo, [mid_u, mid_b, b_eb1, b_eu1])
    fill_face(geo, [b_eu1, b_eb1, eb1, eu1])

    geo.deletePoints(coxa_start_pts)


def _remove_tmp_attributes(node: hou.SopNode) -> None:
    remove_attrs(node.geometry(), global_attribs=("tmp_coxa_corners", "tmp_coxa_midpoints"))


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