import hou

from ..bases import attributes as base_attributes
from ..helper import prims_by_attr
from houkit.attributer import remove_attribs
from houkit.topology import points_to_positions

def extract_right_coxa(node: hou.SopNode) -> None:
    from .pedipalp.builder import prepare

    geo = node.geometry()
    socket_prims = [
        prim for prim in prims_by_attr(geo, "region", base_attributes.Region.COXASOCKET, startswith=True)
        if prim.boundingBox().center().x() > 0
    ]
    assert len(socket_prims) == 8, f"Expected 8 right coxa socket prims, got {len(socket_prims)}"

    used_points = (
            {v.point() for prim in socket_prims for v in prim.vertices()}
            | prepare(geo)
    )
    unused_points = [p for p in geo.points() if p not in used_points]
    geo.deletePoints(unused_points)

    socket_corners, socket_midpoints = _get_right_coxa_socket_points(node)
    geo.deletePrims(geo.prims(), keep_points=True)

    flat_corner_nums = [p.number() for group in socket_corners for p in group]
    geo.addArrayAttrib(hou.attribType.Global, "tmp_coxa_corners", hou.attribData.Int)
    geo.setGlobalAttribValue("tmp_coxa_corners", flat_corner_nums)

    flat_midpoint_nums = [p.number() for group in socket_midpoints for p in group]
    geo.addArrayAttrib(hou.attribType.Global, "tmp_coxa_midpoints", hou.attribData.Int)
    geo.setGlobalAttribValue("tmp_coxa_midpoints", flat_midpoint_nums)

def _get_right_coxa_socket_points(
    node: hou.SopNode,
) -> tuple[list[list[hou.Point]], list[list[hou.Point]]]:
    geo = node.geometry()
    prims = prims_by_attr(geo, "region", base_attributes.Region.COXASOCKET, startswith=True)
    prims = sorted(prims, key=lambda p: p.boundingBox().center().z())
    assert len(prims) == 8, f"Expected 8 socket prims, got {len(prims)}"

    groups = [prims[i:i + 2] for i in range(0, 8, 2)]
    corner_result = []
    midpoint_result = []
    for group in groups:
        corners, midpoints = _get_socket_group_points(group)
        corner_result.append(corners)
        midpoint_result.append(midpoints)

    return corner_result, midpoint_result


def _get_socket_group_points(
    group: list[hou.Prim],
) -> tuple[list[hou.Point], list[hou.Point]]:
    group_points = {
        vertex.point()
        for prim in group
        for vertex in prim.vertices()
    }
    assert len(group_points) == 6, f"Expected 6 unique points in socket group, got {len(group_points)}"

    first_points = {vertex.point() for vertex in group[0].vertices()}
    second_points = {vertex.point() for vertex in group[1].vertices()}
    shared_points = first_points & second_points
    outer_points = list(group_points - shared_points)
    assert len(outer_points) == 4, f"Expected 4 outer points, got {len(outer_points)}"
    assert len(shared_points) == 2, f"Expected 2 shared points, got {len(shared_points)}"

    mid_y = sum(point.position().y() for point in outer_points) / 4.0
    top_points = [point for point in outer_points if point.position().y() >= mid_y]
    bottom_points = [point for point in outer_points if point.position().y() < mid_y]
    assert len(top_points) == 2 and len(bottom_points) == 2

    top_points.sort(key=lambda point: point.position().z())
    bottom_points.sort(key=lambda point: point.position().z())
    corners = [top_points[0], top_points[1], bottom_points[0], bottom_points[1]]
    midpoints = sorted(shared_points, key=lambda point: point.position().y(), reverse=True)
    return corners, midpoints


def remove_tmp_attributes(node: hou.SopNode) -> None:
    remove_attribs(node.geometry(), global_attributes=("tmp_coxa_corners", "tmp_coxa_midpoints"))


def get_front_coxa_socket_size(geo: hou.Geometry) -> tuple[float, float]:
    """

    :param geo:
    :return: width, length
    """
    corners = geo.attribValue("tmp_coxa_corners")
    pts = [geo.iterPoints()[p] for p in corners[:4]]

    pos_top_sz, pos_top_bz, pos_btm_sz, pos_btm_bz = points_to_positions(pts)

    width = (pos_top_bz - pos_top_sz).length()
    top_mid = (pos_top_sz + pos_top_bz) / 2.0
    btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
    height = top_mid.y() - btm_mid.y()

    return width, height
