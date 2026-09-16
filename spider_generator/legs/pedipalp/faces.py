import hou

from houkit.geomath import get_line_face_intersection
from houkit.noder import get_control
from houkit.parameterizer import get_float_parm, get_parms
from houkit.topology import fill_face
from bases.attributes import basemaxillamembrane
from helper import add_id_point, points_from_geo, positions_from_geo
from .attributes import tmp_coxa_base_height, tmp_coxa_corner, tmp_coxa_end, tmp_coxa_start, tmp_coxa_support, tmp_maxilla_pole
from .geometry import get_buffer_dist_z, get_coxa_direction
from .helper import get_leg

def fill_bottom_right_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    es4, c2, m1, cb = points_from_geo(
        geo,
        tmp_coxa_support(2, 4),
        tmp_coxa_corner("base", 2),
        basemaxillamembrane(1),
        tmp_coxa_corner("bottom"),
    )
    fill_face([es4, cb, c2, m1])


def fill_back_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s3, es3, es4, m1 = points_from_geo(
        geo,
        tmp_coxa_start(3),
        tmp_coxa_support(2, 3),
        tmp_coxa_support(2, 4),
        basemaxillamembrane(1),
    )
    fill_face([es3, es4, m1, s3])


def fill_top_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    dist = geo.attribValue(tmp_coxa_base_height())
    direction = get_coxa_direction(geo)

    e2, m2, m3, m4, es2, es3 = points_from_geo(
        geo,
        tmp_coxa_end(2),
        basemaxillamembrane(2),
        basemaxillamembrane(3),
        basemaxillamembrane(4),
        tmp_coxa_support(2, 2),
        tmp_coxa_support(2, 3)
    )

    pos = e2.position() + direction * dist
    c6 = add_id_point(geo, pos, tmp_coxa_corner("fronttop"))

    fill_face([es3, m4, c6, es2])
    fill_face([m4, m3, m2, c6])


def add_maxilla_quads(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)
    pos = _get_maxilla_pole(node)
    normal = _get_averaged_maxilla_quad_normal(geo, pos)
    _add_maxilla_quads_to_geo(geo, pos, normal, control_params.endite_surface_size_ratio)

def _get_maxilla_pole(node: hou.SopNode) -> hou.Vector3:
    geo: hou.Geometry = node.geometry()
    leg = get_leg(node)
    length_ratio = get_float_parm(leg, "endite_length_ratio")

    e1, e2, e3, m1, m2, m4, ct2 = points_from_geo(
        geo,
        tmp_coxa_end(1),
        tmp_coxa_end(2),
        tmp_coxa_end(3),
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        basemaxillamembrane(4),
        tmp_coxa_corner("base", 2)
    )
    direction = m4.position() - m1.position()
    direction = hou.Vector3(direction.x(), 0, direction.z())

    m2_pos = m2.position()
    hit = get_line_face_intersection(
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
    pts = points_from_geo(
        geo,
        tmp_coxa_corner("front"),
        basemaxillamembrane(2),
        tmp_coxa_corner("base", 2),
        tmp_coxa_corner("base", 1),
        tmp_coxa_corner("bottom"),
        tmp_coxa_corner("frontbottom"),
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
    ct2p, cbp, cfp, m2p = positions_from_geo(
        geo,
        tmp_coxa_corner("base", 2),
        tmp_coxa_corner("bottom"),
        tmp_coxa_corner("front"),
        basemaxillamembrane(2),
    )

    w = ct2p.distanceTo(center) * flat_ratio
    h = w * (cbp.distanceTo(cfp)) / (cbp.distanceTo(ct2p))
    hw = w * 0.5
    hh = h * 0.5

    u = (cbp - m2p).normalized()
    u = hou.Vector3(u.x(), 0, u.z()).normalized()
    v = normal.cross(u).normalized()

    pw = u * hw
    ph = v * hh
    p0 = center + (-pw - ph)
    p1 = center + (pw - ph)
    p2 = center + (pw + ph)
    p3 = center + (-pw + ph)
    p4 = (p0 + p3) * 0.5
    p5 = (p1 + p2) * 0.5

    poses = [p0, p1, p2, p3, p4, p5]
    pts = []
    for i, p in enumerate(poses, start=1):
        p = add_id_point(geo, p, tmp_maxilla_pole(i))
        pts.append(p)

    fill_face([pts[0], pts[1], pts[5], pts[4]], True)
    fill_face([pts[5], pts[4], pts[3], pts[2]])

    return pts


def add_front_upper_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)
    p = _add_front_face_point(geo, control_params.endite_buffer_ratios)
    es2, c6, m2 = points_from_geo(
        geo,
        tmp_coxa_support(2, 2),
        tmp_coxa_corner("fronttop"),
        basemaxillamembrane(2),
    )
    fill_face([es2, c6, m2, p])

def _add_front_face_point(
    geo: hou.Geometry,
    endite_buffer: hou.Vector2,
) -> hou.Point:
    e1, e2 = points_from_geo(
        geo,
        tmp_coxa_end(1),
        tmp_coxa_end(2),
    )
    dist = get_buffer_dist_z(geo, endite_buffer.y())
    direction = get_coxa_direction(geo)
    start = e1.position() * endite_buffer.x() + e2.position() * (1.0 - endite_buffer.x())
    target = start + direction * dist
    return add_id_point(geo, target, tmp_coxa_corner("front"))


def add_front_loop_faces(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)
    p = _add_loop_point(geo, control_params.endite_buffer_ratios.y())
    es1, es2, es4, cf, cb = points_from_geo(
        geo,
        tmp_coxa_support(2, 1),
        tmp_coxa_support(2, 2),
        tmp_coxa_support(2, 4),
        tmp_coxa_corner("front"),
        tmp_coxa_corner("bottom"),
    )
    fill_face([es2, cf, p, es1])
    fill_face([es1, p, cb, es4])

def _add_loop_point(
    geo: hou.Geometry,
    endite_buffer_y: float,
) -> hou.Point:
    e1, = points_from_geo(
        geo,
        tmp_coxa_end(1),
    )
    dist = get_buffer_dist_z(geo, endite_buffer_y)
    direction = get_coxa_direction(geo)
    target = e1.position() + direction * dist
    return add_id_point(geo, target, tmp_coxa_corner("frontbottom"))


def fill_maxilla_faces(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    cf, cfb, cb, ct2, ct1, m2 = points_from_geo(
        geo,
        tmp_coxa_corner("front"),
        tmp_coxa_corner("frontbottom"),
        tmp_coxa_corner("bottom"),
        tmp_coxa_corner("base", 2),
        tmp_coxa_corner("base", 1),
        basemaxillamembrane(2),
    )
    p0, p1, p2, p3, p4, p5 = points_from_geo(
        geo,
        *[tmp_maxilla_pole(i + 1) for i in range(6)],
    )
    fill_face([p0, m2, ct1, p4])
    fill_face([p4, ct1, ct2, p3])
    fill_face([p3, ct2, cb, p2])
    fill_face([p2, cb, cfb, p5])
    fill_face([p5, cfb, cf, p1])
    fill_face([p1, cf, m2, p0])
