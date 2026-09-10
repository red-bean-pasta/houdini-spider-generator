import hou

from base_sops import basemaxilla, basemaxillamembrane, basesternum
from helper import point_from_geo
from leg_builder import LegParam, build_leg
from sternum import sternumrim
from utilities.common import (
    MessagedResult,
    get_control,
    get_params,
    get_parent,
    rotation_to,
)


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
    p_maxilla, p_sternum, p_inset = point_from_geo(
        geo,
        basemaxilla(1),
        sternumrim(1),
        basemaxillamembrane(1),
    )

    v = p_maxilla.position() - p_sternum.position()
    direction = hou.Vector3(v.x(), 0.0, v.z()).normalized()
    q = rotation_to(hou.Vector3(0.0, 0.0, -1.0), direction)

    pedipalp_pts = _get_pedipalp_points(geo)
    top_right_pt = max(
        pedipalp_pts,
        key=lambda pt: (pt.position().z(), pt.position().y(), pt.position().x()),
    )
    offset = p_inset.position() - q.rotate(top_right_pt.position())
    for pt in pedipalp_pts:
        pt.setPosition(q.rotate(pt.position()) + offset)


def _build_cubes(
    node: hou.SopNode,
) -> MessagedResult[tuple[list[hou.Point], list[hou.Point], list[hou.Point]]]:
    geo = node.geometry()
    param = _get_pedipalp_param(node)
    return build_leg(geo, param)

def _get_pedipalp_param(
    node: hou.SopNode,
) -> LegParam:
    geo = node.geometry()
    leg = get_parent(node)

    params = get_params(leg, use_tuple=False)
    control_params = get_params(get_control(leg), use_tuple=False)

    coxa_size = _get_pedipalp_coxa_size(geo, params.front_coxa_size_ratio)
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
    p_maxilla, p_sternum = point_from_geo(geo, basemaxilla(1), basesternum(1, 2))
    width = p_maxilla.position().distanceTo(p_sternum.position())
    height = width
    length = front_coxa_size_ratio.y() / front_coxa_size_ratio.x() * width
    return width, height, length


def _get_pedipalp_points(
    geo: hou.Geometry,
) -> list[hou.Point]:
    pts = {
        pt
        for prim in geo.prims()
        if prim.stringAttribValue("region").startswith(("legsegment", "legmembrane"))
        for pt in prim.points()
    }
    if not pts:
        return list(geo.points())
    return list(pts)
