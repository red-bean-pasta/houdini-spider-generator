import math
from enum import StrEnum, auto
from typing import Iterable, Sequence

import hou

import hom_helper
import sternum_sops
from sternum_sops import ID as STERNUM_ID
from hom_helper import (
    get_parent, get_float_parm,
    add_new_prim_attr, add_new_id_attr,
    points_by_id, unique_points_start_with,
    set_points_id,
    fill_face,
    affix_id, get_id_range,
    sopify,
)
from sternum_sops import sternumrim


class ID(StrEnum):
    BASESTERNUM = auto()
    BASESTERNUMMIDDLE = auto()
    BASEMAXILLA = auto()
    BASEEND = auto()

def basesternum(*i: int | str) -> str:
    return affix_id(ID.BASESTERNUM, *i)
def basesternummiddle(*i: int | str) -> str:
    return affix_id(ID.BASESTERNUMMIDDLE, *i)
def basemaxilla(*i: int | str) -> str:
    return affix_id(ID.BASEMAXILLA, *i)
def baseend(*i: int | str) -> str:
    return affix_id(ID.BASEEND, *i)

def outer_loop_ids() -> tuple[str, ...]:
    return ID.BASESTERNUM, ID.BASEMAXILLA, ID.BASESTERNUMMIDDLE, ID.BASEEND


def extract_sternum_rim(node: hou.SopNode) -> None:
    geo = node.geometry()
    sternum_rim = {
        point_id: point.position()
        for point_id, point in unique_points_start_with(geo, sternum_sops.outer_loop_ids()).items()
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

    geo.clear()
    add_new_id_attr(geo)
    points = {}
    for point_id, position in sternum_rim.items():
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)
        points[point_id] = point

    for start_id, end_id in rim_edges:
        edge = geo.createPolygon(is_closed=False)
        edge.addVertex(points[start_id])
        edge.addVertex(points[end_id])


def build_coxa_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    width_x = get_float_parm(parent, "coxa_width_ratiox")
    width_y = get_float_parm(parent, "coxa_width_ratioy")
    flap_ratio = width_y / max(width_x, 1e-6)

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
        direction[2],
        0.0,
        -direction[0],
    ) / edge_length
    offset = outward * edge_length * flap_ratio * 2.0

    outer_start = geo.createPoint()
    outer_start.setPosition(start_position + offset)
    outer_end = geo.createPoint()
    outer_end.setPosition(end_position + offset)
    set_points_id(
        [outer_start, outer_end],
        [_get_extruded_id(start), _get_extruded_id(end)],
    )
    fill_face(geo, [start, end, outer_end, outer_start])


def add_flap_regions(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    add_new_prim_attr(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", "coxa")
    for prim in (geo.prim(0), geo.prim(1)):
        prim.setAttribValue("region", "labium")


def connect_side_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    hom_helper.deduplicate_points(geo, ID.BASESTERNUM, affix=True)
    points = points_by_id(geo)
    count = get_id_range(geo, ID.BASESTERNUM)[1]
    for side in (-1, 1):
        for index in range(2, count):
            first = points[basesternum(side * index, 1)]
            second = points[basesternum(side * index, 2)]
            midpoint = (first.position() + second.position()) / 2.0
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
    height_ratio = get_float_parm(parent, "coxa_width_ratioy") / max(get_float_parm(parent, "coxa_width_ratiox"), 1e-6)
    depth_ratio = min(get_float_parm(parent, "coxa_depth_ratio"), height_ratio)
    rise_scale = depth_ratio / height_ratio if height_ratio > 1e-6 else 0.0

    for primitive in geo.prims():
        points = list(primitive.points())
        assert len(points) == 4, f"Expected a coxa flap quad, got {len(points)} points"
        for origin, outer in ((points[0], points[3]), (points[1], points[2])):
            offset = outer.position() - origin.position()
            height = offset.length()
            if height <= 1e-6:
                continue

            rise = height * rise_scale
            projected = math.sqrt(max(0.0, height * height - rise * rise))
            projection_scale = projected / height
            offset = hou.Vector3(
                offset[0] * projection_scale,
                rise,
                offset[2] * projection_scale,
            )
            outer.setPosition(origin.position() + offset)

def adjust_frontest_line(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    line_start = points[basesternum(-1, 2)].position()
    line_end = points[basesternum(1, 2)].position()
    line_direction = line_end - line_start
    line_length_squared = line_direction.dot(line_direction)
    assert line_length_squared > 1e-12, "Expected distinct frontest line endpoints"

    for point_id in (
        basesternum(0),
        basesternum(1, 1),
        basesternum(-1, 1),
    ):
        point = points[point_id]
        position = point.position()
        line_parameter = (position - line_start).dot(line_direction) / line_length_squared
        point.setPosition(line_start + line_direction * line_parameter)


def fill_maxilla(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    starts = [
        points[basesternum(1, 1)],
        points[basesternum(-1, 1)],
    ]
    ends = [
        points[basesternum(1, 2)],
        points[basesternum(-1, 2)],
    ]
    centers = [
        points[basesternum(0)],
        points[basesternum(0)],
    ]
    pivots = [
        points[sternumrim(1)],
        points[sternumrim(-1)],
    ]
    add_new_prim_attr(geo, "region", "")

    for side, (start, end, center, pivot) in enumerate(zip(starts, ends, centers, pivots)):
        start_position = start.position()
        end_position = end.position()
        center_position = center.position()
        direction = end_position - start_position
        direction_length = direction.length()
        assert direction_length > 1e-6, "Expected distinct maxilla endpoints"
        direction /= direction_length
        maxilla = geo.createPoint()
        maxilla.setPosition(start_position + direction * (center_position - start_position).length())
        maxilla.setAttribValue("id", f"basemaxilla{1 if side == 0 else -1}")
        primitive = fill_face(geo, [start, maxilla, end, pivot])
        primitive.setAttribValue("region", "maxilla")

def fill_pedicel_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    p5 = points[sternumrim(5)]
    e5_1 = points[basesternum(5, 1)]
    e5_2 = points[basesternum(5, 2)]

    p5_position = p5.position()
    e5_1_offset = e5_1.position() - p5_position
    e5_2_offset = e5_2.position() - p5_position
    horizontal = hou.Vector3(e5_1_offset[0] + e5_2_offset[0], 0.0, e5_1_offset[2] + e5_2_offset[2])
    horizontal_length = horizontal.length(); assert horizontal_length > 1e-6, "Expected a nonzero pedicel direction"
    horizontal /= horizontal_length
    px_offset = horizontal * math.sqrt(e5_1_offset[0] ** 2 + e5_1_offset[2] ** 2)
    px_offset[1] = (e5_1_offset[1] + e5_2_offset[1]) / 2.0

    px0 = geo.createPoint()
    px0.setPosition(p5_position + px_offset)
    px0.setAttribValue("id", "baseend0")
    primitive = fill_face(geo, [px0, e5_1, p5, e5_2])
    primitive.setAttribValue("region", "basepedicelmembrane")


def inset_membrane(parent: hou.SopNode, coxa: hou.SopNode) -> hou.SopNode:
    attr_prepared = sopify(parent, coxa, _prepare_membrane_attributes)
    front_prepared = sopify(parent, attr_prepared, _prepare_front_membrane)
    maxilla_prepared = sopify(parent, front_prepared, _prepare_maxilla_membrane)
    side_prepared = sopify(parent, maxilla_prepared, _prepare_side_membrane)
    side_split = sopify(parent, side_prepared, _identify_side_inset_split)

    side = parent.createNode("polyextrude", "inset_side_membrane")
    side.setInput(0, side_split)
    side.parm("group").set("@region=coxa")
    side.parm("splittype").set(1)
    side.parm("usesplitgroup").set(1)
    side.parm("splitgroup").set("tmp_side_split")
    side.parm("inset").setExpression('ch("../membrane_ratio")')
    side.parm("uselocalinsetscaleattrib").set(1)
    side.parm("localinsetscaleattrib").set("tmp_insetscale")

    classify_side = sopify(parent, side, _classify_side)

    front = parent.createNode("polyextrude", "inset_front_membrane")
    front.setInput(0, classify_side)
    front.parm("group").set("@region=labium")
    front.parm("splittype").set(1)
    front.parm("inset").setExpression('ch("../membrane_ratio")')
    front.parm("uselocalinsetscaleattrib").set(1)
    front.parm("localinsetscaleattrib").set("tmp_insetscale")

    classify_front = sopify(parent, front, _classify_front)

    maxilla = parent.createNode("polyextrude", "inset_maxilla")
    maxilla.setInput(0, classify_front)
    maxilla.parm("group").set("@region=maxilla")
    maxilla.parm("splittype").set(0)
    maxilla.parm("inset").setExpression('ch("../membrane_ratio")')
    maxilla.parm("uselocalinsetscaleattrib").set(1)
    maxilla.parm("localinsetscaleattrib").set("tmp_insetscale")

    classify_maxilla = sopify(parent, maxilla, _classify_maxilla)

    cleanup = sopify(parent, classify_maxilla, _cleanup_temp_attributes)
    return cleanup

def _prepare_membrane_attributes(node: hou.SopNode) -> None:
    geo = node.geometry()
    add_new_prim_attr(geo, "tmp_insetscale", 0.0)

def _prepare_maxilla_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    prims = [
        p
        for p in geo.prims()
        if p.stringAttribValue("region") == "maxilla"
    ]; assert prims is not None and len(prims) == 2
    pivot = points[sternumrim(1)]
    outer = points[basesternum(1, 1)]
    for pm in prims:
        pm.setAttribValue("tmp_insetscale", (pivot.position() - outer.position()).length())

def _prepare_front_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()
    for prim in geo.prims():
        points = points_by_id(prim)
        pivot = points.get(sternumrim(0))
        outer = points.get(basesternum(0))
        if pivot is None or outer is None:
            continue
        prim.setAttribValue("tmp_insetscale", (pivot.position() - outer.position()).length())

def _prepare_side_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()

    for prim in geo.prims():
        dic = points_by_id(prim)
        points = list(dic.values())
        midpoint = next(
            (p for k, p in dic.items() if k.startswith(STERNUM_ID.STERNUMMIDDLE)),
            None,
        )
        if midpoint is None:
            continue

        midpoint_index = points.index(midpoint)
        outer_index = {
            0: 3,
            1: 2,
        }.get(midpoint_index)
        if outer_index is None:
            continue

        outer = points[outer_index]
        prim.setAttribValue("tmp_insetscale", (midpoint.position() - outer.position()).length())

def _identify_side_inset_split(node: hou.SopNode) -> None:
    geo = node.geometry()
    hom_helper.find_quad_polyextrude_splits(
        geo,
        [
            point
            for point in geo.points()
            if point.stringAttribValue("id").startswith(STERNUM_ID.STERNUMMIDDLE)
        ],
        "tmp_side_split"
    )

def _classify_side(node: hou.SopNode) -> None:
    _classify_membrane_and_socket(node, "coxasocket", "coxamembrane", 2)

def _classify_front(node: hou.SopNode) -> None:
    _classify_membrane_and_socket(node, "labiumsocket", "labiummembrane", 2)

def _classify_maxilla(node: hou.SopNode) -> None:
    _classify_membrane_and_socket(node, "maxillasocket", "maxillamembrane")

def _classify_membrane_and_socket(
        node: hou.SopNode,
        socket_prefix: str,
        membrane_prefix: str,
        horizontal_pack_size: int = 1,
) -> None:
    hom_helper.attribute_after_inset(node, "region", socket_prefix, membrane_prefix, horizontal_pack_size)


def _cleanup_temp_attributes(node: hou.SopNode) -> None:
    geo = node.geometry()
    hom_helper.remove_attributes(geo, prim_attribs="tmp_insetscale")
    hom_helper.remove_groups(geo, edge_groups="tmp_side_split")
    hom_helper.deduplicate_points(geo, None, "id", False)
