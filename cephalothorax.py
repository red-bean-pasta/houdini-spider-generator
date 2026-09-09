import math

import hou

import base_sops
from base import build as build_base
from chelicerae import (
    build as build_chelicerae,
    cheliceraeend,
    cheliceraemembrane,
    cheliceraemiddle,
    cheliceraestart,
    cheliceraestartmembranesupport,
    cheliceraeintermediate,
    upper_middle,
)
from head import build as build_head, headbasesupport, headchelicerae
from helper import deduplicate_id_attr, point_from_geo
from utilities.common import (
    add_float_param,
    get_float_parm,
    get_parent,
    points_by_attr,
)
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_output,
    add_outside_recalculation,
    add_reloadable_subnet,
    propagate_parameters,
    sopify,
)
from utilities.topology import inset, loop_cut, traverse_faces_between_edges


def build(spider: hou.OpNode) -> hou.SopNode:
    cephalothorax = add_reloadable_subnet(spider, "cephalothorax")
    _add_parameters(cephalothorax)

    base = build_base(cephalothorax)
    _link_membrane_ratio(cephalothorax, base)

    head = build_head(cephalothorax, base)
    _link_membrane_ratio(cephalothorax, head)

    b_h_merge = add_merge(cephalothorax, "merge_base_and_head", base, head)
    b_h_fuse = add_fuse(cephalothorax, "fuse_base_and_head", b_h_merge)

    chelicerae = build_chelicerae(cephalothorax, b_h_fuse)
    _link_membrane_ratio(cephalothorax, chelicerae)

    all_merge = add_merge(cephalothorax, "merge_head_and_chelicerae", b_h_fuse, chelicerae)
    all_fuse = add_fuse(cephalothorax, "fuse_head_and_chelicerae", all_merge)

    upper_inset = sopify(cephalothorax, all_fuse, _inset_chelicerae_support_loop)
    clamped_membrane = sopify(cephalothorax, upper_inset, _add_start_membrane_support_loops)
    clamped_start = sopify(cephalothorax, clamped_membrane, _add_start_section_support_loops)
    adjusted = sopify(cephalothorax, clamped_start, _adjust_head_chelicerae_depth)

    recalculate = add_outside_recalculation(cephalothorax, "recalculate_normals", adjusted)
    positioned = _position_cephalothorax(cephalothorax, recalculate)

    _ = add_output(cephalothorax, "OUT_CEPHALOTHORAX", positioned)

    cephalothorax.layoutChildren()
    return cephalothorax


def _add_parameters(cephalothorax: hou.SopNode) -> None:
    add_float_param(
        cephalothorax,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )


def _link_membrane_ratio(parent: hou.SopNode, child: hou.SopNode) -> None:
    propagate_parameters(parent, child, skip_params="membrane_ratio")
    child.parm("membrane_ratio").set(parent.parm("membrane_ratio"))


def _position_cephalothorax(parent: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    position = parent.createNode("xform", "position_cephalothorax")
    position.setInput(0, source)
    pattern = f'pointpattern(0, "@id={base_sops.baseend(0)}")'
    for axis_index, axis_name in enumerate(("tx", "ty", "tz")):
        position.parm(axis_name).setExpression(f'0 - point(0, {pattern}, "P", {axis_index})')
    return position


def _adjust_head_chelicerae_depth(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    # h0: headchelicerae0, hs0: headbasesupport_headchelicerae0
    # c6: cheliceraemembrane6, cs6: cheliceraestartmembranesupport2
    h0, hs0, c6, cs6 = point_from_geo(
        geo,
        headchelicerae(0),
        headbasesupport(headchelicerae(0)),
        cheliceraemembrane(6),
        cheliceraestartmembranesupport(2),
    )
    for pt in (h0, hs0, c6, cs6):
        assert abs(pt.position().x()) < 1e-4

    dh = (h0.position() - hs0.position()).normalized()
    dc = (cs6.position() - c6.position()).normalized()

    v0 = h0.position() - c6.position()
    v_perp = (v0 - dc * v0.dot(dc)).normalized()
    angle = math.radians(10)
    d_target = dc * math.cos(angle) + v_perp * math.sin(angle)

    denom = (d_target.cross(dh)).x()
    assert abs(denom) > 1e-6, "Target direction and head direction are nearly parallel"
    t = (v0.cross(d_target)).x() / denom
    h0.setPosition(h0.position() + dh * t)


def _inset_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    # Boundary vertices along the upper-medial edge (#2) of the chelicera tube
    medial_upper_points = point_from_geo(
        geo,
        cheliceraemembrane(6),
        cheliceraeend(2),
    )
    # Opposing vertices along the upper-middle loop cut (#uppermiddle_1)
    upper_middle_points = point_from_geo(
        geo,
        cheliceraemembrane(5),
        upper_middle(cheliceraeend, 1),
    )
    # Boundary vertices along the upper-lateral edge (#3) of the chelicera tube
    lateral_upper_points = point_from_geo(
        geo,
        cheliceraemembrane(4),
        cheliceraeend(3),
    )
    side_points = point_from_geo(
        geo,
        cheliceraestartmembranesupport(2),
        cheliceraestartmembranesupport(3),
    )
    # Form the full upper quad strip (medial and lateral halves) from start membrane to end section
    left_prims = [
        prim
        for prim in traverse_faces_between_edges(
            (medial_upper_points[0], upper_middle_points[0]),
            (medial_upper_points[1], upper_middle_points[1]),
            side_points[0],
        )
    ]
    right_prims = [
        prim
        for prim in traverse_faces_between_edges(
            (lateral_upper_points[0], upper_middle_points[0]),
            (lateral_upper_points[1], upper_middle_points[1]),
            side_points[1],
        )
    ]

    # Inset distance evaluated from the start membrane gap (1/3 of gap)
    start_membrane_support, start_point = point_from_geo(
        geo,
        cheliceraestartmembranesupport(2),
        cheliceraestart(2),
    )
    start_membrane_gap = start_membrane_support.position().distanceTo(start_point.position())
    dist = start_membrane_gap / 3.0
    inset(left_prims + right_prims, dist, use_ratio=False)

    _adjust_chelicerae_support_loop(node)

    deduplicate_id_attr(geo, None, keep_first=True)

def _adjust_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    # This method adjusts the points position so the topology becomes more natural and smooth at certain places
    by_id = points_by_attr(geo, "id", skip_blank=True)
    _adjust_right_chelicerae_support_points(by_id)
    _adjust_right_chelicerae_membrane_points(by_id)
    _adjust_left_chelicerae_support_points(by_id)
    _adjust_bottom_chelicerae_support_points(by_id)

def _adjust_right_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # For the right half support points, move them along 1/2 towards the upper middle line
    sections = (
        (cheliceraemembrane(4), cheliceraemembrane(5)),
        (cheliceraestartmembranesupport(3), upper_middle(cheliceraestartmembranesupport, 1)),
        (cheliceraestart(3), upper_middle(cheliceraestart, 1)),
        (cheliceraeintermediate(0.25, 3), upper_middle(cheliceraeintermediate, 1, j=0.25)),
        (cheliceraemiddle(3), upper_middle(cheliceraemiddle, 1)),
        (cheliceraeintermediate(0.75, 3), upper_middle(cheliceraeintermediate, 1, j=0.75)),
        (cheliceraeend(3), upper_middle(cheliceraeend, 1)),
    )
    for support_id, mid_id in sections:
        inset_support = _get_inset_chelicerae_support_point(points_by_id, support_id)
        inset_mid = _get_inset_chelicerae_support_point(points_by_id, mid_id)
        inset_support.setPosition((inset_support.position() + inset_mid.position()) * 0.5)

def _adjust_right_chelicerae_membrane_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # for inset_cheliceraestartmambranesupport3
    # move it along inset_cheliceraestartmambranesupport3-inset_cheliceraemembrane4
    # so that it's y is at 1/4 of the y_offset of cheliceraestartmambranesupport_uppermiddle1-cheliceraestartmambranesupport3
    # apply the same offset to inset_cheliceraestart3
    inset_support3 = _get_inset_chelicerae_support_point(points_by_id, cheliceraestartmembranesupport(3))
    inset_membrane4 = _get_inset_chelicerae_support_point(points_by_id, cheliceraemembrane(4))
    inset_start3 = _get_inset_chelicerae_support_point(points_by_id, cheliceraestart(3))

    support3 = _get_original_chelicerae_point(points_by_id, cheliceraestartmembranesupport(3))
    support_uppermid = _get_original_chelicerae_point(points_by_id, upper_middle(cheliceraestartmembranesupport, 1))

    target_y = (
       support_uppermid.position().y() * 3/4
       + support3.position().y() * 1/4
    )
    direction = inset_support3.position() - inset_membrane4.position()
    assert abs(direction.y()) > 1e-6, "Expected non-zero y component in direction"
    offset = direction * ((target_y - inset_support3.position().y()) / direction.y())

    inset_support3.setPosition(inset_support3.position() + offset)
    inset_start3.setPosition(inset_start3.position() + offset)

def _adjust_left_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # For the left half support points, cheliceraemembrane(6), cheliceraestartmembranesupport(2),
    # and cheliceraestart(2) are kept at 0, tmpsection 0.25 is moved by 1/4, and the rest to 1/2
    sections = (
        (cheliceraemembrane(6), cheliceraemembrane(5), 0.0),
        (cheliceraestartmembranesupport(2), upper_middle(cheliceraestartmembranesupport, 1), 0.0),
        (cheliceraestart(2), upper_middle(cheliceraestart, 1), 0.0),
        (cheliceraeintermediate(0.25, 2), upper_middle(cheliceraeintermediate, 1, j=0.25), 0.25),
        (cheliceraemiddle(2), upper_middle(cheliceraemiddle, 1), 0.5),
        (cheliceraeintermediate(0.75, 2), upper_middle(cheliceraeintermediate, 1, j=0.75), 0.5),
        (cheliceraeend(2), upper_middle(cheliceraeend, 1), 0.5),
    )
    for support_id, mid_id, ratio in sections:
        if ratio == 0.0:
            continue
        inset_support = _get_inset_chelicerae_support_point(points_by_id, support_id)
        inset_mid = _get_inset_chelicerae_support_point(points_by_id, mid_id)
        inset_support.setPosition(inset_support.position() * (1.0 - ratio) + inset_mid.position() * ratio)

def _adjust_bottom_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    sections = (
        (cheliceraeend(2), cheliceraeintermediate(0.75, 2)),
        (upper_middle(cheliceraeend, 1), upper_middle(cheliceraeintermediate, 1, j=0.75)),
        (cheliceraeend(3), cheliceraeintermediate(0.75, 3)),
    )
    for end_id, section_id in sections:
        inset_end = _get_inset_chelicerae_support_point(points_by_id, end_id)
        inset_section = _get_inset_chelicerae_support_point(points_by_id, section_id)
        inset_end.setPosition((inset_end.position() + inset_section.position()) * 0.5)

def _get_original_chelicerae_point(points_by_id: dict[str, set[hou.Point]], pt_id: str) -> hou.Point:
    matches = points_by_id[pt_id]
    return min(matches, key=lambda pt: pt.number())

def _get_inset_chelicerae_support_point(points_by_id: dict[str, set[hou.Point]], pt_id: str) -> hou.Point:
    matches = points_by_id[pt_id]
    return max(matches, key=lambda pt: pt.number())


def _add_start_membrane_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    membrane, support = point_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraestartmembranesupport(1),
    )
    _add_support_loop(geo, ratio, support, membrane)


def _add_start_section_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    start, middle = point_from_geo(
        geo,
        cheliceraestart(2),
        cheliceraeintermediate(0.25, 2),
    )
    _add_support_loop(geo, ratio, start, middle)

def _add_support_loop(
    geo: hou.Geometry,
    ratio: float,
    start_point: hou.Point,
    end_point: hou.Point,
) -> list[hou.Point]:
    edge = geo.findEdge(start_point, end_point)
    assert edge is not None, "Expected start membrane support edge"
    prim = edge.prims()[0]
    added_points, _ = loop_cut(prim, start_point, end_point, ratio, use_ratio=True)
    return added_points
