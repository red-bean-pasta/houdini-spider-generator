import hou

from ...bases.attributes import basemaxillamembrane
from ...helper import add_id_point, points_from_geo, positions_from_geo, prims_by_attr, set_point_id
from houkit.attributer import add_global_attrib, points_by_attrib, points_start_with, remove_attribs
from houkit.geomath import rotation_to
from houkit.models import Moject
from houkit.noder import get_control
from houkit.parameterizer import get_float_parm, get_parms
from houkit.topology import fill_face
from ..attributes import LegParam, Region
from ..cubes import build_leg
from .attributes import tmp_coxa_base_height, tmp_coxa_corner, tmp_coxa_end, tmp_coxa_start, tmp_coxa_support, tmp_front_socket_width
from .helper import get_leg


def remove_noise_points(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    from ..coxa import get_front_coxa_socket_size
    front_socket_width, _ = get_front_coxa_socket_size(geo)
    add_global_attrib(geo, tmp_front_socket_width(), front_socket_width)
    pts = points_by_attrib(geo, "id", False)
    geo.deletePoints(list(pts[""]))


def build_basic(
    node: hou.SopNode,
) -> None:
    _, warnings = _build_cubes(node)
    for w in warnings:
        node.addWarning(w)


def trim_bottom_side_length(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    m1, m3 = points_from_geo(
        geo,
        basemaxillamembrane(1),
        basemaxillamembrane(3),
    )
    v = m3.position() - m1.position()
    trim_length = hou.Vector3(v.x(), 0.0, v.z()).length()

    pedipalp_pts = _get_pedipalp_points(geo)
    for pt in pedipalp_pts:
        pid = pt.stringAttribValue("id")
        if pid.startswith(tmp_coxa_start()) or pid.startswith(tmp_coxa_support(1)):
            continue
        pos = pt.position()
        pt.setPosition(hou.Vector3(pos.x(), pos.y(), pos.z() + trim_length))


def position_basic(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    pedipalp_pts = _get_pedipalp_points(geo)
    top_right_pt, m1, m3, m4 = points_from_geo(
        geo,
        tmp_coxa_start(3),
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


def delete_start_coxa_supports(
    node: hou.SopNode,
) -> None:
    geo: hou.Geometry = node.geometry()
    pts = [p for p in geo.points() if p.stringAttribValue("id").startswith(tmp_coxa_support(1))]
    geo.deletePoints(list(pts))

    starts = points_from_geo(
        geo,
        tmp_coxa_start(1),
        tmp_coxa_start(2),
        tmp_coxa_start(4),
    )
    geo.deletePoints(list(starts))


def prepare_coxa_base_trapezoid(
    node: hou.SopNode,
) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)
    _add_bottom_right_face_point(geo, control_params.endite_buffer_ratios)
    _add_base_trapezoid(node)

def _add_bottom_right_face_point(
    geo: hou.Geometry,
    endite_buffer: hou.Vector2,
) -> hou.Point:
    e1, e4, m1 = points_from_geo(
        geo,
        tmp_coxa_end(1),
        tmp_coxa_end(4),
        basemaxillamembrane(1),
    )

    direction = get_coxa_direction(geo)

    start_position = e1.position() * endite_buffer.x() + e4.position() * (1.0 - endite_buffer.x())
    dist = get_buffer_dist_z(geo, endite_buffer.y())
    target_position = start_position + direction * dist
    p = add_id_point(geo, target_position, tmp_coxa_corner("bottom"))
    return p


def remove_tmp_attributes(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    pts = points_start_with(geo, "id", "tmp_")
    for p in pts:
        set_point_id(p, "")
    remove_attribs(geo, global_attributes=(tmp_front_socket_width(),))



def _build_cubes(
    node: hou.SopNode,
) -> Moject[tuple[list[hou.Point], list[hou.Point], list[hou.Point]]]:
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
        set_point_id(s_pt, tmp_coxa_start(i))
        set_point_id(e_pt, tmp_coxa_end(i))
        set_point_id(ss_pt, tmp_coxa_support(1, i))
        set_point_id(es_pt, tmp_coxa_support(2, i))

    return result

def _get_pedipalp_param(
    node: hou.SopNode,
) -> LegParam:
    geo = node.geometry()
    leg = get_leg(node)

    params = get_parms(leg, use_tuple=False)
    control_params = get_parms(get_control(leg, "CONTROL"), use_tuple=False)

    coxa_width_length = _get_pedipalp_coxa_width_length(
        geo,
        params.front_coxa_width_length_ratios.y(),
        params.pedipalp_coxa_length,
    )
    length_ratios = tuple(params.pedipalp_segment_length_ratios)
    max_segment_yaws = tuple(params.max_yaw_angles)[:len(length_ratios)]
    min_segment_flexes = tuple(params.min_flex_angles)[:len(length_ratios)]

    return LegParam.from_specs(
        coxa_width_length=coxa_width_length,
        length_ratios=length_ratios,
        max_segment_yaws=max_segment_yaws,
        min_segment_flexes=min_segment_flexes,
        coxa_trochanter_height_ratio=control_params.coxa_trochanter_height_ratio,
        other_segment_height_ratio=control_params.other_segment_height_ratio,
        spine_ratio=control_params.segment_bulge_bias_ratio,
        shrink_ratios=control_params.segment_taper_ratios,
        minimum_membrane=control_params.joint_clearance_limits,
        support_loop_ratio=control_params.joint_support_loop_ratio,
        tarsus_wedge_angle=control_params.tarsus_wedge_angle,
    )

def _get_pedipalp_coxa_width_length(
    geo: hou.Geometry,
    front_coxa_length_ratio: float,
    pedipalp_coxa_length: float,
) -> tuple[float, float]:
    m3, m4 = positions_from_geo(geo, basemaxillamembrane(3), basemaxillamembrane(4))
    width = m3.distanceTo(m4)
    front_socket_width = geo.attribValue(tmp_front_socket_width())
    front_coxa_length = front_socket_width * front_coxa_length_ratio
    length = front_coxa_length * pedipalp_coxa_length
    return width, length

def _get_pedipalp_points(
    geo: hou.Geometry,
) -> list[hou.Point]:
    pts = {pt for prim in prims_by_attr(geo, "region", (Region.LEGMEMBRANE, Region.LEGSEGMENT), startswith=True) for pt in prim.points()}
    if not pts:
        return list(geo.points())
    return list(pts)



def _add_base_trapezoid(
    node: hou.SopNode,
) -> float:
    geo = node.geometry()
    m1, m2, cb, es4, e1, e4 = points_from_geo(
        geo,
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        tmp_coxa_corner("bottom"),
        tmp_coxa_support(2, 4),
        tmp_coxa_end(1),
        tmp_coxa_end(4),
    )

    pos_mid_bottom = (e1.position() + e4.position()) * 0.5

    pos_p4, pos_p3, height = _calculate_base_trapezoid_points(
        node,
        m1.position(),
        m2.position(),
        cb.position(),
        es4.position(),
        pos_mid_bottom,
    )

    p3 = add_id_point(geo, pos_p3, tmp_coxa_corner("base", 1))
    p4 = add_id_point(geo, pos_p4, tmp_coxa_corner("base", 2))

    fill_face([m1, m2, p3, p4], reverse=True)
    add_global_attrib(geo, tmp_coxa_base_height(), height)

    return height

def _calculate_base_trapezoid_points(
    node: hou.SopNode,
    pos_m1: hou.Vector3,
    pos_m2: hou.Vector3,
    pos_cb: hou.Vector3,
    pos_es4: hou.Vector3,
    pos_mid_bottom: hou.Vector3,
) -> tuple[hou.Vector3, hou.Vector3, float]:
    geo = node.geometry()
    leg = get_leg(node)
    wedge_angle = get_float_parm(get_control(leg, "CONTROL"), "coxa_start_wedge_angle")

    m4 = points_from_geo(geo, basemaxillamembrane(4))[0]
    neg_z = hou.Vector3(0.0, 0.0, -1.0)
    n_socket = (pos_m2 - pos_m1).cross(m4.position() - pos_m1).normalized()
    if n_socket.dot(neg_z) < 0:
        n_socket = -n_socket

    edge = pos_m2 - pos_m1
    u = edge.normalized()
    length = edge.length()

    n = hou.Quaternion(90.0 - wedge_angle, u).rotate(n_socket)
    v = n.cross(u).normalized()
    if v.y() > 0.0:
        v = -v
    n_plane = u.cross(v).normalized()

    dir_line = pos_m1 - pos_es4
    denom = dir_line.dot(n_plane)
    t = (pos_m1 - pos_cb).dot(n_plane) / denom
    pos_pp1 = pos_cb + dir_line * t

    offset_pp = (pos_pp1 - pos_m1).dot(u)
    pos_pp2 = pos_pp1 + u * (length - 2.0 * offset_pp)
    mid_pp = (pos_pp1 + pos_pp2) * 0.5

    n_bottom_plane = (pos_cb - pos_es4).cross(pos_m1 - pos_es4).normalized()
    d = (pos_mid_bottom - mid_pp).dot(n_bottom_plane)
    offset_vec = n_bottom_plane * d

    pos_p4 = pos_pp1 + offset_vec
    pos_p3 = pos_pp2 + offset_vec

    offset = (pos_p4 - pos_m1).dot(u)
    height = (pos_p4 - pos_m1 - u * offset).length()

    return pos_p4, pos_p3, height


def get_coxa_direction(geo: hou.Geometry) -> hou.Vector3:
    es3, e3 = points_from_geo(
        geo,
        tmp_coxa_support(2, 3),
        tmp_coxa_end(3),
    )
    return (es3.position() - e3.position()).normalized()


def get_buffer_dist_z(geo: hou.Geometry, endite_buffer_y: float) -> float:
    e1, m1 = positions_from_geo(
        geo,
        tmp_coxa_end(1),
        basemaxillamembrane(1),
    )
    return e1.distanceTo(m1) * endite_buffer_y
