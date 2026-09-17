import hou

from houkit.attributer import add_prim_attrib, deduplicate_point_attribs, set_point_attribs_by_position
from houkit.noder import get_control, get_parent
from houkit.parameterizer import get_parms
from houkit.topology import outset
from houkit.topologies.sorter import Axis
from ..helper import points_by_id, points_from_geo
from .attributes import ID, outer_loop_ids, sternummiddle, sternumrim, sternumriminner

def add_prim_regions(node: hou.SopNode) -> None:
    geo = node.geometry()

    add_prim_attrib(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", "sternum")


def outset_sternum_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)
    control_params = get_parms(get_control(node, "CONTROL"), use_tuple=False)

    membrane_width = params.membrane_ratio * control_params.half_width
    support_dist = membrane_width
    dist = membrane_width
    assert dist > 0.0, f"Expected positive sternum membrane inset distance, got {dist}"

    inner_loop = _add_sternum_loop(geo, support_dist)
    inner_rim = [
        point for point in inner_loop
        if point.stringAttribValue("id").startswith(ID.STERNUMRIM)
    ]
    _add_sternum_loop(geo, dist)
    _attribute_inner_sternum_rim(inner_rim)
    _adjust_midpoints_after_outset(geo)

def _add_sternum_loop(geo: hou.Geometry, dist: float) -> list[hou.Point]:
    outset(list(geo.prims()), dist, use_ratio=False)
    deduplicate_point_attribs(geo, "id", (ID.STERNUMSPINE,), keep_first=True)
    deduplicate_point_attribs(geo, "id", outer_loop_ids(), keep_first=False)
    return [
        pt for pt in geo.points()
        if (
            pt.attribValue("id").startswith(outer_loop_ids())
            and not pt.attribValue("id").startswith(sternumriminner())
        )
    ]

def _adjust_midpoints_after_outset(geo: hou.Geometry) -> None:
    points = points_by_id(geo)
    rim1, rim_neg1 = points_from_geo(geo, sternumrim(1), sternumrim(-1))
    p0 = (rim1.position() + rim_neg1.position()) / 2.0
    (rim0,) = points_from_geo(geo, sternumrim(0))
    rim0.setPosition(hou.Vector3(0.0, p0[1], p0[2]))
    if sternumrim(5) in points:
        (rim5,) = points_from_geo(geo, sternumrim(5))
        p5 = rim5.position()
        rim5.setPosition(hou.Vector3(0.0, p5[1], p5[2]))
    for side in (1, -1):
        for i in range(1, 5):
            start, end = points_from_geo(
                geo,
                sternumrim(side * i),
                sternumrim(5) if i == 4 else sternumrim(side * (i + 1)),
            )
            start = start.position()
            end = end.position()
            midpoint = (start + end) / 2.0
            (middle_point,) = points_from_geo(geo, sternummiddle(side * i))
            middle_point.setPosition(midpoint)


def _attribute_inner_sternum_rim(points: list[hou.Point]) -> None:
    right_points = [point for point in points if point.position().x() >= 0.0]
    left_points = [point for point in points if point.position().x() < 0.0]

    set_point_attribs_by_position(
        right_points,
        "id",
        sternumriminner(),
        (Axis.Z, Axis.Y, Axis.X),
    )
    set_point_attribs_by_position(
        left_points,
        "id",
        sternumriminner("-"),
        (Axis.Z, Axis.Y, Axis.X),
        start_index=1,
    )
