import hou

from base_sops import basemaxillamembrane
from helper import affix_id, point_from_geo, set_point_id
from leg_builder import LegParam, build_leg, Region
from utilities.common import (
    MessagedResult,
    get_control,
    get_params,
    get_parent,
    rotation_to,
)


def _tmp_coxa(*i) -> str:
    return affix_id("tmp_pedipalpcoxa", *i)
def _tmp_coxa_support(*i) -> str:
    return affix_id("tmp_pedipalpcoxasupport", *i)


def build_pedipalp(
    node: hou.SopNode,
) -> None:
    _, warnings = _build_cubes(node)
    for w in warnings:
        node.addWarning(w)


def position_pedipalp(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    pedipalp_pts = _get_pedipalp_points(geo)
    top_right_pt, m1, m3, m4 = point_from_geo(
        geo,
        _tmp_coxa(3),
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


def adjust_pedipalp_coxa(
    node: hou.SopNode,
) -> None:
    geo = node.geometry()
    c1, c2, c4, s1, s2, s4, m1, m2, m3 = point_from_geo(
        geo,
        _tmp_coxa(1),
        _tmp_coxa(2),
        _tmp_coxa(4),
        _tmp_coxa_support(1),
        _tmp_coxa_support(2),
        _tmp_coxa_support(4),
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        basemaxillamembrane(3),
    )
    for c_pt, s_pt, pos in (
        (c4, s4, m1.position()),
        (c2, s2, m3.position()),
        (c1, s1, (m2.position() + m1.position()) * 0.5),
    ):
        offset = pos - c_pt.position()
        c_pt.setPosition(pos)
        s_pt.setPosition(s_pt.position() + offset)


def _build_cubes(
    node: hou.SopNode,
) -> MessagedResult[tuple[list[hou.Point], list[hou.Point], list[hou.Point]]]:
    geo = node.geometry()
    param = _get_pedipalp_param(node)
    result = build_leg(geo, param)
    (all_seg_pts, _, _), _ = result

    # 1: Bottom left, 2: Top left, 3: Top right, 4: Bottom right
    coxa_corners = (all_seg_pts[3], all_seg_pts[1], all_seg_pts[0], all_seg_pts[2])
    support_corners = (all_seg_pts[7], all_seg_pts[5], all_seg_pts[4], all_seg_pts[6])
    for i, (c_pt, s_pt) in enumerate(zip(coxa_corners, support_corners), start=1):
        set_point_id(c_pt, _tmp_coxa(i))
        set_point_id(s_pt, _tmp_coxa_support(i))

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
