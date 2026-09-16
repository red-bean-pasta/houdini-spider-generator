import hou

from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm, get_parms
from houkit.topology import fill_face, get_prim_centroid
from .attributes import Region, cheliceraemembrane, cheliceraestart, cheliceraestartmembranesupport
from ..bases import attributes as base_attributes
from ..heads.attributes import headchelicerae
from ..helper import (
    add_id_point,
    deduplicate_id_attr,
    inset_inner_prims,
    points_from_geo,
    prims_by_attr,
    set_point_id,
)


def inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")

    lower, upper = points_from_geo(
        geo,
        base_attributes.basesternum(0),
        headchelicerae(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    chelicera_prims = prims_by_attr(geo, "region", Region.CHELICERA)
    inner = inset_and_recess(chelicera_prims, dist / 4, dist)
    for prim in inner:
        prim.setAttribValue("region", Region.CHELICERASOCKET)

    for prim in prims_by_attr(geo, "region", Region.CHELICERA):
        prim.setAttribValue("region", Region.CHELICERAMEMBRANE)


def classify_after_inset(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = prims_by_attr(geo, "region", Region.CHELICERASOCKET)
    pts_dict = {}
    for prim in socket_prims:
        for pt in prim.points():
            pts_dict[pt.number()] = pt
    points = list(pts_dict.values())
    points.sort(key=lambda p: p.position().x())
    assert len(points) == 10, f"Expected 10 points in the whole socket, got {len(points)}"

    left_outer = sorted(points[:2], key=lambda p: p.position().y())
    left_mid = sorted(points[2:4], key=lambda p: p.position().y())
    center = sorted(points[4:6], key=lambda p: p.position().y())
    right_mid = sorted(points[6:8], key=lambda p: p.position().y())
    right_outer = sorted(points[8:], key=lambda p: p.position().y())

    set_point_id(left_outer[0], cheliceraemembrane(-3))
    set_point_id(left_outer[1], cheliceraemembrane(-4))
    set_point_id(left_mid[0], cheliceraemembrane(-2))
    set_point_id(left_mid[1], cheliceraemembrane(-5))
    set_point_id(center[0], cheliceraemembrane(1))
    set_point_id(center[1], cheliceraemembrane(6))
    set_point_id(right_mid[0], cheliceraemembrane(2))
    set_point_id(right_mid[1], cheliceraemembrane(5))
    set_point_id(right_outer[0], cheliceraemembrane(3))
    set_point_id(right_outer[1], cheliceraemembrane(4))
    deduplicate_id_attr(geo, None, add_affix=False)


def prepare_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims = prims_by_attr(geo, "region", Region.CHELICERASOCKET, startswith=True)
    geo.deletePrims(socket_prims)


def remove_left_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    left_prims = [
        prim for prim in prims_by_attr(geo, "region", Region.CHELICERAMEMBRANE)
        if get_prim_centroid(prim).x() < 0.0
    ]
    left_points = list({
        pt.number(): pt
        for prim in left_prims
        for pt in prim.points()
        if pt.position().x() < -1e-4
    }.values())
    geo.deletePoints(left_points)


def add_start_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)

    b0, u0, m6 = points_from_geo(
        geo,
        base_attributes.basesternum(0),
        headchelicerae(0),
        cheliceraemembrane(6),
    )
    membrane_points = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(6),
        cheliceraemembrane(4),
        cheliceraemembrane(3),
    )

    end_section_offset = params.end_section_offset
    middle_section_offset = params.middle_section_offset
    middle_section_height_ratio = params.middle_section_height_ratio

    dir_y = -end_section_offset.y() * middle_section_height_ratio
    dir_z = -middle_section_offset.y()
    dir_zy = hou.Vector3(0.0, dir_y, dir_z).normalized()

    target_y = u0.position().y() - (u0.position().y() - b0.position().y()) * (1.0 / 3.0)
    dist = (target_y - m6.position().y()) / dir_zy.y()
    offsets = (
        hou.Vector3(0.0, 0.0, -dist * 0.5),
        dir_zy * dist,
        dir_zy * dist,
        hou.Vector3(0.0, 0.0, -dist * 0.5),
    )

    pts = [
        add_id_point(geo, start.position() + offset, cheliceraestart(j))
        for j, (start, offset) in enumerate(zip(membrane_points, offsets), start=1)
    ]

    fill_face(pts, True)


def inset_start_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    lower, upper = points_from_geo(
        geo,
        base_attributes.basesternum(0),
        headchelicerae(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    start_points = points_from_geo(geo, *(cheliceraestart(j) for j in range(1, 5)))
    start_prim = next(prim for prim in start_points[0].prims() if all(pt in start_points for pt in prim.points()))
    inset_and_recess([start_prim], dist / 4, dist, delete_inset_prims=True)

    for j, pt in enumerate(start_points, start=1):
        set_point_id(pt, cheliceraestartmembranesupport(j))


def adjust_start_section_left(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s1, s2, ss1, ss2 = points_from_geo(
        geo,
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
    )
    ratio = 1/3
    for s, ss in ((s1, ss1), (s2, ss2)):
        pos = s.position()
        new_x = pos.x() * ratio + ss.position().x() * (1 - ratio)
        s.setPosition(hou.Vector3(new_x, pos.y(), pos.z()))


def inset_and_recess(
    prims: list[hou.Prim],
    inset_dist: float,
    recess_dist: float,
    delete_inset_prims: bool = False,
) -> list[hou.Prim]:
    geo = prims[0].geometry()
    inner = inset_inner_prims(geo, prims, inset_dist, use_ratio=False)
    norm = inner[0].normal()
    inner_pts = list({pt.number(): pt for prim in inner for pt in prim.points()}.values())
    if delete_inset_prims:
        inner[0].geometry().deletePrims(inner, keep_points=True)

    # Move inset points along the face normal backwards by its width to create a seam
    for pt in inner_pts:
        pt.setPosition(pt.position() - norm * recess_dist)
    return inner
