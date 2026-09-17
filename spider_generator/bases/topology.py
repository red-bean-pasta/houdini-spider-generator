import math

import hou

from houkit.attributer import add_prim_attrib, deduplicate_point_attribs
from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm
from houkit.topology import outset
from . import coxa_flaps, membrane, hinge_retopology
from .attributes import ID, Region, basesternum, basesternummiddle, outer_loop_ids
from ..sternums import attributes as sternum_attributes
from ..helper import (
    add_id_point,
    deduplicate_id_attr,
    fill_face_with_attr,
    get_id_range,
    points_by_id,
    points_from_geo,
    replace_points,
    unique_points_start_with_id,
)


def extract_sternum_rim(node: hou.SopNode) -> None:
    geo = node.geometry()
    sternum_rim = {
        point_id: point.position()
        for point_id, point in unique_points_start_with_id(geo, sternum_attributes.outer_loop_ids()).items()
        if not point_id.startswith(sternum_attributes.sternumriminner())
    }
    rim_edges = [
        tuple(point.stringAttribValue("id") for point in edge.points())
        for edge in geo.globEdges("*")
        if all(
            point.stringAttribValue("id") in sternum_rim
            for point in edge.points()
        )
    ]
    assert len(rim_edges) == len(sternum_rim), "Expected one edge per sternum rim point"

    points = dict(zip(sternum_rim, replace_points(geo, sternum_rim.items())))

    for start_id, end_id in rim_edges:
        edge = geo.createPolygon(is_closed=False)
        edge.addVertex(points[start_id])
        edge.addVertex(points[end_id])


def build_coxa_flaps(node: hou.SopNode) -> None:
    coxa_flaps.build_coxa_flaps(node)


def add_flap_regions(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    add_prim_attrib(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", Region.COXA)
    for prim in (geo.prim(0), geo.prim(1)):
        prim.setAttribValue("region", Region.LABIUM)


def connect_side_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    deduplicate_id_attr(geo, ID.BASESTERNUM, add_affix=True)
    count = get_id_range(geo, ID.BASESTERNUM)[1]
    for side in (-1, 1):
        for index in range(2, count):
            first, second = points_from_geo(
                geo,
                basesternum(side * index, 1),
                basesternum(side * index, 2),
            )
            prev_mid, curr_mid = points_from_geo(
                geo,
                basesternummiddle(side * (index - 1)),
                basesternummiddle(side * index),
            )
            midpoint = (prev_mid.position() + curr_mid.position()) / 2.0
            first.setPosition(midpoint)
            second.setPosition(midpoint)


def adjust_front_and_end_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    for side in (1, -1):
        target, opposite, sternum_middle, base_middle = points_from_geo(
            geo,
            basesternum(side, 2),
            basesternum(side * 2, 1),
            sternum_attributes.sternummiddle(side),
            basesternummiddle(side),
        )
        _reflect_point_across_edge(target, opposite, (sternum_middle, base_middle))

    for side, target_minor in ((1, 1), (-1, 2)):
        target, opposite, sternum_middle, base_middle = points_from_geo(
            geo,
            basesternum(5, target_minor),
            basesternum(side * 4, 2),
            sternum_attributes.sternummiddle(side * 4),
            basesternummiddle(side * 4),
        )
        _reflect_point_across_edge(target, opposite, (sternum_middle, base_middle))


def cleanup_connected_side_flap_ids(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    count = get_id_range(geo, ID.BASESTERNUM)[1]
    for i in range(2, count):
        for major in (i, -i):
            point = next(
                (
                    points.get(basesternum(major, minor))
                    for minor in (1, 2)
                    if points.get(basesternum(major, minor)) is not None
                ),
                None,
            )
            assert point is not None, f"Expected connected side-flap point {basesternum(major)}"
            point.setAttribValue("id", basesternum(major))


def rotate_coxa_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    angle = get_float_parm(parent, "coxa_flap_rise_angle")
    clamped_angle = max(0.0, min(90.0, angle))

    rad = math.radians(clamped_angle)
    sin_angle = math.sin(rad)
    cos_angle = math.cos(rad)

    rotated_points = set()
    for primitive in geo.prims():
        points = list(primitive.points())
        assert len(points) == 4, f"Expected a coxa flap quad, got {len(points)} points"
        for origin, outer in ((points[3], points[0]), (points[2], points[1])):
            if outer.number() in rotated_points:
                continue
            rotated_points.add(outer.number())

            offset = outer.position() - origin.position()
            height = offset.length()
            if height <= 1e-6:
                continue

            rise = height * sin_angle
            projection_scale = cos_angle
            offset = hou.Vector3(
                offset[0] * projection_scale,
                rise,
                offset[2] * projection_scale,
            )
            outer.setPosition(origin.position() + offset)


def adjust_frontest_line(node: hou.SopNode) -> None:
    geo = node.geometry()
    line_start, line_end = points_from_geo(
        geo,
        basesternum(-1, 2),
        basesternum(1, 2),
    )
    line_start = line_start.position()
    line_end = line_end.position()
    line_direction = line_end - line_start
    line_length_squared = line_direction.dot(line_direction)
    assert line_length_squared > 1e-12, "Expected distinct frontest line endpoints"

    for point in points_from_geo(
        geo,
        basesternum(0),
        basesternum(1, 1),
        basesternum(-1, 1),
    ):
        position = point.position()
        line_parameter = (position - line_start).dot(line_direction) / line_length_squared
        point.setPosition(line_start + line_direction * line_parameter)


def fill_maxilla(node: hou.SopNode) -> None:
    geo = node.geometry()
    starts = points_from_geo(geo, basesternum(1, 1), basesternum(-1, 1))
    ends = points_from_geo(geo, basesternum(1, 2), basesternum(-1, 2))
    centers = points_from_geo(geo, basesternum(0), basesternum(0))
    pivots = points_from_geo(geo, sternum_attributes.sternumrim(1), sternum_attributes.sternumrim(-1))
    add_prim_attrib(geo, "region", "")

    for side, (start, end, center, pivot) in enumerate(zip(starts, ends, centers, pivots)):
        start_position = start.position()
        end_position = end.position()
        center_position = center.position()
        direction = end_position - start_position
        direction_length = direction.length()
        assert direction_length > 1e-6, "Expected distinct maxilla endpoints"
        direction /= direction_length
        maxilla = add_id_point(
            geo,
            start_position + direction * (center_position - start_position).length(),
            f"basemaxilla{1 if side == 0 else -1}",
        )
        fill_face_with_attr(geo, [start, maxilla, end, pivot], "region", Region.MAXILLA, side == 0)


def fill_pedicel_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()
    p5, e5_1, e5_2 = points_from_geo(
        geo,
        sternum_attributes.sternumrim(5),
        basesternum(5, 1),
        basesternum(5, 2),
    )

    p5_position = p5.position()
    e5_1_offset = e5_1.position() - p5_position
    e5_2_offset = e5_2.position() - p5_position
    horizontal = hou.Vector3(e5_1_offset[0] + e5_2_offset[0], 0.0, e5_1_offset[2] + e5_2_offset[2])
    horizontal_length = horizontal.length()
    assert horizontal_length > 1e-6, "Expected a nonzero pedicel direction"
    horizontal /= horizontal_length
    px_offset = horizontal * math.sqrt(e5_1_offset[0] ** 2 + e5_1_offset[2] ** 2)
    px_offset[1] = (e5_1_offset[1] + e5_2_offset[1]) / 2.0

    px0 = add_id_point(geo, p5_position + px_offset, "baseend0")
    fill_face_with_attr(geo, [px0, e5_1, p5, e5_2], "region", Region.BASEPEDICELMEMBRANE)


def adjust_mouth(node: hou.SopNode) -> None:
    geo = node.geometry()
    center, right, left = points_from_geo(
        geo,
        basesternum(0),
        basesternum(1, 1),
        basesternum(-1, 1),
    )
    ratio = 1 / 3
    center_position = center.position()
    for point in (right, left):
        point.setPosition(point.position() * ratio + center_position * (1 - ratio))


def inset_membrane(node: hou.SopNode) -> None:
    membrane.inset_membrane(node)


def retopo_corners(node: hou.SopNode) -> None:
    hinge_retopology.retopo_corners(node)


def extrude_base_buffer(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    dist = get_float_parm(parent, "membrane_ratio") * 50
    outer_prims = [
        prim
        for component in outset(list(geo.prims()), dist, use_ratio=False).values()
        for prim in component
    ]
    for prim in outer_prims:
        prim.setAttribValue("region", Region.BASEBUFFERMEMBRANE)

    deduplicate_point_attribs(geo, "id", outer_loop_ids(), keep_first=False)


def _reflect_point_across_edge(
    target: hou.Point,
    opposite: hou.Point,
    edge: tuple[hou.Point, hou.Point],
) -> None:
    edge_start, edge_end = (point.position() for point in edge)
    edge_vector = edge_end - edge_start
    edge_length_squared = edge_vector.dot(edge_vector)
    assert edge_length_squared > 1e-12, "Expected distinct flap-edge endpoints"

    source_offset = opposite.position() - edge_start
    projection = edge_start + edge_vector * (source_offset.dot(edge_vector) / edge_length_squared)
    target.setPosition(projection * 2.0 - opposite.position())
