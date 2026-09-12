from collections.abc import Callable, Sequence
from typing import Any, Literal

import hou

from utilities.common import (
    add_point,
    add_point_attr,
    affix_attribute_value,
    fill_face,
    set_point_attr,
    set_points_attr,
)
from utilities.identifying import (
    deduplicate_point_attributes,
    fill_face_by_attr,
    indexed_attr_range,
    points_by_unique_attr,
    rename_point_attr,
    unique_points_start_with,
)
from utilities.nodes import sopify


def affix_id(prefix: str, *affixes: int | str | float) -> str:
    return affix_attribute_value(prefix, *affixes)


def add_id_attr(geo: hou.Geometry, default: str = "") -> hou.Attrib:
    return add_point_attr(geo, "id", default)


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
    polygon = fill_face(geo, points, reverse)
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
            polygon = fill_face(geo, points, reverse)
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


def points_by_id(
    geo: hou.Geometry | hou.Prim | Sequence[hou.Prim],
) -> dict[str, hou.Point]:
    return points_by_unique_attr(geo, "id")


def point_from_geo(geo: hou.Geometry, *point_ids: str) -> tuple[hou.Point, ...]:
    """Return the geometry points identified by ``point_ids`` in the same order."""
    points = points_by_id(geo)
    return tuple(points[point_id] for point_id in point_ids)

def position_from_geo(geo: hou.Geometry, *point_ids: str) -> tuple[hou.Vector3, ...]:
    """Return the geometry points' positions identified by ``point_ids`` in the same order."""
    points = points_by_id(geo)
    return tuple(points[point_id].position() for point_id in point_ids)


def set_point_id(point: hou.Point, value: str) -> None:
    set_point_attr(point, "id", value)


def set_points_id(points: Sequence[hou.Point], values: Sequence[str]) -> None:
    set_points_attr(points, "id", values)


def get_id_range(geo: hou.Geometry, prefix: str) -> tuple[int, int] | None:
    return indexed_attr_range(geo, "id", prefix)


def fill_face_by_id(geo: hou.Geometry, values: Sequence[str], reverse: bool = False) -> hou.Polygon:
    return fill_face_by_attr(geo, "id", values, reverse)


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
    return unique_points_start_with(geo, "id", prefixes)


def deduplicate_id_attr(
    geo: hou.Geometry,
    prefix: str | tuple[str, ...] | None = None,
    add_affix: bool = False,
    keep_first: bool = True,
) -> None:
    deduplicate_point_attributes(geo, "id", prefix, add_affix=add_affix, keep_first=keep_first)


def rename_left_ids(geo: hou.Geometry, affix_index: int | None = 0) -> None:
    """Rename point IDs for mirrored geometry on the left side (x < 0).

    Negates the numeric affix at the given `affix_index` (default 0).
    - If `affix_index` is an integer: negates the affix at that index, supporting negative indexing like `list[-1]` to negate the last affix.
    - If `affix_index` is None: negates all affixes.

    If an ID has only a single affix (e.g. "cheliceraestart1"), that affix is negated even if `affix_index` is out of range.
    """
    def filtrate(p: hou.Point) -> bool:
        return p.position()[0] < 0.0

    def rename(point_id: str) -> str | Literal[False]:
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
            return False

        def negate(val: str) -> str:
            if not val:
                return val
            return val[1:] if val.startswith("-") else f"-{val}"

        if affix_index is None:
            affixes = [negate(a) for a in affixes]
        else:
            try:
                affixes[affix_index] = negate(affixes[affix_index])
            except IndexError:
                if len(affixes) == 1:
                    affixes[0] = negate(affixes[0])

        return prefix + "_".join(affixes)

    rename_point_attr(geo, "id", filtrate, rename)


def rename_left_ids_node(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry())
