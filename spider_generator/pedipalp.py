import math

import hou

from .base_sops import basemaxillamembrane
from .helper import add_id_point, affix_id, point_from_geo, position_from_geo, prims_by_attr, set_point_id, sopify_chain
from .leg_builder import LegParam, build_leg, Region
from utilities.common import (
    MessagedResult,
    fill_face,
    get_control,
    get_params,
    get_parent,
    rotation_to,
    add_global_attr,
    add_heading,
    add_float_param,
    get_float_parm,
    points_by_attr,
    remove_attrs,
    points_start_with,
)
from utilities.nodes import (
    add_fuse,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import edge_point_on_face


def _tmp_coxa_start(*i) -> str:
    return affix_id("tmp_pedipalpcoxastart", *i)
def _tmp_coxa_end(*i) -> str:
    return affix_id("tmp_pedipalpcoxaend", *i)
def _tmp_coxa_support(*i) -> str:
    return affix_id("tmp_pedipalpcoxasupport", *i)
def _tmp_coxa_corner(*i) -> str:
    return affix_id("tmp_pedipalpcoxacorner", *i)
def _tmp_coxa_base_height() -> str:
    return "tmp_maxillabaseheight"
def _tmp_maxilla_pole(*i) -> str:
    return affix_id("tmp_maxillapole", *i)


def add_parameters(subnet: hou.OpNode) -> None:
    add_heading(
        subnet,
        "Pedipalp",
    )
    add_float_param(
        subnet,
        "pedipalp_segment_length_ratios",
        5,
        (0.8, 3.75, 3, 2.5, 1.5),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Pedipalp Lengths",
        help="One length ratio per post-coxa pedipalp segment, measured against pedipalp coxa length.",
    )
    add_float_param(
        subnet,
        "endite_length_ratio",
        default=1.0,
        min_max=(0.0, None),
        label="Endite Length",
        help="Extension from the endite membrane attachment toward the coxa.",
    )


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
    pedipalp = add_reloadable_subnet(parent, "pedipalp")
    pedipalp.setInput(0, input_node)
    _add_controls(pedipalp)

    cleaned_up = sopify_chain(
        pedipalp,
        pedipalp.indirectInputs()[0],
        (
            _remove_noise_points,
            _build_basic,
            _position_basic,
            _delete_start_coxa_supports,
            _prepare_coxa_corners,
            _fill_bottom_right_face,
            _fill_back_face,
            _fill_top_face,
            _add_front_upper_face,
            _add_front_loop_faces,
            _add_maxilla_quads,
            _fill_maxilla_faces,
            _remove_tmp_attributes,
        ),
    )
    fused = add_fuse(pedipalp, "fuse_sockets", cleaned_up)
    add_output(pedipalp, "OUT_PEDIPALP", fused)
    pedipalp.layoutChildren()
    return pedipalp


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_param(
        control,
        "endite_buffer_ratios",
        size=2,
        default=(0.2, 0.2),
        min_max=(0.0, 1.0),
        label="Endite Buffer",
        help="X positions the buffer across the coxa end; Y sets its lengthwise reach.",
    )
    add_float_param(
        control,
        "endite_surface_size_ratio",
        default=0.1,
        min_max=(0.0, 1.0),
        label="Endite Surface Size",
        help="Size of the added endite surface faces.",
    )
    return control


def _remove_noise_points(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    pts = points_by_attr(geo, "id", False)
    geo.deletePoints(list(pts[""]))


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
    _add_base_trapezoid(geo)


def _fill_bottom_right_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_params(get_control(node), use_tuple=False)
    c4 = _add_bottom_right_face_point(geo, control_params.endite_buffer_ratios)
    es4, c2, m1 = point_from_geo(
        geo,
        _tmp_coxa_support(2, 4),
        _tmp_coxa_corner("base", 2),
        basemaxillamembrane(1),
    )
    fill_face(geo, [es4, c4, c2, m1])

def _add_bottom_right_face_point(
    geo: hou.Geometry,
    endite_buffer: hou.Vector2,
) -> hou.Point:
    e1, e4, m1 = point_from_geo(
        geo,
        _tmp_coxa_end(1),
        _tmp_coxa_end(4),
        basemaxillamembrane(1),
    )

    direction = _get_coxa_direction(geo)

    start_position = e1.position() * endite_buffer.x() + e4.position() * (1.0 - endite_buffer.x())
    dist = _get_buffer_dist_z(geo, endite_buffer.y())
    target_position = start_position + direction * dist
    p = add_id_point(geo, target_position, _tmp_coxa_corner("bottom"))
    return p


def _fill_back_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s3, es3, es4, m1 = point_from_geo(
        geo,
        _tmp_coxa_start(3),
        _tmp_coxa_support(2, 3),
        _tmp_coxa_support(2, 4),
        basemaxillamembrane(1),
    )
    fill_face(geo, [es3, es4, m1, s3])


def _fill_top_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    dist = geo.attribValue(_tmp_coxa_base_height())
    direction = _get_coxa_direction(geo)

    e2, m2, m3, m4, es2, es3 = point_from_geo(
        geo,
        _tmp_coxa_end(2),
        basemaxillamembrane(2),
        basemaxillamembrane(3),
        basemaxillamembrane(4),
        _tmp_coxa_support(2, 2),
        _tmp_coxa_support(2, 3)
    )

    pos = e2.position() + direction * dist
    c6 = add_id_point(geo, pos, _tmp_coxa_corner("fronttop"))

    fill_face(geo, [es3, m4, c6, es2])
    fill_face(geo, [m4, m3, m2, c6])


def _add_maxilla_quads(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_params(get_control(node), use_tuple=False)
    pos = _get_maxilla_pole(node)
    normal = _get_averaged_maxilla_quad_normal(geo, pos)
    _add_maxilla_quads_to_geo(geo, pos, normal, control_params.endite_surface_size_ratio)

def _get_maxilla_pole(node: hou.SopNode) -> hou.Vector3:
    geo: hou.Geometry = node.geometry()
    leg = get_leg(node)
    length_ratio = get_float_parm(leg, "endite_length_ratio")

    e1, e2, e3, es3, m2, ct2 = point_from_geo(
        geo,
        _tmp_coxa_end(1),
        _tmp_coxa_end(2),
        _tmp_coxa_end(3),
        _tmp_coxa_support(2, 3),
        basemaxillamembrane(2),
        _tmp_coxa_corner("base", 2)
    )
    direction = e3.position()- es3.position()

    m2_pos = m2.position()
    hit = edge_point_on_face(
        (m2_pos, m2_pos + direction * 100),
        (e1.position(), e2.position(), e3.position()),
    )
    assert hit is not None
    start_pos = m2_pos + (hit - m2_pos) * length_ratio

    v1 = ct2.position() - start_pos
    v2 = (e1.position() - e2.position()).normalized()
    end_pos = start_pos + v2 * v1.dot(v2)
    return end_pos

def _get_averaged_maxilla_quad_normal(geo: hou.Geometry, target: hou.Vector3) -> hou.Vector3:
    pts = point_from_geo(
        geo,
        _tmp_coxa_corner("front"),
        basemaxillamembrane(2),
        _tmp_coxa_corner("base", 2),
        _tmp_coxa_corner("base", 1),
        _tmp_coxa_corner("bottom"),
        _tmp_coxa_corner("frontbottom"),
    )

    total = hou.Vector3()
    for p in pts:
        v = (target - p.position()).normalized()
        total += v
    return total.normalized()

def _add_maxilla_quads_to_geo(
        geo: hou.Geometry,
        center: hou.Vector3,
        normal: hou.Vector3,
        flat_ratio: float,
) -> list[hou.Point]:
    ct2, cb, m2 = point_from_geo(
        geo,
        _tmp_coxa_corner("base", 2),
        _tmp_coxa_corner("bottom"),
        basemaxillamembrane(2),
    )

    l = ct2.position().distanceTo(center) * flat_ratio
    h = l * 0.5

    u = (cb.position() - m2.position()).normalized()
    u = hou.Vector3(u.x(), 0, u.z()).normalized()
    v = normal.cross(u).normalized()

    p0 = center + (-u - v) * h
    p1 = center + (u - v) * h
    p2 = center + (u + v) * h
    p3 = center + (-u + v) * h
    p4 = (p0 + p3) * 0.5
    p5 = (p1 + p2) * 0.5

    poses = [p0, p1, p2, p3, p4, p5]
    pts = []
    for i, p in enumerate(poses, start=1):
        p = add_id_point(geo, p, _tmp_maxilla_pole(i))
        pts.append(p)

    fill_face(geo, [pts[0], pts[1], pts[5], pts[4]], True)
    fill_face(geo, [pts[5], pts[4], pts[3], pts[2]])

    return pts


def _add_front_upper_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_params(get_control(node), use_tuple=False)
    p = _add_front_face_point(geo, control_params.endite_buffer_ratios)
    es2, c6, m2 = point_from_geo(
        geo,
        _tmp_coxa_support(2, 2),
        _tmp_coxa_corner("fronttop"),
        basemaxillamembrane(2),
    )
    fill_face(geo, [es2, c6, m2, p])

def _add_front_face_point(
    geo: hou.Geometry,
    endite_buffer: hou.Vector2,
) -> hou.Point:
    e1, e2 = point_from_geo(
        geo,
        _tmp_coxa_end(1),
        _tmp_coxa_end(2),
    )
    dist = _get_buffer_dist_z(geo, endite_buffer.y())
    direction = _get_coxa_direction(geo)
    start = e1.position() * endite_buffer.x() + e2.position() * (1.0 - endite_buffer.x())
    target = start + direction * dist
    return add_id_point(geo, target, _tmp_coxa_corner("front"))


def _add_front_loop_faces(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_params(get_control(node), use_tuple=False)
    p = _add_loop_point(geo, control_params.endite_buffer_ratios.y())
    es1, es2, es4, cf, cb = point_from_geo(
        geo,
        _tmp_coxa_support(2, 1),
        _tmp_coxa_support(2, 2),
        _tmp_coxa_support(2, 4),
        _tmp_coxa_corner("front"),
        _tmp_coxa_corner("bottom"),
    )
    fill_face(geo, [es2, cf, p, es1])
    fill_face(geo, [es1, p, cb, es4])

def _add_loop_point(
    geo: hou.Geometry,
    endite_buffer_y: float,
) -> hou.Point:
    e1, = point_from_geo(
        geo,
        _tmp_coxa_end(1),
    )
    dist = _get_buffer_dist_z(geo, endite_buffer_y)
    direction = _get_coxa_direction(geo)
    target = e1.position() + direction * dist
    return add_id_point(geo, target, _tmp_coxa_corner("frontbottom"))


def _fill_maxilla_faces(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    cf, cfb, cb, ct2, ct1, m2 = point_from_geo(
        geo,
        _tmp_coxa_corner("front"),
        _tmp_coxa_corner("frontbottom"),
        _tmp_coxa_corner("bottom"),
        _tmp_coxa_corner("base", 2),
        _tmp_coxa_corner("base", 1),
        basemaxillamembrane(2),
    )
    p0, p1, p2, p3, p4, p5 = point_from_geo(
        geo,
        *[_tmp_maxilla_pole(i + 1) for i in range(6)],
    )
    fill_face(geo, [p0, m2, ct1, p4])
    fill_face(geo, [p4, ct1, ct2, p3])
    fill_face(geo, [p3, ct2, cb, p2])
    fill_face(geo, [p2, cb, cfb, p5])
    fill_face(geo, [p5, cfb, cf, p1])
    fill_face(geo, [p1, cf, m2, p0])


def _remove_tmp_attributes(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    pts = points_start_with(geo, "id", "tmp_")
    for p in pts:
        set_point_id(p, "")



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
    leg = get_leg(node)

    params = get_params(leg, use_tuple=False)
    control_params = get_params(get_control(leg), use_tuple=False)

    coxa_size = _get_pedipalp_coxa_size(
        geo,
        params.front_coxa_width_length_ratios,
    )
    length_ratios = tuple(params.pedipalp_segment_length_ratios)
    max_segment_yaws = tuple(params.max_yaw_angles)[:len(length_ratios)]
    min_segment_flexes = tuple(params.min_flex_angles)[:len(length_ratios)]

    return LegParam.from_specs(
        coxa_size=coxa_size,
        length_ratios=length_ratios,
        max_segment_yaws=max_segment_yaws,
        min_segment_flexes=min_segment_flexes,
        height_ratio=control_params.segment_height_ratio,
        spine_ratio=control_params.segment_bulge_bias_ratio,
        shrink_ratios=control_params.segment_taper_ratios,
        minimum_membrane=control_params.joint_clearance_limits,
        support_loop_ratio=control_params.joint_support_loop_ratio,
        tarsus_wedge_angle=control_params.tarsus_wedge_angle,
    )

def _get_pedipalp_coxa_size(
    geo: hou.Geometry,
    front_coxa_size_ratio: hou.Vector2,
) -> tuple[float, float, float]:
    m3, m4 = position_from_geo(geo, basemaxillamembrane(3), basemaxillamembrane(4))
    width = m3.distanceTo(m4)
    height = width
    length = front_coxa_size_ratio.y() / front_coxa_size_ratio.x() * width
    return width, height, length

def _get_pedipalp_points(
    geo: hou.Geometry,
) -> list[hou.Point]:
    pts = {pt for prim in prims_by_attr(geo, "region", (Region.LEGMEMBRANE, Region.LEGSEGMENT), startswith=True) for pt in prim.points()}
    if not pts:
        return list(geo.points())
    return list(pts)



def _add_base_corner_point(
        geo: hou.Geometry,
        dist: float,
) -> None:
    """
    Legacy method
    :param geo:
    :param dist:
    :return:
    """
    s3, e3, m1 = point_from_geo(
        geo,
        _tmp_coxa_start(3),
        _tmp_coxa_end(3),
        basemaxillamembrane(1),
    )
    d = (e3.position() - s3.position()).normalized()
    pos = m1.position() + d * dist
    p = add_id_point(geo, pos, _tmp_coxa_corner(3))

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

    p3 = add_id_point(geo, pos_p3, _tmp_coxa_corner("base", 1))
    p4 = add_id_point(geo, pos_p4, _tmp_coxa_corner("base", 2))

    fill_face(geo, [m1, m2, p3, p4], reverse=True)
    add_global_attr(geo, _tmp_coxa_base_height(), height)

    return height



def _get_coxa_direction(geo: hou.Geometry) -> hou.Vector3:
    es3, e3 = point_from_geo(
        geo,
        _tmp_coxa_support(2, 3),
        _tmp_coxa_end(3),
    )
    return (es3.position() - e3.position()).normalized()


def _get_buffer_dist_z(geo: hou.Geometry, endite_buffer_y: float) -> float:
    e1, m1 = position_from_geo(
        geo,
        _tmp_coxa_end(1),
        basemaxillamembrane(1),
    )
    return e1.distanceTo(m1) * endite_buffer_y


def get_leg(node: hou.Node) -> hou.OpNode:
    subnet = node if node.isSubNetwork() else get_parent(node)
    return get_parent(subnet)
