import math

import hou

from base_sops import basemaxillamembrane
from helper import affix_id, point_from_geo, set_point_id
from leg_builder import LegParam, build_leg, Region
from utilities.common import (
    MessagedResult,
    fill_face,
    get_control,
    get_params,
    get_parent,
    rotation_to,
    add_global_attr,
)
from utilities.nodes import sopify


def _tmp_coxa_start(*i) -> str:
    return affix_id("tmp_pedipalpcoxastart", *i)
def _tmp_coxa_end(*i) -> str:
    return affix_id("tmp_pedipalpcoxaend", *i)
def _tmp_coxa_support(*i) -> str:
    return affix_id("tmp_pedipalpcoxasupport", *i)
def _tmp_coxa_corner(*i) -> str:
    return affix_id("tmp_pedipalpcoxacorner", *i)
def _tmp_coxa_base_height() -> str:
    return "tmp_coxabaseheight"


def prepare(
    geo: hou.Geometry
) -> set[hou.Point]:
    retained = point_from_geo(
        geo,
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        basemaxillamembrane(3),
        basemaxillamembrane(4),
    )
    return set(retained)


def build(
    parent: hou.SopNode,
    input_node: hou.SopNode,
) -> hou.SopNode:
    built_pedipalp = sopify(parent, input_node, _build_basic)
    positioned_pedipalp = sopify(parent, built_pedipalp, _position_basic)
    support_deleted_pedipalp = sopify(parent, positioned_pedipalp, _delete_start_coxa_supports)
    base_trapezoid = sopify(parent, support_deleted_pedipalp, _prepare_coxa_corners)
    bottom_right_face_filled = sopify(parent, base_trapezoid, _fill_bottom_right_face)
    back_filled = sopify(parent, bottom_right_face_filled, _fill_back_face)
    return back_filled


def _build_basic(
    node: hou.SopNode,
) -> None:
    _, warnings = _build_cubes(node)
    for w in warnings:
        node.addWarning(w)


def _position_basic(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    pedipalp_pts = _get_pedipalp_points(geo)
    top_right_pt, m1, m3, m4 = point_from_geo(
        geo,
        _tmp_coxa_start(3),
        basemaxillamembrane(1),
        basemaxillamembrane(3),
        basemaxillamembrane(4),
    )

    v = m3.position() - m1.position()
    direction = hou.Vector3(v.x(), 0.0, v.z()).normalized()
    q = rotation_to(hou.Vector3(0.0, 0.0, -1.0), direction)

    origin = m4.position() - q.rotate(top_right_pt.position())
    for pt in pedipalp_pts:
        pt.setPosition(q.rotate(pt.position()) + origin)


def _delete_start_coxa_supports(
    node: hou.SopNode,
) -> None:
    geo: hou.Geometry = node.geometry()
    pts = [p for p in geo.points() if p.stringAttribValue("id").startswith(_tmp_coxa_support(1))]
    geo.deletePoints(list(pts))

    starts = point_from_geo(
        geo,
        _tmp_coxa_start(1),
        _tmp_coxa_start(2),
        _tmp_coxa_start(4),
    )
    geo.deletePoints(list(starts))


def _prepare_coxa_corners(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    dist = _add_base_trapezoid(geo)
    _add_base_corner_point(geo, dist)

def _add_base_corner_point(
        geo: hou.Geometry,
        dist: float,
) -> None:
    s3, e3, m1 = point_from_geo(
        geo,
        _tmp_coxa_start(3),
        _tmp_coxa_end(3),
        basemaxillamembrane(1),
    )
    d = (e3.position() - s3.position()).normalized()
    pos = m1.position() + d * dist
    p = geo.createPoint()
    p.setPosition(pos)
    set_point_id(p, _tmp_coxa_corner(3))

def _add_base_trapezoid(
    geo: hou.Geometry
) -> float:
    m1, m2, m4 = point_from_geo(
        geo,
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        basemaxillamembrane(4),
    )
    neg_z = hou.Vector3(0.0, 0.0, -1.0)

    n_socket = (m2.position() - m1.position()).cross(m4.position() - m1.position()).normalized()
    if n_socket.dot(neg_z) < 0:
        n_socket = -n_socket

    pos_m1 = m1.position()
    pos_m2 = m2.position()
    edge = pos_m2 - pos_m1
    length = edge.length()
    u = edge.normalized()

    n = hou.Quaternion(45.0, u).rotate(n_socket)
    v = n.cross(u).normalized()

    height = math.sqrt(3) / 4.0 * length
    pos_p3 = pos_m1 + u * (0.75 * length) + v * height
    pos_p4 = pos_m1 + u * (0.25 * length) + v * height

    p3 = geo.createPoint()
    p3.setPosition(pos_p3)
    set_point_id(p3, _tmp_coxa_corner(1))
    p4 = geo.createPoint()
    p4.setPosition(pos_p4)
    set_point_id(p4, _tmp_coxa_corner(2))

    fill_face(geo, [m1, m2, p3, p4], reverse=True)
    add_global_attr(geo, _tmp_coxa_base_height(), height)

    return height


def _fill_bottom_right_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    c4, c5 = _add_bottom_right_face_point(geo)
    es4, c2, c3, m1 = point_from_geo(
        geo,
        _tmp_coxa_support(2, 4),
        _tmp_coxa_corner(2),
        _tmp_coxa_corner(3),
        basemaxillamembrane(1),
    )
    fill_face(geo, [es4, c4, c3, c5])
    fill_face(geo, [c4, c3, m1, c2], True)

def _add_bottom_right_face_point(geo: hou.Geometry) -> tuple[hou.Point, hou.Point]:
    dist = geo.attribValue(_tmp_coxa_base_height())
    e1, e4= point_from_geo(
        geo,
        _tmp_coxa_end(1),
        _tmp_coxa_end(4),
    )

    direction = _get_coxa_direction(geo)

    start_position = e1.position() * 1 / 3 + e4.position() * 2 / 3
    target_position = start_position + direction * dist
    p1 = geo.createPoint()
    p1.setPosition(target_position)
    set_point_id(p1, _tmp_coxa_corner(4))

    start_position = e4.position()
    target_position = start_position + direction * dist
    p2 = geo.createPoint()
    p2.setPosition(target_position)
    set_point_id(p2, _tmp_coxa_corner(5))

    return p1, p2


def _fill_back_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s3, es3, es4, c5, c3, m1 = point_from_geo(
        geo,
        _tmp_coxa_start(3),
        _tmp_coxa_support(2, 3),
        _tmp_coxa_support(2, 4),
        _tmp_coxa_corner(5),
        _tmp_coxa_corner(3),
        basemaxillamembrane(1),
    )
    fill_face(geo, [es3, es4, c5, s3])
    fill_face(geo, [s3, c5, c3, m1])


def _build_cubes(
    node: hou.SopNode,
) -> MessagedResult[tuple[list[hou.Point], list[hou.Point], list[hou.Point]]]:
    geo = node.geometry()
    param = _get_pedipalp_param(node)
    result = build_leg(geo, param)
    (all_seg_pts, _, _), _ = result

    def _get_ordered_loop(index: int) -> tuple[hou.Point, ...]:
        return all_seg_pts[index * 4 + 3], all_seg_pts[index * 4 + 1], all_seg_pts[index * 4 + 0], all_seg_pts[index * 4 + 2]

    # 1: Bottom left, 2: Top left, 3: Top right, 4: Bottom right
    start_corners = _get_ordered_loop(0)
    end_corners = _get_ordered_loop(3)
    start_support_corners = _get_ordered_loop(1)
    end_support_corners = _get_ordered_loop(2)
    for i, (s_pt, e_pt, ss_pt, es_pt) in enumerate(
        zip(start_corners, end_corners, start_support_corners, end_support_corners),
        start=1
    ):
        set_point_id(s_pt, _tmp_coxa_start(i))
        set_point_id(e_pt, _tmp_coxa_end(i))
        set_point_id(ss_pt, _tmp_coxa_support(1, i))
        set_point_id(es_pt, _tmp_coxa_support(2, i))

    return result

def _get_pedipalp_param(
    node: hou.SopNode,
) -> LegParam:
    geo = node.geometry()
    leg = get_parent(node)

    params = get_params(leg, use_tuple=False)
    control_params = get_params(get_control(leg), use_tuple=False)

    coxa_size = _get_pedipalp_coxa_size(
        geo,
        params.front_coxa_size_ratio,
    )
    length_ratios = tuple(params.pedipalp_segment_length_ratios)
    segment_specs = tuple(zip(params.max_segment_yaws[1:], params.min_segment_flexes[1:]))[:len(length_ratios)]

    return LegParam(
        coxa_size=coxa_size,
        length_ratios=length_ratios,
        yaw_flex_specs=segment_specs,
        height_ratio=control_params.segment_height_ratio,
        spine_ratio=control_params.segment_lateral_ratio,
        shrink_ratios=control_params.segment_shrink_ratios,
        minimum_membrane=control_params.minimum_membrane_spec,
        support_loop_ratio=control_params.support_loop_ratio,
        tarsus_wedge_angle=control_params.tarsus_wedge_angle,
    )

def _get_pedipalp_coxa_size(
    geo: hou.Geometry,
    front_coxa_size_ratio: hou.Vector2,
) -> tuple[float, float, float]:
    m3, m4 = point_from_geo(geo, basemaxillamembrane(3), basemaxillamembrane(4))
    width = m3.position().distanceTo(m4.position())
    height = width
    length = front_coxa_size_ratio.y() / front_coxa_size_ratio.x() * width
    return width, height, length


def _get_pedipalp_points(
    geo: hou.Geometry,
) -> list[hou.Point]:
    pts = {
        pt
        for prim in geo.prims()
        if prim.stringAttribValue("region").startswith((Region.LEGMEMBRANE, Region.LEGSEGMENT))
        for pt in prim.points()
    }
    if not pts:
        return list(geo.points())
    return list(pts)


def _get_coxa_direction(geo: hou.Geometry) -> hou.Vector3:
    es4, c3 = point_from_geo(
        geo,
        _tmp_coxa_support(2, 4),
        _tmp_coxa_corner(3),
    )
    return (c3.position() - es4.position()).normalized()