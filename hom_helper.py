import re
from collections import defaultdict
from typing import Callable, Any, Sequence

import hou


def assert_node(condition: bool, message: str = "") -> None:
   if not condition:
       raise hou.NodeError(message)


def affix_id(prefix: str, *affixes: int | str) -> str:
    return prefix + "_".join(map(str, affixes))


def sopify(
    parent: hou.SopNode,
    input_node: hou.SopNode | None,
    function: Callable[[hou.SopNode], None],
) -> hou.SopNode:
    if "<locals>" in function.__qualname__:
        raise ValueError("Python SOP functions must be module-level functions")

    module = function.__module__
    qualname = function.__qualname__

    node = parent.createNode("python", function.__name__)
    if input_node is not None:
        node.setInput(0, input_node)
    node.parm("python").set(
        f"import {module}\n"
        f"{module}.{qualname}(hou.pwd())"
    )
    return node


def get_parent(node: hou.SopNode) -> hou.SopNode:
    parent = node.parent()
    if not isinstance(parent, hou.SopNode):
        raise hou.NodeError("Expected Python SOP to be inside a SOP network")
    return parent

def get_float_parm(node: hou.SopNode, name: str) -> float:
    parm = node.parm(name)
    if parm is None:
        raise hou.NodeError(f"Expected parameter {name!r} on {node.path()}")
    return parm.evalAsFloat()


def add_edge_group(geo: hou.Geometry, name: str) -> hou.EdgeGroup:
    group = geo.findEdgeGroup(name)
    if group is None:
        group = geo.createEdgeGroup(name)
    return group


def add_new_id_attr(geo: hou.Geometry) -> hou.Attrib:
    return add_new_attr(geo, hou.attribType.Point, "id", "")

def add_new_prim_attr(geo: hou.Geometry, name: str, default: Any) -> hou.Attrib:
    return add_new_attr(geo, hou.attribType.Prim, name, default)

def add_new_edge_attr(geo: hou.Geometry, name: str, default: Any) -> hou.Attrib:
    return add_new_attr(geo, hou.attribType.Edge, name, default)

def add_new_attr(
        geo: hou.Geometry,
        p_type: hou.attribType,
        name: str,
        default: Any,
        skip_existing: bool = True,
) -> hou.Attrib:
    found = geo.findPointAttrib(name)
    if skip_existing and found:
        return found
    return geo.addAttrib(p_type, name, default)


def points_by_id(geo: hou.Geometry | hou.Prim, attribute: str = "id") -> dict[str, hou.Point]:
    result = {}
    point: hou.Point
    for point in geo.points():
        value = point.stringAttribValue(attribute)
        if not value:
            continue
        if value in result:
            raise hou.NodeError(f"Duplicate point {attribute}: {value}")
        result[value] = point
    return result

def unique_points_start_with(
    geo: hou.Geometry,
    prefixes: tuple[str, ...],
    attribute: str = "id",
) -> dict[str, hou.Point]:
    result = {}
    for point, value in zip(
            geo.points(),
            geo.pointStringAttribValues(attribute),
    ):
        if not value:
            continue
        if value in result:
            raise hou.NodeError(f"Duplicate point {attribute}: {value}")
        if not value.startswith(prefixes):
            continue
        result[value] = point
    return result

def points_starting_with(
    geo: hou.Geometry,
    prefixes: tuple[str, ...] | str,
    attribute: str = "id",
) -> list[hou.Point]:
    return [
        point
        for point, value in zip(
            geo.points(),
            geo.pointStringAttribValues(attribute),
        )
        if value.startswith(prefixes)
    ]


def set_point_id(
    point: hou.Point,
    value: str,
    attribute: str = "id",
) -> None:
    point.setAttribValue(attribute, value)

def set_points_id(
    points: Sequence[hou.Point],
    values: Sequence[str],
    attribute: str = "id",
) -> None:
    if len(points) != len(values):
        raise hou.NodeError("Expected matching point and value array sizes")
    for p_point, p_id in zip(points, values):
        set_point_id(p_point, p_id, attribute)


def fill_face(
    geo: hou.Geometry,
    points: list[hou.Point],
) -> hou.Polygon:
    polygon = geo.createPolygon()
    for point in points:
        polygon.addVertex(point)
    return polygon

def fill_face_by_id(
    geo: hou.Geometry,
    values: list[str],
    attribute: str = "id",
) -> hou.Polygon:
    all_points = points_by_id(geo, attribute)
    face_points = []
    for v in values:
        p = all_points.get(v)
        if p is None:
            raise hou.NodeError(f"Expected point with id {v}")
        face_points.append(p)
    return fill_face(geo, face_points)


def get_id_range(
        geo: hou.Geometry,
        prefix: str,
        attribute: str = "id",
) -> tuple[int, int] | None:
    values = geo.pointStringAttribValues(attribute)
    numbers: list[int] = []
    for value in values:
        if prefix:
            if not value.startswith(prefix):
                continue
            remainder = value[len(prefix):]
            match = re.search(r"-?\d+", remainder)
        else:
            match = re.search(r"-?\d+", value)
        if match is not None:
            numbers.append(int(match.group()))

    if not numbers:
        return None
    return min(numbers), max(numbers)


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
        if len(primitives) != 2:
            raise hou.NodeError(f"Expected point {split_point.number()} to belong to exactly 2 primitives, got {len(primitives)}")
        first, second = primitives

        common_points = set(first.points()) & set(second.points())
        if len(common_points) != 2:
            raise hou.NodeError(f"Expected primitives {first.number()} and {second.number()} around point {split_point.number()} to share exactly 2 points, got {len(common_points)}")
        if split_point not in common_points:
            raise hou.NodeError(f"Shared edge between primitives {first.number()} and {second.number()} does not contain point {split_point.number()}")

        for primitive in primitives:
            primitive_points = primitive.points()
            if len(primitive_points) != 4:
                raise hou.NodeError(f"Expected primitive {primitive.number()} to be a quad, got {len(primitive_points)} points")

            opposite_points = [
                point
                for point in primitive_points
                if point not in common_points
            ]
            if len(opposite_points) != 2:
                raise hou.NodeError(f"Could not determine opposite edge of primitive {primitive.number()}")

            edge = geo.findEdge(opposite_points[0],  opposite_points[1])
            if edge is None:
                raise hou.NodeError(f"Expected opposite points of primitive {primitive.number()} to form an edge")
            split_group.add(edge)


def deduplicate_points(
        geo: hou.Geometry,
        prefix: tuple[str, ...] | str,
        attribute: str = "id"
) -> None:
    points = points_starting_with(geo, prefix, attribute) if prefix else geo.points()
    grouped: defaultdict[str, list[hou.Point]] = defaultdict(list)
    for p in points:
        v = p.stringAttribValue(attribute)
        grouped[v].append(p)
    for value, duplicates in grouped.items():
        if len(duplicates) <= 1:
            continue
        for i, point in enumerate(duplicates):
            set_point_id(point, f"{value}_{i+1}", attribute)