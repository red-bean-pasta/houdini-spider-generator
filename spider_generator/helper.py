from collections.abc import Callable, Sequence
from typing import Any, Iterator

import hou

from houkit.attributer import (
    add_point_attrib,
    deduplicate_point_attribs,
    modify_point_attribs,
    scan_indexed_attrib_range,
    set_point_attrib,
    set_points_attrib,
    unique_points_by_attrib,
    unique_points_start_with, points_by_attrib,
)
from houkit.formatter import affix_text
from houkit.noder import sopify
from houkit.topology import add_point, fill_face, fill_face_by_attrib, inset


def affix_id(prefix: str, *affixes: int | str | float) -> str:
    return affix_text(prefix, *affixes)


def add_id_attr(geo: hou.Geometry, default: str = "") -> hou.Attrib:
    return add_point_attrib(geo, "id", default)


def add_id_point(geo: hou.Geometry, position: hou.Vector3, value: str) -> hou.Point:
    return add_point(geo, position, ("id", value))


def replace_points(
    geo: hou.Geometry,
    point_data: Sequence[tuple[str, hou.Vector3]],
) -> list[hou.Point]:
    geo.clear()
    add_id_attr(geo)
    return [add_id_point(geo, position, point_id) for point_id, position in point_data]


def fill_face_with_attr(
    geo: hou.Geometry,
    points: Sequence[hou.Point],
    attribute: str,
    value: Any,
    reverse: bool = False,
) -> hou.Polygon:
    polygon = fill_face(points, reverse)
    polygon.setAttribValue(attribute, value)
    return polygon


def bridge_loops(
    geo: hou.Geometry,
    first_loop: Sequence[hou.Point],
    second_loop: Sequence[hou.Point],
    reverse: bool = False,
    cross_order: bool = False,
    primitive_attr: tuple[str, Any] | None = None,
) -> list[hou.Polygon]:
    assert len(first_loop) == len(second_loop) >= 2, "Expected equally sized loops with at least two points"
    polygons = []
    for index in range(len(first_loop)):
        next_index = (index + 1) % len(first_loop)
        points = (
            [first_loop[next_index], first_loop[index], second_loop[index], second_loop[next_index]]
            if cross_order
            else [first_loop[index], first_loop[next_index], second_loop[next_index], second_loop[index]]
        )
        if primitive_attr is None:
            polygon = fill_face(points, reverse)
        else:
            polygon = fill_face_with_attr(geo, points, primitive_attr[0], primitive_attr[1], reverse)
        polygons.append(polygon)
    return polygons


def prims_by_attr(
    geo: hou.Geometry | Sequence[hou.Prim],
    attribute: str,
    value: str | tuple[str, ...],
    startswith: bool = False,
) -> list[hou.Prim]:
    prims = geo.prims() if hasattr(geo, "prims") else geo
    if startswith:
        return [prim for prim in prims if prim.stringAttribValue(attribute).startswith(value)]
    return [prim for prim in prims if prim.stringAttribValue(attribute) == value]


def set_prim_attr_where_blank(
    geo: hou.Geometry,
    attribute: str,
    value: Any,
) -> None:
    for prim in geo.prims():
        if not prim.stringAttribValue(attribute):
            prim.setAttribValue(attribute, value)


def sopify_chain(
    parent: hou.SopNode,
    input_node: hou.SopNode | None,
    stages: Sequence[Callable[[], None] | Callable[[hou.SopNode], None]],
) -> hou.SopNode:
    current = input_node
    for stage in stages:
        current = sopify(parent, current, stage)
    assert current is not None, "Expected a chain with at least one stage"
    return current


def points_from_loop_cut(
    cut_edges: dict[tuple[hou.Point, hou.Point], tuple[hou.Prim, hou.Prim]],
) -> list[hou.Point]:
    edges = list(cut_edges)
    if not edges:
        return []

    points = [edges[0][0]]
    for start, end in edges:
        assert points[-1] == start, "Loop cut edges are not ordered"
        points.append(end)
    if points[-1] == points[0]:
        points.pop()
    return points


def inset_inner_prims(
    geo: hou.Geometry,
    prims: list[hou.Prim],
    scalar: float,
    use_ratio: bool = True,
    follow_existing_edge: bool = True,
) -> list[hou.Prim]:
    if not prims or scalar == 0:
        return list(prims)

    prim_count_before = len(geo.prims())
    components = inset(prims, scalar, use_ratio, follow_existing_edge)
    created_prims = list(geo.prims())[prim_count_before - len(prims):]

    inner_prims: list[hou.Prim] = []
    created_index = 0
    for inner_component, border_prims in components.items():
        inner_count = len(inner_component)
        inner_prims.extend(created_prims[created_index:created_index + inner_count])
        created_index += inner_count + len(border_prims)

    assert created_index == len(created_prims), "Unexpected inset primitive layout"
    return inner_prims


def points_by_id(
    geo: hou.Geometry | hou.Prim | Sequence[hou.Prim],
) -> dict[str, hou.Point]:
    return unique_points_by_attrib(geo, "id")


def points_from_geo(geo: hou.Geometry, *point_ids: str) -> tuple[hou.Point, ...]:
    """Return the geometry points identified by ``point_ids`` in the same order."""
    points = points_by_id(geo)
    return tuple(points[point_id] for point_id in point_ids)

def positions_from_geo(geo: hou.Geometry, *point_ids: str) -> tuple[hou.Vector3, ...]:
    """Return the geometry points' positions identified by ``point_ids`` in the same order."""
    points = points_by_id(geo)
    return tuple(points[point_id].position() for point_id in point_ids)

def positions_from_points(*points: hou.Point) -> tuple[hou.Vector3, ...]:
    return tuple(p.position() for p in points)


def set_point_id(point: hou.Point, value: str) -> None:
    set_point_attrib(point, "id", value)


def set_points_id(points: Sequence[hou.Point], values: Sequence[str]) -> None:
    set_points_attrib(points, "id", values)


def get_id_range(geo: hou.Geometry, prefix: str) -> tuple[int, int] | None:
    return scan_indexed_attrib_range(geo, "id", prefix)


def fill_face_by_id(geo: hou.Geometry, values: Sequence[str], reverse: bool = False) -> hou.Polygon:
    return fill_face_by_attrib(geo, "id", values, reverse)


def fill_face_by_id_with_attr(
    geo: hou.Geometry,
    values: Sequence[str],
    attribute: str,
    value: Any,
    reverse: bool = False,
) -> hou.Polygon:
    polygon = fill_face_by_id(geo, values, reverse)
    polygon.setAttribValue(attribute, value)
    return polygon


def unique_points_start_with_id(
    geo: hou.Geometry,
    prefixes: str | tuple[str, ...],
) -> dict[str, hou.Point]:
    if isinstance(prefixes, str):
        prefixes = (prefixes,)
    return {
        point_id: point
        for points in unique_points_start_with(geo, "id", prefixes).values()
        for point_id, point in points.items()
    }


def deduplicate_id_attr(
    geo: hou.Geometry,
    prefix: str | tuple[str, ...] | None = None,
    add_affix: bool = False,
    keep_first: bool = True,
) -> None:
    deduplicate_point_attribs(geo, "id", prefix, add_affix=add_affix, keep_first=keep_first)


def rename_left_ids(geo: hou.Geometry, affix_index: int | None = 0) -> None:
    """Rename point IDs for mirrored geometry on the left side (x < 0).

    Negates the numeric affix at the given `affix_index` (default 0).
    - If `affix_index` is an integer: negates the affix at that index, supporting negative indexing like `list[-1]` to negate the last affix.
    - If `affix_index` is None: negates all affixes.

    If an ID has only a single affix (e.g. "cheliceraestart1"), that affix is negated even if `affix_index` is out of range.
    """
    modify_point_attribs(
        geo,
        "id",
        _is_left_point,
        lambda point_id: _rename_point_id(point_id, affix_index),
    )


def _is_left_point(point: hou.Point) -> bool:
    return point.position()[0] < 0.0


def _rename_point_id(point_id: str, affix_index: int | None) -> str | None:
    parts = point_id.split("_")
    first_digit = next(
        (index for index, character in enumerate(parts[0]) if character.isdigit() or character == "-"),
        None,
    )
    if first_digit is not None:
        prefix = parts[0][:first_digit]
        affixes = [parts[0][first_digit:]] + parts[1:]
    elif len(parts) > 1:
        prefix = parts[0] + "_"
        affixes = parts[1:]
    else:
        return None

    if affix_index is None:
        affixes = [_negate_id_affix(affix) for affix in affixes]
    else:
        try:
            affixes[affix_index] = _negate_id_affix(affixes[affix_index])
        except IndexError:
            if len(affixes) == 1:
                affixes[0] = _negate_id_affix(affixes[0])

    return prefix + "_".join(affixes)


def _negate_id_affix(value: str) -> str:
    if not value:
        return value
    return value[1:] if value.startswith("-") else f"-{value}"


def rename_left_ids_node(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry())