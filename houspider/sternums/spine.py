import hou

from houkit.attributer import deduplicate_point_attribs
from houkit.geomath import is_equal_approx
from houkit.noder import get_control, get_parent
from houkit.parameterizer import get_parms
from houkit.topology import inset
from ..helper import points_by_id, positions_from_geo
from .attributes import ID, outer_loop_ids, sternumrim

def inset_spine_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)
    ratio_x, _ = params.spine_loop_position_ratio
    assert 0.0 < ratio_x <= 1.0

    if not is_equal_approx(ratio_x, 1.0):
        inset(list(geo.prims()), 1.0 - ratio_x, use_ratio=True, follow_existing_edge=True)
        deduplicate_point_attribs(geo, "id", outer_loop_ids(), keep_first=True)


def elevate_spine_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)

    ratio_x, ratio_y = params.spine_loop_position_ratio
    if is_equal_approx(ratio_x, 1.0) or is_equal_approx(ratio_y, 0.0):
        return

    depth = control_params.half_width * params.spine_depth_ratio
    rest_y = -depth * ratio_y

    for point in geo.points():
        if point.attribValue("id").startswith(outer_loop_ids()):
            continue
        pos = point.position()
        point.setPosition((pos[0], rest_y, pos[2]))


def descend_sternum_spine(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)

    depth = control_params.half_width * params.spine_depth_ratio
    power = params.spine_descent_power
    points = points_by_id(geo)

    top, middle, bottom = positions_from_geo(
        geo,
        sternumrim(0),
        sternumrim(3),
        sternumrim(5),
    )

    upper_span = abs(middle[2] - top[2])
    lower_span = abs(bottom[2] - middle[2])
    assert upper_span != 0.0 and lower_span != 0.0
    for point_id, point in points.items():
        if not point_id.startswith(ID.STERNUMSPINE):
            continue
        position = point.position()
        rest_y = position[1]
        if position[2] <= middle[2]:
            y = _get_eased_depth(position[2], top[2], middle[2], rest_y, -depth, power)
        else:
            y = _get_eased_depth(position[2], bottom[2], middle[2], rest_y, -depth, power)
        point.setPosition((position[0], y, position[2]))

def _get_eased_depth(
    x: float,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    power: float,
) -> float:
    span = x1 - x0
    assert span != 0.0, "Expected non-zero span for easing interpolation"
    t = max(0.0, min(1.0, (x - x0) / span))
    return y0 + (y1 - y0) * (t ** power)

