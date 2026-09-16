import math

import hou

from houkit.attributer import points_by_attrib
from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm
from houkit.topology import find_prim, loop_cut, merge_points, offset_point, traverse_faces_between_edges
from ..heads.attributes import headbasesupport, headchelicerae
from ..helper import (
    deduplicate_id_attr,
    inset_inner_prims,
    points_from_geo,
    points_from_loop_cut,
    set_points_id,
)
from .attributes import (
    bottom_middle,
    cheliceraeend,
    cheliceraeintermediate,
    cheliceraemembrane,
    cheliceraemiddle,
    cheliceraestart,
    cheliceraestartmembranesupport,
    upper_middle,
)


def remove_middle_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    membrane1, membrane6, support1, support2 = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(6),
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
    )
    middle_face = find_prim(membrane1, membrane6, support1, support2)
    geo.deletePrims([middle_face], keep_points=True)


def middle_loop_cut(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s2, s3 = points_from_geo(
        geo,
        cheliceraestart(2),
        cheliceraestart(3),
    )
    top_edge = geo.findEdge(s2, s3)
    assert top_edge is not None, "Expected top edge between cheliceraestart(2) and cheliceraestart(3)"
    added_points = points_from_loop_cut(loop_cut(top_edge.prims()[0], s2, s3, 1 / 3, use_ratio=True))
    cut_ids = [
        bottom_middle(cheliceraemembrane, 1),
        bottom_middle(cheliceraestartmembranesupport, 1),
        bottom_middle(cheliceraestart, 1),
        bottom_middle(cheliceraeintermediate, 1, j=0.25),
        bottom_middle(cheliceraemiddle, 1),
        bottom_middle(cheliceraeintermediate, 1, j=0.75),
        bottom_middle(cheliceraeend, 1),
        upper_middle(cheliceraeend, 1),
        upper_middle(cheliceraeintermediate, 1, j=0.75),
        upper_middle(cheliceraemiddle, 1),
        upper_middle(cheliceraeintermediate, 1, j=0.25),
        upper_middle(cheliceraestart, 1),
        upper_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraemembrane, 1),
    ]
    set_points_id(added_points, cut_ids)


def merge_membrane_curves(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m2, m5, top_cut, bottom_cut = points_from_geo(
        geo,
        cheliceraemembrane(2),
        cheliceraemembrane(5),
        upper_middle(cheliceraemembrane, 1),
        bottom_middle(cheliceraemembrane, 1),
    )
    merge_points([
        (m5, top_cut),
        (m2, bottom_cut),
    ])


def adjust_start_membrane_curve(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m2, m3, m4, m5, ss3, ss4, s3, s4 = points_from_geo(
        geo,
        cheliceraemembrane(2),
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraemembrane(5),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
        cheliceraestart(3),
        cheliceraestart(4),
    )
    upper_width = m4.position().distanceTo(ss3.position())
    bottom_width = m3.position().distanceTo(ss4.position())

    support_bottom_mid, support_upper_mid, start_bottom_mid, start_upper_mid = points_from_geo(
        geo,
        bottom_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraestartmembranesupport, 1),
        bottom_middle(cheliceraestart, 1),
        upper_middle(cheliceraestart, 1),
    )
    upper_offset = (
        (m5.position() - support_upper_mid.position()).normalized()
        * upper_width
        * 1/2
    )
    bottom_offset = (
        (m2.position() - support_bottom_mid.position()).normalized()
        * bottom_width
        * 1/2
    )

    for point in (support_upper_mid, start_upper_mid):
        offset_point(point, upper_offset)
    for point in (support_bottom_mid, start_bottom_mid):
        offset_point(point, bottom_offset)


def adjust_right_membrane_width(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m3, m4, ss3, ss4, s3, s4 = points_from_geo(
        geo,
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
        cheliceraestart(3),
        cheliceraestart(4),
    )
    upper_offset = (ss3.position() - m4.position()) * 0.5
    bottom_offset = (ss4.position() - m3.position()) * 0.5
    for point in (ss3, s3):
        offset_point(point, upper_offset)
    for point in (ss4, s4):
        offset_point(point, bottom_offset)


def adjust_head_chelicerae_depth(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    # h0: headchelicerae0, hs0: headbasesupport_headchelicerae0
    # c6: cheliceraemembrane6, cs6: cheliceraestartmembranesupport2
    h0, hs0, c6, cs6 = points_from_geo(
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
    offset_point(h0, dh * t)


def inset_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    support_prims = _get_chelicerae_support_strip_prims(geo)

    # Inset distance evaluated from the start membrane gap (1/3 of gap)
    start_membrane_support, start_point = points_from_geo(
        geo,
        cheliceraestartmembranesupport(2),
        cheliceraestart(2),
    )
    start_membrane_gap = start_membrane_support.position().distanceTo(start_point.position())
    dist = start_membrane_gap / 3.0
    inset_inner_prims(geo, support_prims, dist, use_ratio=False)

    _adjust_chelicerae_support_loop(node)
    deduplicate_id_attr(geo, None, keep_first=True)


def _get_chelicerae_support_strip_prims(geo: hou.Geometry) -> list[hou.Prim]:
    # Boundary vertices along the upper-medial edge (#2) of the chelicera tube
    medial_upper_points = points_from_geo(
        geo,
        headbasesupport(headchelicerae(0)),
        cheliceraeend(2),
    )
    # Opposing vertices along the upper-middle loop cut (#uppermiddle_1)
    upper_middle_points = points_from_geo(
        geo,
        headbasesupport(headchelicerae(1)),
        upper_middle(cheliceraeend, 1),
    )
    # Boundary vertices along the upper-lateral edge (#3) of the chelicera tube
    lateral_upper_points = points_from_geo(
        geo,
        headbasesupport(headchelicerae(2)),
        cheliceraeend(3),
    )
    side_points = points_from_geo(
        geo,
        headchelicerae(0),
        headchelicerae(2),
    )
    # Form the full upper quad strip (medial and lateral halves)
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
    return left_prims + right_prims


def _adjust_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    # This method adjusts the points position so the topology becomes more natural and smooth at certain places
    by_id = points_by_attrib(geo, "id", skip_blank=True)
    _adjust_right_chelicerae_support_points(by_id)
    _adjust_right_chelicerae_membrane_points(by_id)
    _adjust_left_chelicerae_support_points(by_id)
    _adjust_bottom_chelicerae_support_points(by_id)


def _adjust_right_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # For the right half support points, move them along 1/2 towards the upper middle line
    sections = (
        (headbasesupport(headchelicerae(2)), headbasesupport(headchelicerae(1))),
        (headchelicerae(2), headchelicerae(1)),
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

    for point in (inset_support3, inset_start3):
        offset_point(point, offset)


def _adjust_left_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # For the left half support points, new cuts at headbasesupport and headchelicerae are moved to 1/2
    sections = (
        (headbasesupport(headchelicerae(0)), headbasesupport(headchelicerae(1)), 0.0),
        (headchelicerae(0), headchelicerae(1), 0.0),
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
    return min(points_by_id[pt_id], key=lambda pt: pt.number())


def _get_inset_chelicerae_support_point(points_by_id: dict[str, set[hou.Point]], pt_id: str) -> hou.Point:
    return max(points_by_id[pt_id], key=lambda pt: pt.number())


def add_start_membrane_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    membrane, support = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraestartmembranesupport(1),
    )
    added = _add_support_loop(geo, ratio, membrane, support)
    _add_support_loop(geo, ratio, support, added[0])


def add_start_section_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    start, middle = points_from_geo(
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
    added_points = points_from_loop_cut(loop_cut(prim, start_point, end_point, ratio, use_ratio=True))
    return added_points
