import math

import hou

from houkit.attributer import add_prim_attrib
from houkit.topology import loop_cut, points_to_positions

from ...helper import bridge_loops, fill_face_with_attr, points_from_loop_cut
from ..attributes import Region


def inset_segment_thickness(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    support_loop_ratio: float,
) -> list[hou.Point]:
    assert len(seg_pts) % 8 == 0, f"Expected seg_pts length to be a multiple of 8, got {len(seg_pts)}"
    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_segs = len(seg_pts) // 8
    thickness_pts: list[hou.Point] = []

    for i in range(num_segs - 1):
        former_end = seg_pts[i * 8 + 4:(i + 1) * 8]
        latter_start = seg_pts[(i + 1) * 8:(i + 1) * 8 + 4]
        former_inset, latter_inset = _add_segment_thickness_loops(
            geo,
            former_end,
            latter_start,
            cut_length,
        )
        thickness_pts.extend([*former_inset, *latter_inset])

    return thickness_pts


def _add_segment_thickness_loops(
    geo: hou.Geometry,
    former_end: list[hou.Point],
    latter_start: list[hou.Point],
    cut_length: float,
) -> tuple[list[hou.Point], list[hou.Point]]:
    former_inset = _inset_loop(geo, former_end, cut_length)
    latter_inset = _inset_loop(geo, latter_start, cut_length)

    e_loop = [former_end[0], former_end[1], former_end[3], former_end[2]]
    ie_loop = [former_inset[0], former_inset[1], former_inset[3], former_inset[2]]
    bridge_loops(
        geo,
        e_loop,
        ie_loop,
        reverse=True,
        cross_order=True,
        primitive_attr=("region", Region.LEGSEGMENT),
    )

    s_loop = [latter_start[0], latter_start[1], latter_start[3], latter_start[2]]
    is_loop = [latter_inset[0], latter_inset[1], latter_inset[3], latter_inset[2]]
    bridge_loops(
        geo,
        s_loop,
        is_loop,
        reverse=True,
        primitive_attr=("region", Region.LEGSEGMENT),
    )
    return former_inset, latter_inset


def _inset_loop(
    geo: hou.Geometry,
    pts: list[hou.Point],
    cut_length: float,
) -> list[hou.Point]:
    assert len(pts) == 4
    pos0, pos1, pos2, pos3 = points_to_positions(pts)
    v_down = pos2 - pos0
    dir_down = v_down.normalized()

    pos_in0 = pos0 + hou.Vector3(-cut_length, 0, 0) + dir_down * cut_length
    pos_in1 = pos1 + hou.Vector3(cut_length, 0, 0) + dir_down * cut_length
    pos_in2 = pos2 + hou.Vector3(-cut_length, 0, 0) - dir_down * cut_length
    pos_in3 = pos3 + hou.Vector3(cut_length, 0, 0) - dir_down * cut_length

    p_in = [geo.createPoint() for _ in range(4)]
    for p, pos in zip(p_in, (pos_in0, pos_in1, pos_in2, pos_in3)):
        p.setPosition(pos)
    return p_in


def add_segment_loop_cuts(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    support_loop_ratio: float,
) -> list[hou.Point]:
    assert len(seg_pts) % 8 == 0, f"Expected seg_pts length to be a multiple of 8, got {len(seg_pts)}"
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


def fill_membranes(
    geo: hou.Geometry,
    thickness_pts: list[hou.Point],
) -> list[hou.Point]:
    if not thickness_pts:
        return []

    add_prim_attrib(geo, "region", "")
    assert len(thickness_pts) % 8 == 0, f"Expected thickness_pts length to be a multiple of 8, got {len(thickness_pts)}"

    membrane_points: list[hou.Point] = []
    num_joints = len(thickness_pts) // 8
    for i in range(num_joints):
        former_end = thickness_pts[i * 8:i * 8 + 4]
        latter_start = thickness_pts[i * 8 + 4:(i + 1) * 8]
        membrane_points.extend(_add_membrane_joint(geo, former_end, latter_start))

    return membrane_points


def _add_membrane_joint(
    geo: hou.Geometry,
    former_end: list[hou.Point],
    latter_start: list[hou.Point],
) -> list[hou.Point]:
    # fu: former upper, fb: former bottom, lu: latter upper, lb: latter bottom
    fu1, fu2, fb1, fb2 = former_end
    lu1, lu2, lb1, lb2 = latter_start
    midpoint_positions = _get_membrane_joint_midpoint_positions(former_end, latter_start)
    mu1, mu2, mb1, mb2 = _create_membrane_midpoints(geo, midpoint_positions)

    former_loop = [fu1, fu2, fb2, fb1]
    mid_loop = [mu1, mu2, mb2, mb1]
    latter_loop = [lu1, lu2, lb2, lb1]
    bridge_loops(geo, former_loop, mid_loop, primitive_attr=("region", Region.LEGMEMBRANE))
    bridge_loops(geo, mid_loop, latter_loop, primitive_attr=("region", Region.LEGMEMBRANE))
    return [mu1, mu2, mb1, mb2]


def _get_membrane_joint_midpoint_positions(
    former_end: list[hou.Point],
    latter_start: list[hou.Point],
) -> tuple[hou.Vector3, hou.Vector3, hou.Vector3, hou.Vector3]:
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

    # mu: midpoint upper, mb: midpoint bottom
    pos_mu1 = (pos_fu1 + pos_lu1) * 0.5
    pos_mu2 = (pos_fu2 + pos_lu2) * 0.5
    pos_mb1 = (pos_fb1 + pos_lb1) * 0.5
    pos_mb2 = (pos_fb2 + pos_lb2) * 0.5
    pos_mb1[1] = (pos_mb1.y() + (pos_mu1.y() - membrane_length)) * 0.5
    pos_mb2[1] = (pos_mb2.y() + (pos_mu2.y() - membrane_length)) * 0.5
    return pos_mu1, pos_mu2, pos_mb1, pos_mb2


def _create_membrane_midpoints(
    geo: hou.Geometry,
    positions: tuple[hou.Vector3, hou.Vector3, hou.Vector3, hou.Vector3],
) -> tuple[hou.Point, hou.Point, hou.Point, hou.Point]:
    points = [geo.createPoint() for _ in positions]
    for point, position in zip(points, positions):
        point.setPosition(position)
    return tuple(points)


def add_membrane_loop_cuts(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    thickness_pts: list[hou.Point],
    mem_pts: list[hou.Point],
    support_loop_ratio: float,
) -> list[hou.Point]:
    assert len(thickness_pts) % 8 == 0, f"Expected thickness_pts length to be a multiple of 8, got {len(thickness_pts)}"
    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_joints = len(thickness_pts) // 8
    all_mem_pts: list[hou.Point] = []

    for i in range(num_joints):
        former_end = thickness_pts[i * 8:i * 8 + 4]
        latter_start = thickness_pts[i * 8 + 4:(i + 1) * 8]
        mid_pts = mem_pts[i * 4:(i + 1) * 4]

        # fu: former upper, lu: latter upper
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


def close_tarsus(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    tarsus_wedge_angle: float,
) -> None:
    assert len(seg_pts) >= 4, f"Expected at least 4 seg_pts, got {len(seg_pts)}"
    p4, p5, p6, p7 = seg_pts[-4:]
    fill_face_with_attr(geo, [p4, p6, p7, p5], "region", Region.LEGSEGMENT)

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
    cut_edges = loop_cut(
        prim,
        s0,
        e0,
        cut_length,
        use_ratio=False,
    )
    cut_pts = points_from_loop_cut(cut_edges)
    assert len(cut_pts) == 4, f"Expected four points from tube loop cut, got {len(cut_pts)}"
    m0, m1, m3, m2 = cut_pts
    return [m0, m1, m2, m3]
