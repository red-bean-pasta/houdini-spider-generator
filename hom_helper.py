from typing import Callable

import hou


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


def add_id_attr(geo: hou.Geometry, skip_if_existing: bool = True) -> None:
    if skip_if_existing and geo.findPointAttrib("id"):
        return
    geo.addAttrib(hou.attribType.Point, "id", "")


def affix_id(prefix: str, affix: int) -> str:
    return prefix + str(affix)


def points_by_id(geo: hou.Geometry, attribute: str = "id") -> dict[str, hou.Point]:
    result: dict[str, hou.Point] = {}
    for point in geo.points():
        point_id = point.stringAttribValue(attribute)
        if point_id:
            result[point_id] = point
    return result


def set_id(
    points: list[hou.Point],
    values: list[str],
    attribute: str = "id",
) -> None:
    if len(points) != len(values):
        raise hou.NodeError("Expected matching point and value array sizes")
    for point, p_id in zip(points, values):
        point.setAttribValue(attribute, p_id)


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


def find_quad_polyextrude_splits(
    geo: hou.Geometry,
    split_points: list[hou.Point],
    split_group_name: str,
) -> None:
    split_group = geo.findEdgeGroup(split_group_name)
    if split_group is None:
        split_group = geo.createEdgeGroup(split_group_name)
    for split_point in split_points:
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