import hou

from houkit.attributer import add_prim_attrib, deduplicate_point_attribs
from houkit.noder import get_control, get_parent
from houkit.parameterizer import get_parms
from houkit.topology import outset
from ..helper import points_by_id, points_from_geo
from .attributes import ID, outer_loop_ids, sternummiddle, sternumrim

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

    add_sternum_loop(geo, support_dist)
    add_sternum_loop(geo, dist)

    adjust_midpoints_after_outset(geo)

def add_sternum_loop(geo: hou.Geometry, dist: float) -> list[hou.Point]:
    outset(list(geo.prims()), dist, use_ratio=False)
    deduplicate_point_attribs(geo, "id", (ID.STERNUMSPINE,), keep_first=True)
    deduplicate_point_attribs(geo, "id", outer_loop_ids(), keep_first=False)
    return [
        pt for pt in geo.points()
        if pt.attribValue("id").startswith(outer_loop_ids())
    ]

def adjust_midpoints_after_outset(geo: hou.Geometry) -> None:
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
