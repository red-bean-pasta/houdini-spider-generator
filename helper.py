from collections.abc import Sequence
from typing import Literal

import hou

from utilities.common import (
    add_point_attr,
    affix_attribute_value,
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


def affix_id(prefix: str, *affixes: int | str | float) -> str:
    return affix_attribute_value(prefix, *affixes)


def add_id_attr(geo: hou.Geometry, default: str = "") -> hou.Attrib:
    return add_point_attr(geo, "id", default)


def points_by_id(
    geo: hou.Geometry | hou.Prim | Sequence[hou.Prim],
) -> dict[str, hou.Point]:
    return points_by_unique_attr(geo, "id")


def point_from_geo(geo: hou.Geometry, *point_ids: str) -> tuple[hou.Point, ...]:
    """Return the geometry points identified by ``point_ids`` in the same order."""
    points = points_by_id(geo)
    return tuple(points[point_id] for point_id in point_ids)


def set_point_id(point: hou.Point, value: str) -> None:
    set_point_attr(point, "id", value)


def set_points_id(points: Sequence[hou.Point], values: Sequence[str]) -> None:
    set_points_attr(points, "id", values)


def get_id_range(geo: hou.Geometry, prefix: str) -> tuple[int, int] | None:
    return indexed_attr_range(geo, "id", prefix)


def fill_face_by_id(geo: hou.Geometry, values: Sequence[str], reverse: bool = False) -> hou.Polygon:
    return fill_face_by_attr(geo, "id", values, reverse)


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


def find_quad_polyextrude_splits(
    geo: hou.Geometry,
    reference_points: list[hou.Point],
    split_group_name: str,
) -> None:
    split_group = geo.findEdgeGroup(split_group_name)
    if split_group is None:
        split_group = geo.createEdgeGroup(split_group_name)
    for split_point in reference_points:
        primitives = split_point.prims()
        assert len(primitives) == 2, f"Expected point {split_point.number()} to belong to exactly 2 primitives, got {len(primitives)}"
        first, second = primitives

        common_points = set(first.points()) & set(second.points())
        assert len(common_points) == 2, f"Expected primitives {first.number()} and {second.number()} around point {split_point.number()} to share exactly 2 points, got {len(common_points)}"
        assert split_point in common_points, f"Shared edge between primitives {first.number()} and {second.number()} does not contain point {split_point.number()}"

        for primitive in primitives:
            primitive_points = primitive.points()
            assert len(primitive_points) == 4, f"Expected primitive {primitive.number()} to be a quad, got {len(primitive_points)} points"

            opposite_points = [
                point
                for point in primitive_points
                if point not in common_points
            ]
            assert len(opposite_points) == 2, f"Could not determine opposite edge of primitive {primitive.number()}"

            edge = geo.findEdge(opposite_points[0], opposite_points[1])
            assert edge is not None, f"Expected opposite points of primitive {primitive.number()} to form an edge"
            split_group.add(edge)
