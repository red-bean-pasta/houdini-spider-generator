import math
from enum import StrEnum, auto

import hou

import base_sops
from utilities.common import (
    add_float_param,
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_params,
    get_parent,
    points_to_positions,
    rotation_to,
    add_heading,
    remove_attrs,
    MessagedResult,
)
from utilities.nodes import (
    add_fuse,
    add_mirror,
    add_outside_recalculation,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import fill_pentagon_with_buffer, loop_cut


class Region(StrEnum):
    LEGSEGMENT = auto()
    LEGMEMBRANE = auto()


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
    cleaned = sopify(legs, extruded, _remove_tmp_attributes)
    fused = add_fuse(legs, "fuse_sockets", cleaned)
    mirrored = add_mirror(legs, "mirror_left_legs", fused, (1, 0, 0), True, False)
    recalculated = add_outside_recalculation(legs, "recalculate_normals", mirrored)
    add_output(legs, "OUT_LEGS", recalculated)

    legs.layoutChildren()
    return legs


def _add_parameters(legs: hou.OpNode) -> None:
    add_heading(
        legs,
        "Basic",
    )
    add_float_param(
        legs,
        "support_loop_ratio",
        1,
        0.015,
        (0.0, 1.0),
        help="Ratio relative to coxa width, fixed across segments.",
    )
    add_float_param(
        legs,
        "segment_height_ratio",
        1,
        1.15,
        (0.0, None),
    )
    add_float_param(
        legs,
        "segment_lateral_ratio",
        1,
        0.5,
        (0.0, None),
        help="The top to the thickest part : the thickest part to the bottom",
    )
    add_float_param(
        legs,
        "segment_shrink_ratios",
        2,
        (0.95, 0.875),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="1 for in-segment section shrinking; 2 for between-section.",
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
    add_float_param(
        legs,
        "minimum_membrane_spec",
        2,
        (1.0, 5.0),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Membrane distance in ratio to the latter segment's width; Wedge angle in degrees",
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
        "Other Legs",
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


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
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

    used_points = {v.point() for prim in socket_prims for v in prim.vertices()}
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
    prims = sorted(geo.prims(), key=lambda p: p.boundingBox().center().z())
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


def _remove_tmp_attributes(node: hou.SopNode) -> None:
    remove_attrs(node.geometry(), global_attribs=("tmp_coxa_corners", "tmp_coxa_midpoints"))


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

        pos_top_sz, pos_top_bz, pos_btm_sz, pos_btm_bz = points_to_positions(pts)

        top_mid = (pos_top_sz + pos_top_bz) / 2.0
        btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
        origin = top_mid
        direction = hou.Vector3(top_mid.x() - btm_mid.x(), 0.0, top_mid.z() - btm_mid.z()).normalized()

        seg_pts, mem_pts = _build_leg(node, i)

        q = rotation_to(hou.Vector3(0.0, 0.0, -1.0), direction)
        for pt in seg_pts + mem_pts:
            pt.setPosition(q.rotate(pt.position()) + origin)

        _adjust_coxa(node, pts, mid_pts, seg_pts[:16])


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

    su1, su2, sb1, sb2 = socket_points
    pos_su1, pos_su2, pos_sb1, pos_sb2 = points_to_positions(socket_points)
    s_mu, s_mb = socket_midpoints

    coxa_start_pts = coxa_points[:4]
    coxa_start_support_pts = coxa_points[4:8]
    coxa_end_pts = coxa_points[12:16]

    pos_bu2, pos_bu1, pos_bb2, pos_bb1 = points_to_positions(coxa_end_pts)

    y_d1 = abs(pos_sb1.y() - pos_bb1.y())
    xz_d1 = math.sqrt((pos_bb1.x() - pos_sb1.x()) ** 2 + (pos_bb1.z() - pos_sb1.z()) ** 2)
    ratio1 = (y_d1 / xz_d1) if xz_d1 > 1e-6 else 0.5
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

    eu2 = coxa_start_support_pts[0]
    eu1 = coxa_start_support_pts[1]
    eb2 = coxa_start_support_pts[2]
    eb1 = coxa_start_support_pts[3]

    parent = get_parent(node)
    support_loop_ratio = get_float_parm(parent, "support_loop_ratio")

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


def _build_leg(
        node: hou.SopNode,
        leg_index: int,
) -> tuple[list[hou.Point], list[hou.Point]]:
    geo = node.geometry()
    add_prim_attr(geo, "region", "")

    seg_pts, warnings = _build_segment_tubes(node, leg_index)
    for w in warnings:
        node.addWarning(w)
    all_seg_pts = _add_segment_loop_cuts(node, seg_pts)
    all_seg_pts, mem_pts = _fill_mebranes(all_seg_pts)
    all_mem_pts = _add_membrane_loop_cuts(node, all_seg_pts, mem_pts)
    _close_tarsus(node, all_seg_pts)
    return all_seg_pts, all_mem_pts

def _build_segment_tubes(
        node: hou.SopNode,
        leg_index: int,
) -> MessagedResult[list[hou.Point]]:
    assert 0 <= leg_index <= 3
    geo = node.geometry()
    parent = get_parent(node)

    params = get_params(parent, use_tuple=False)
    segment_height_ratio = params.segment_height_ratio
    spine_ratio = params.segment_lateral_ratio
    shrink_ratios = params.segment_shrink_ratios
    min_segment_flexes = params.min_segment_flexes
    max_segment_yaws = params.max_segment_yaws
    minimum_membrane = params.minimum_membrane_spec
    segment_specs = tuple(zip(max_segment_yaws[1:], min_segment_flexes[1:]))

    front_coxa_size_ratio = params.front_coxa_size_ratio
    length_ratios = params.front_segment_length_ratios
    leg_width_ratios = params.leg_width_ratios
    leg_length_ratios = params.leg_length_ratios

    front_socket_width, _ = _get_front_coxa_socket_size(geo)
    front_coxa_width = front_socket_width * front_coxa_size_ratio.x()
    front_coxa_length = front_socket_width * front_coxa_size_ratio.y()

    if leg_index == 0:
        coxa_width = front_coxa_width
        coxa_length = front_coxa_length
    else:
        coxa_width = front_coxa_width * leg_width_ratios[leg_index - 1]
        coxa_length = front_coxa_length * leg_length_ratios[leg_index - 1]

    coxa_height = coxa_width
    coxa_size = (coxa_width, coxa_height, coxa_length)

    segments, messages = _get_leg_points(
        coxa_size,
        segment_height_ratio,
        shrink_ratios,
        list(length_ratios),
        spine_ratio,
        segment_specs,
        minimum_membrane,
    )

    seg_pts: list[hou.Point] = []
    for seg in segments:
        cur_seg_pts = [geo.createPoint() for _ in range(8)]
        for pt, pos in zip(cur_seg_pts, seg):
            pt.setPosition(pos)
        seg_pts.extend(cur_seg_pts)

        start_loop = [cur_seg_pts[0], cur_seg_pts[1], cur_seg_pts[3], cur_seg_pts[2]]
        end_loop = [cur_seg_pts[4], cur_seg_pts[5], cur_seg_pts[7], cur_seg_pts[6]]
        for j in range(4):
            next_j = (j + 1) % 4
            prim = fill_face(geo, [
                start_loop[j],
                start_loop[next_j],
                end_loop[next_j],
                end_loop[j],
            ])
            prim.setAttribValue("region", Region.LEGSEGMENT)

    return MessagedResult(seg_pts, messages)

def _add_segment_loop_cuts(
        node: hou.SopNode,
        seg_pts: list[hou.Point],
) -> list[hou.Point]:
    assert len(seg_pts) % 8 == 0, f"Expected seg_pts length to be a multiple of 8, got {len(seg_pts)}"
    geo = node.geometry()
    parent = get_parent(node)
    support_loop_ratio = get_float_parm(parent, "support_loop_ratio")

    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_segs = len(seg_pts) // 8
    all_seg_pts: list[hou.Point] = []

    for i in range(num_segs):
        cur_pts = seg_pts[i * 8:(i + 1) * 8]
        start_pts = cur_pts[:4]
        end_pts = cur_pts[4:]

        start_cut = _add_tube_loop_cut(geo, start_pts, end_pts, cut_length)
        end_cut = _add_tube_loop_cut(geo, end_pts, start_cut, cut_length)

        all_seg_pts.extend([
            *start_pts,
            *start_cut,
            *end_cut,
            *end_pts,
        ])

    return all_seg_pts

def _add_membrane_loop_cuts(
        node: hou.SopNode,
        seg_pts: list[hou.Point],
        mem_pts: list[hou.Point],
) -> list[hou.Point]:
    assert len(seg_pts) % 16 == 0, f"Expected seg_pts length to be a multiple of 16, got {len(seg_pts)}"
    geo = node.geometry()
    parent = get_parent(node)
    support_loop_ratio = get_float_parm(parent, "support_loop_ratio")

    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_segs = len(seg_pts) // 16
    all_mem_pts: list[hou.Point] = []

    for i in range(num_segs - 1):
        former_end = seg_pts[i * 16 + 12:(i + 1) * 16]
        latter_start = seg_pts[(i + 1) * 16:(i + 1) * 16 + 4]
        mid_pts = mem_pts[i * 4:(i + 1) * 4]

        fu1 = former_end[0]
        lu1 = latter_start[0]
        half_width = fu1.position().distanceTo(lu1.position()) * 0.5
        if cut_length >= half_width:
            all_mem_pts.extend(mid_pts)
            continue

        former_cut = _add_tube_loop_cut(geo, former_end, mid_pts, cut_length)
        latter_cut = _add_tube_loop_cut(geo, latter_start, mid_pts, cut_length)
        all_mem_pts.extend([
            *former_cut,
            *mid_pts,
            *latter_cut,
        ])

    return all_mem_pts

def _close_tarsus(
        node: hou.SopNode,
        seg_pts: list[hou.Point],
) -> None:
    assert len(seg_pts) >= 4, f"Expected at least 4 seg_pts, got {len(seg_pts)}"
    geo = seg_pts[0].geometry()
    p4, p5, p6, p7 = seg_pts[-4:]
    prim = fill_face(geo, [p4, p6, p7, p5])
    prim.setAttribValue("region", Region.LEGSEGMENT)

    parent = get_parent(node)
    control = parent.node("CONTROL")
    assert control is not None, "Expected CONTROL node"
    tarsus_wedge_angle = get_float_parm(control, "tarsus_wedge_angle")

    pos4, pos5, pos6, pos7 = points_to_positions([p4, p5, p6, p7])
    offset_y = pos4.y() - pos6.y()
    offset_z = offset_y * math.tan(math.radians(tarsus_wedge_angle))

    p6.setPosition(hou.Vector3(pos6.x(), pos6.y(), pos6.z() - offset_z))
    p7.setPosition(hou.Vector3(pos7.x(), pos7.y(), pos7.z() - offset_z))

def _add_tube_loop_cut(
        geo: hou.Geometry,
        start_pts: list[hou.Point],
        end_pts: list[hou.Point],
        cut_length: float,
) -> list[hou.Point]:
    s0, s1, s2, s3 = start_pts
    e0, e1, e2, e3 = end_pts

    edge = geo.findEdge(s0, e0)
    assert edge is not None, f"Expected edge between {s0} and {e0}"
    prim = [p for p in edge.prims() if s1 in p.points()][0]
    cut_pts, _ = loop_cut(
        prim,
        s0,
        e0,
        cut_length,
        use_ratio=False,
    )
    m0, m1, m3, m2 = cut_pts
    return [m0, m1, m2, m3]

def _fill_mebranes(
        seg_pts: list[hou.Point],
) -> tuple[list[hou.Point], list[hou.Point]]:
    if not seg_pts:
        return [], []

    geo = seg_pts[0].geometry()
    add_prim_attr(geo, "region", "")
    assert len(seg_pts) % 16 == 0, f"Expected seg_pts length to be a multiple of 16, got {len(seg_pts)}"

    membrane_points: list[hou.Point] = []
    num_segs = len(seg_pts) // 16
    for i in range(num_segs - 1):
        former_end = seg_pts[i * 16 + 12:(i + 1) * 16]
        latter_start = seg_pts[(i + 1) * 16:(i + 1) * 16 + 4]
        fu1, fu2, fb1, fb2 = former_end
        lu1, lu2, lb1, lb2 = latter_start

        (
            pos_fu1,
            pos_fu2,
            pos_fb1,
            pos_fb2,
            pos_lu1,
            pos_lu2,
            pos_lb1,
            pos_lb2,
        ) = points_to_positions(former_end + latter_start)

        lf = pos_fu1.distanceTo(pos_fb1)
        ll = pos_lu1.distanceTo(pos_lb1)
        membrane_length = (lf + ll) * 0.5

        pos_mu1 = (pos_fu1 + pos_lu1) * 0.5
        pos_mu2 = (pos_fu2 + pos_lu2) * 0.5
        pos_mb1 = (pos_fb1 + pos_lb1) * 0.5
        pos_mb2 = (pos_fb2 + pos_lb2) * 0.5
        pos_mb1[1] = (pos_mb1.y() + (pos_mu1.y() - membrane_length)) * 0.5
        pos_mb2[1] = (pos_mb2.y() + (pos_mu2.y() - membrane_length)) * 0.5

        mu1 = geo.createPoint()
        mu2 = geo.createPoint()
        mb1 = geo.createPoint()
        mb2 = geo.createPoint()

        mu1.setPosition(pos_mu1)
        mu2.setPosition(pos_mu2)
        mb1.setPosition(pos_mb1)
        mb2.setPosition(pos_mb2)

        membrane_points.extend([mu1, mu2, mb1, mb2])

        former_loop = [fu1, fu2, fb2, fb1]
        mid_loop = [mu1, mu2, mb2, mb1]
        latter_loop = [lu1, lu2, lb2, lb1]

        for j in range(4):
            next_j = (j + 1) % 4
            prim1 = fill_face(geo, [
                former_loop[j],
                former_loop[next_j],
                mid_loop[next_j],
                mid_loop[j],
            ])
            prim1.setAttribValue("region", Region.LEGMEMBRANE)
            prim2 = fill_face(geo, [
                mid_loop[j],
                mid_loop[next_j],
                latter_loop[next_j],
                latter_loop[j],
            ])
            prim2.setAttribValue("region", Region.LEGMEMBRANE)

    return seg_pts, membrane_points

def _get_front_coxa_socket_size(geo: hou.Geometry) -> tuple[float, float]:
    corners = geo.attribValue("tmp_coxa_corners")
    pts = [geo.iterPoints()[p] for p in corners[:4]]

    pos_top_sz, pos_top_bz, pos_btm_sz, pos_btm_bz = points_to_positions(pts)

    width = (pos_top_bz - pos_top_sz).length()
    top_mid = (pos_top_sz + pos_top_bz) / 2.0
    btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
    height = top_mid.y() - btm_mid.y()

    return width, height

def _get_leg_points(
        coxa_size: tuple[float, float, float],
        segment_height_ratio: float,
        section_shrink_ratios: tuple[float, float],
        length_ratios: list[float],
        spine_ratio: float,
        segment_specs: tuple[tuple[float, float], ...],
        minimum_membrane: tuple[float, float],
) -> MessagedResult[list[list[hou.Vector3]]]:
    assert len(segment_specs) == len(length_ratios) == 6  # TROCHANTER, FEMUR, PATELLA, TIBIA, METATARSUS, TARSUS

    coxa_width, coxa_height, coxa_length = coxa_size
    half_w = coxa_width / 2.0
    top_y = 0.0
    btm_y = -coxa_height
    start_z = 0.0
    end_z = -coxa_length
    coxa = [
        hou.Vector3(half_w, top_y, start_z),
        hou.Vector3(-half_w, top_y, start_z),
        hou.Vector3(half_w, btm_y, start_z),
        hou.Vector3(-half_w, btm_y, start_z),
        hou.Vector3(half_w, top_y, end_z),
        hou.Vector3(-half_w, top_y, end_z),
        hou.Vector3(half_w, btm_y, end_z),
        hou.Vector3(-half_w, btm_y, end_z),
    ]

    messages: list[str] = []
    segments: list[list[hou.Vector3]] = [coxa]
    for i, (max_yaw, min_flex) in enumerate(segment_specs):
        length_ratio_to_former = (
            length_ratios[i] / length_ratios[i - 1]
            if i > 0 else
            length_ratios[0] / 1.0
        )
        cur_height_ratio = 1.0 if i == 0 else segment_height_ratio
        (former_wedged, latter), seg_messages = _append_segment(
            segments[-1],
            cur_height_ratio,
            section_shrink_ratios,
            length_ratio_to_former,
            spine_ratio,
            max_yaw,
            min_flex,
            minimum_membrane,
        )
        messages.extend(seg_messages)
        segments[-1] = former_wedged
        segments.append(latter)

    assert len(segments) == 7
    return MessagedResult(segments, messages)


def _append_segment(
        former_positions: list[hou.Vector3],
        height_ratio: float,
        section_shrink_ratios: tuple[float, float],
        length_ratio: float,
        spine_ratio: float,
        max_yaw: float,
        min_flex: float,
        minimum_membrane: tuple[float, float],
) -> MessagedResult[tuple[list[hou.Vector3], list[hou.Vector3]]]:
    assert len(former_positions) == 8, f"Expected 8 positions for former segment, got {len(former_positions)}"

    # former_positions are ordered:
    # 0: start top +X, 1: start top -X, 2: start btm +X, 3: start btm -X
    # 4: end top +X,   5: end top -X,   6: end btm +X,   7: end btm -X
    start_top1 = former_positions[0]
    # start_topn1 = former_positions[1]
    start_btm1 = former_positions[2]
    start_btmn1 = former_positions[3]
    end_top1 = former_positions[4]
    end_topn1 = former_positions[5]
    end_btm1 = former_positions[6]
    end_btmn1 = former_positions[7]

    former_width = end_top1.x() - end_topn1.x()
    former_height = end_top1.y() - end_btm1.y()
    former_length = start_top1.z() - end_top1.z()
    former_size = (former_width, former_height)

    in_shrink, between_shrink = section_shrink_ratios
    latter_start_width = former_width * between_shrink
    latter_start_height = latter_start_width * height_ratio
    latter_start_size = (latter_start_width, latter_start_height)
    latter_length = former_length * length_ratio

    latter_end_width = latter_start_width * in_shrink
    latter_end_height = latter_start_height * in_shrink

    (offset, wedge_angle), messages = _calc_segment_offset_and_wedge(
        max_yaw,
        min_flex,
        spine_ratio,
        (former_size, latter_start_size),
        minimum_membrane,
    )

    latter_start_top_y = end_top1.y() + offset.y()
    latter_start_btm_y = latter_start_top_y - latter_start_height
    latter_start_z = end_top1.z() - offset.x()
    latter_end_z = latter_start_z - latter_length
    latter_start_hw = latter_start_width / 2.0
    latter_end_hw = latter_end_width / 2.0

    delta_z_latter = latter_start_height * math.tan(math.radians(wedge_angle))
    latter_start_btm_z = latter_start_z - delta_z_latter

    offset_y_in = -(latter_start_height - latter_end_height) * spine_ratio
    latter_end_top_y = latter_start_top_y + offset_y_in
    latter_end_btm_y = latter_end_top_y - latter_end_height

    latter_segment = [
        hou.Vector3(latter_start_hw, latter_start_top_y, latter_start_z),
        hou.Vector3(-latter_start_hw, latter_start_top_y, latter_start_z),
        hou.Vector3(latter_start_hw, latter_start_btm_y, latter_start_btm_z),
        hou.Vector3(-latter_start_hw, latter_start_btm_y, latter_start_btm_z),
        hou.Vector3(latter_end_hw, latter_end_top_y, latter_end_z),
        hou.Vector3(-latter_end_hw, latter_end_top_y, latter_end_z),
        hou.Vector3(latter_end_hw, latter_end_btm_y, latter_end_z),
        hou.Vector3(-latter_end_hw, latter_end_btm_y, latter_end_z),
    ]

    delta_z_former = former_height * math.tan(math.radians(wedge_angle))
    new_end_btm1_z = min(end_btm1.z() + delta_z_former, start_btm1.z())
    new_end_btmn1_z = min(end_btmn1.z() + delta_z_former, start_btmn1.z())

    former_positions_list = list(former_positions)
    former_positions_list[6] = hou.Vector3(end_btm1.x(), end_btm1.y(), new_end_btm1_z)
    former_positions_list[7] = hou.Vector3(end_btmn1.x(), end_btmn1.y(), new_end_btmn1_z)

    return MessagedResult((former_positions_list, latter_segment), messages)


def _calc_segment_offset_and_wedge(
        max_yaw: float,
        min_flex: float,
        spine_ratio: float,
        segment_size: tuple[tuple[float, float], tuple[float, float]],
        minimum_membrane: tuple[float, float],
) -> MessagedResult[tuple[hou.Vector2, float]]:
    (former_width, former_height), (latter_width, latter_height) = segment_size

    (offset_x, wedge_angle), messages = _calc_membrane_spec(max_yaw, min_flex, segment_size, minimum_membrane)

    offset_y = (former_height - latter_height) * spine_ratio
    if offset_y > 0:
        offset_y *= -1

    wedged_x = abs(offset_y) * math.tan(math.radians(wedge_angle))
    offset_x -= wedged_x
    offset_x = max(offset_x, minimum_membrane[0])

    return MessagedResult((hou.Vector2(offset_x, offset_y), wedge_angle), messages)


def _calc_membrane_spec(
        max_yaw_deg: float,
        min_flex_deg: float,
        segment_sections: tuple[tuple[float, float], tuple[float, float]],
        min_return: tuple[float, float],
        max_wedge_deg: float = 45,
        max_distance_ratio: float = 1.0,
) -> MessagedResult[tuple[float, float]]:
    max_yaw_deg = abs(max_yaw_deg)
    assert min_flex_deg > 0
    assert max_yaw_deg <= 90

    min_distance, min_angle = min_return
    assert min_distance > 0 and 0 < min_angle < 45

    messages: list[str] = []
    (former_width, former_height), (latter_width, latter_height) = segment_sections
    distance = latter_width / 2 * math.sin(math.radians(max_yaw_deg))
    distance = max(distance, min_distance)

    if min_flex_deg >= 180:
        angle = min_angle
        return MessagedResult((distance, angle), messages)

    min_height = min(former_height, latter_height)
    angle, wedge_messages = _solve_membrane_wedge_deg(
        min_flex_deg,
        distance,
        min_height,
    )
    messages.extend(wedge_messages)
    angle = max(angle, min_return[1])
    if angle > max_wedge_deg:
        angle = max_wedge_deg
        distance = _solve_membrane_thickness_deg(
            180 - 2 * max_wedge_deg - min_flex_deg,
            min_height,
            max_wedge_deg,
        )
        max_distance = max(former_width, latter_width) * max_distance_ratio
        if distance > max_distance:
            max_membrane_angle = math.degrees(
                math.atan(max_distance * math.cos(math.radians(max_wedge_deg)) / min_height)
            )
            min_flex_ceiling = 180 - 2 * max_wedge_deg - max_membrane_angle
            messages.append(
                f"Membrane distance ({distance:.4f}) exceeded max_distance_ratio limit "
                f"({max_distance:.4f}). Max angle ceiling reached with max_wedge_deg={max_wedge_deg}° "
                f"and max_distance_ratio={max_distance_ratio}, limiting min flex angle ceiling to {min_flex_ceiling:.2f}° "
                f"(requested {min_flex_deg:.2f}°)."
            )
            distance = max_distance
        distance = max(distance, min_distance)

    return MessagedResult((distance, angle), messages)


def _solve_membrane_wedge_deg(
        min_flex: float,
        membrane_thickness: float,
        min_height: float,
        tolerance: float = 1e-5,
        iterations: int = 50,
) -> MessagedResult[float]:
    wedge_rad, messages = _solve_membrane_wedge_rad(
        math.radians(min_flex),
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return MessagedResult(math.degrees(wedge_rad), messages)


def _solve_membrane_wedge_rad(
        min_flex: float,
        membrane_thickness: float,
        min_height: float,
        tolerance: float = 1e-5,
        iterations: int = 50,
) -> MessagedResult[float]:
    remain_rad, messages = _solve_membrane_wedge_remain_rad(
        min_flex,
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return MessagedResult(math.pi / 2 - remain_rad, messages)


def _solve_membrane_wedge_remain_rad(
        min_flex: float,
        membrane_thickness: float,
        min_height: float,
        tolerance: float = 1e-5,
        iterations: int = 50,
) -> MessagedResult[float]:
    """
        :solve:
            u: pi / 2 - wedge_angle
            w: max rotate angle introduced by membrane thickness
            2u - w = min_flex
            tan(w) = d / (h / sin(u))
        :return: in radians
        """
    assert min_height > 0 and membrane_thickness > 0

    k = membrane_thickness / min_height

    u = min_flex * 0.5
    f = 0.0
    for _ in range(iterations):
        w = 2.0 * u - min_flex
        cos_w = math.cos(w)
        assert abs(cos_w) >= tolerance, "Solver reached tan(w) singularity"

        f = math.tan(w) - k * math.sin(u)
        if abs(f) < tolerance:
            return MessagedResult(u)
        df = 2.0 / (cos_w * cos_w) - k * math.cos(u)
        assert abs(df) >= tolerance, "Derivative too small"
        u -= f / df

    msg = (
        f"Membrane wedge solver exhausted {iterations} iterations without converging to tolerance {tolerance:.2e} "
        f"(final residual: {abs(f):.4e}, min_flex: {math.degrees(min_flex):.2f}°, "
        f"membrane_thickness: {membrane_thickness:.4f}, min_height: {min_height:.4f})."
    )
    return MessagedResult(u, [msg])


def _solve_membrane_thickness_deg(
        needed_angle: float,
        min_height: float,
        wedge_angle: float,
) -> float:
    return _solve_membrane_thickness_rad(
        math.radians(needed_angle),
        min_height,
        math.radians(wedge_angle),
    )

def _solve_membrane_thickness_rad(
        needed_angle: float,
        min_height: float,
        wedge_angle: float,
) -> float:
    """
    :param needed_angle: in radians
    :param min_height:
    :param wedge_angle: in radians
    :return:
    """
    # d / tan(needed_angle) = l = min_height / cos(wedge_angle)
    return min_height / math.cos(wedge_angle) * math.tan(needed_angle)
