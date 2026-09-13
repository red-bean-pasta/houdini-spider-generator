import math
from enum import StrEnum, auto

import hou

from . import sternum
from .sternum import ID as STERNUM_ID
from .sternum import sternumrim
from utilities.common import (
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_parent,
    points_by_attr,
)
from .helper import (
    affix_id,
    deduplicate_id_attr,
    add_id_point,
    fill_face_with_attr,
    get_id_range,
    point_from_geo,
    points_by_id,
    prims_by_attr,
    replace_points,
    unique_points_start_with_id,
)
from utilities.identifying import deduplicate_point_attributes
from utilities.topology import inset, outset


class ID(StrEnum):
    BASESTERNUM = auto()
    BASESTERNUMMIDDLE = auto()
    BASEMAXILLA = auto()
    BASEMAXILLAMEMBRANE = auto()
    BASEEND = auto()


class Region(StrEnum):
    COXA = auto()
    LABIUM = auto()
    MAXILLA = auto()
    COXASOCKET = auto()
    COXAMEMBRANE = auto()
    LABIUMSOCKET = auto()
    LABIUMMEMBRANE = auto()
    MAXILLASOCKET = auto()
    MAXILLAMEMBRANE = auto()
    BASEBUFFERMEMBRANE = auto()
    BASEPEDICELMEMBRANE = auto()


def basesternum(*i: int | str) -> str:
    return affix_id(ID.BASESTERNUM, *i)
def basesternummiddle(*i: int | str) -> str:
    return affix_id(ID.BASESTERNUMMIDDLE, *i)
def basemaxilla(*i: int | str) -> str:
    return affix_id(ID.BASEMAXILLA, *i)
def basemaxillamembrane(*i: int | str) -> str:
    return affix_id(ID.BASEMAXILLAMEMBRANE, *i)
def baseend(*i: int | str) -> str:
    return affix_id(ID.BASEEND, *i)
def outer_loop_ids() -> tuple[str, ...]:
    return ID.BASESTERNUM, ID.BASEMAXILLA, ID.BASESTERNUMMIDDLE, ID.BASEEND


def extract_sternum_rim(node: hou.SopNode) -> None:
    geo = node.geometry()
    sternum_rim = {
        point_id: point.position()
        for point_id, point in unique_points_start_with_id(geo, sternum.outer_loop_ids()).items()
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
    geo = node.geometry()
    parent = get_parent(node)

    flap_ratio = get_float_parm(parent, "coxa_flap_extension_ratio")

    flap_edges = [
        tuple(edge.points())
        for edge in geo.globEdges("*")
        if not any(
            point.stringAttribValue("id").startswith(STERNUM_ID.STERNUMSPINE)
            for point in edge.points()
        )
    ]
    assert flap_edges, "Expected sternum rim edges"
    flap_edges.sort(
        key=lambda edge: (
            (edge[0].position()[2] + edge[1].position()[2]) / 2.0,
            -(edge[0].position()[0] + edge[1].position()[0]) / 2.0,
        )
    )
    geo.deletePrims(list(geo.prims()), keep_points=True)
    for start, end in flap_edges:
        _extrude_edge_outward(geo, start, end, flap_ratio)

def _extrude_edge_outward(
    geo: hou.Geometry,
    start: hou.Point,
    end: hou.Point,
    flap_ratio: float,
) -> None:
    def _get_extruded_id(source: hou.Point) -> str:
        source_id = source.stringAttribValue("id")
        source_id = source_id.replace(STERNUM_ID.STERNUMRIM, ID.BASESTERNUM)
        source_id = source_id.replace(STERNUM_ID.STERNUMMIDDLE, ID.BASESTERNUMMIDDLE)
        return source_id

    start_position = start.position()
    end_position = end.position()
    direction = end_position - start_position
    edge_length = start_position.distanceTo(end_position)
    assert edge_length > 1e-6, f"Expected nonzero edge from {start.number()} to {end.number()}"

    outward = hou.Vector3(
        -direction[2],
        0.0,
        direction[0],
    ) / edge_length
    offset = outward * edge_length * flap_ratio * 2.0

    outer_start = add_id_point(geo, start_position + offset, _get_extruded_id(start))
    outer_end = add_id_point(geo, end_position + offset, _get_extruded_id(end))
    fill_face(geo, [start, end, outer_end, outer_start], True)


def add_flap_regions(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    add_prim_attr(geo, "region", "")
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
            first, second = point_from_geo(
                geo,
                basesternum(side * index, 1),
                basesternum(side * index, 2),
            )
            prev_mid, curr_mid = point_from_geo(
                geo,
                basesternummiddle(side * (index - 1)),
                basesternummiddle(side * index),
            )
            midpoint = (prev_mid.position() + curr_mid.position()) / 2.0
            first.setPosition(midpoint)
            second.setPosition(midpoint)


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
    line_start, line_end = point_from_geo(
        geo,
        basesternum(-1, 2),
        basesternum(1, 2),
    )
    line_start = line_start.position()
    line_end = line_end.position()
    line_direction = line_end - line_start
    line_length_squared = line_direction.dot(line_direction)
    assert line_length_squared > 1e-12, "Expected distinct frontest line endpoints"

    for point in point_from_geo(
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
    starts = point_from_geo(geo, basesternum(1, 1), basesternum(-1, 1))
    ends = point_from_geo(geo, basesternum(1, 2), basesternum(-1, 2))
    centers = point_from_geo(geo, basesternum(0), basesternum(0))
    pivots = point_from_geo(geo, sternumrim(1), sternumrim(-1))
    add_prim_attr(geo, "region", "")

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
    p5, e5_1, e5_2 = point_from_geo(
        geo,
        sternumrim(5),
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


def inset_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    ratio = get_float_parm(parent, "membrane_ratio")
    points = points_by_id(geo)

    _inset_coxa_membranes(geo, points, ratio)
    _inset_membrane_region(
        geo,
        Region.LABIUM,
        Region.LABIUMSOCKET,
        Region.LABIUMMEMBRANE,
        (points[sternumrim(0)], points[basesternum(0)]),
        ratio,
        follow_existing_edge=False,
    )
    _inset_membrane_region(
        geo,
        Region.MAXILLA,
        Region.MAXILLASOCKET,
        Region.MAXILLAMEMBRANE,
        (points[sternumrim(1)], points[basesternum(1, 1)]),
        ratio,
        follow_existing_edge=False,
    )

    _classify_maxilla_membrane_points(geo)
    deduplicate_id_attr(geo, None, add_affix=False)

def _inset_coxa_membranes(geo: hou.Geometry, points: dict[str, hou.Point], ratio: float) -> None:
    side_indices = (*range(1, 5), *range(-4, 0))
    for idx in side_indices:
        sm = points[sternum.sternummiddle(idx)]
        bsm = points[basesternummiddle(idx)]
        dist = ratio * sm.position().distanceTo(bsm.position())
        prims = prims_by_attr(sm.prims(), "region", Region.COXA)
        inner_prims = inset(prims, dist, use_ratio=False, follow_existing_edge=True)
        for prim in inner_prims:
            prim.setAttribValue("region", Region.COXASOCKET)

    for prim in prims_by_attr(geo, "region", Region.COXA):
        prim.setAttribValue("region", Region.COXAMEMBRANE)

def _inset_membrane_region(
    geo: hou.Geometry,
    region: Region,
    socket_region: Region,
    membrane_region: Region,
    baseline: tuple[hou.Point, hou.Point],
    ratio: float,
    follow_existing_edge: bool = True,
) -> None:
    inner_pt, outer_pt = baseline
    dist = ratio * inner_pt.position().distanceTo(outer_pt.position())
    prims = prims_by_attr(geo, "region", region)
    inner_prims = inset(prims, dist, use_ratio=False, follow_existing_edge=follow_existing_edge)
    for prim in inner_prims:
        prim.setAttribValue("region", socket_region)
    for prim in prims_by_attr(geo, "region", region):
        prim.setAttribValue("region", membrane_region)

def _classify_maxilla_membrane_points(geo: hou.Geometry) -> None:
    points_by_id_dict = points_by_attr(geo, "id", skip_blank=True)
    for side in (1, -1):
        for index, name in enumerate(
            (sternumrim(side), basesternum(side, 1), basemaxilla(side), basesternum(side, 2)),
            start=1
        ):
            pts = points_by_id_dict[name]
            inset_pt = max(pts, key=lambda pt: pt.number())
            inset_pt.setAttribValue("id", basemaxillamembrane(side * index))


def extrude_base_buffer(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    dist = get_float_parm(parent, "membrane_ratio") * 50
    outer_prims = outset(list(geo.prims()), dist, use_ratio=False)
    for prim in outer_prims:
        prim.setAttribValue("region", Region.BASEBUFFERMEMBRANE)

    deduplicate_point_attributes(geo, "id", outer_loop_ids(), keep_first=False)
