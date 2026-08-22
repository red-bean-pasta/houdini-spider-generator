import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, Any, Sequence

import hou

import dev_helper


def affix_id(prefix: str, *affixes: int | str) -> str:
    return prefix + "_".join(map(str, affixes))


def sopify(
    parent: hou.SopNode,
    input_node: hou.SopNode | None,
    function: Callable[[hou.SopNode], None],
) -> hou.SopNode:
    assert "<locals>" not in function.__qualname__, "Python SOP functions must be module-level functions"

    module = function.__module__
    qualname = function.__qualname__

    node = parent.createNode("python", function.__name__.strip('_'))
    if input_node is not None:
        node.setInput(0, input_node)
    node.parm("python").set(
        f"from {_hip_module_name(dev_helper)} import {dev_helper.reload_hip_modules.__name__} as reload\n"
        f"reload()\n"
        f"import {module}\n"
        f"{module}.{qualname}(hou.pwd())"
    )
    return node

def _hip_module_name(module) -> str:
    hip_dir = Path(hou.hipFile.path()).resolve().parent
    module_path = Path(module.__file__).resolve()
    relative = module_path.relative_to(hip_dir)
    if relative.name == "__init__.py":
        relative = relative.parent
    else:
        relative = relative.with_suffix("")
    return ".".join(relative.parts)


def get_parent(node: hou.SopNode) -> hou.SopNode:
    parent = node.parent()
    assert isinstance(parent, hou.SopNode), "Expected Python SOP to be inside a SOP network"
    return parent

def get_float_parm(node: hou.SopNode, name: str) -> float:
    parm = node.parm(name)
    assert parm is not None, f"Expected parameter {name!r} on {node.path()}"
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
        type: hou.attribType,
        name: str,
        default: Any,
        skip_existing: bool = True,
) -> hou.Attrib:
    find_attrib = {
        hou.attribType.Point: geo.findPointAttrib,
        hou.attribType.Prim: geo.findPrimAttrib,
        hou.attribType.Vertex: geo.findVertexAttrib,
        hou.attribType.Global: geo.findGlobalAttrib,
    }[type]
    found = find_attrib(name)
    if skip_existing and found:
        return found
    return geo.addAttrib(type, name, default)


def points_by_id(geo: hou.Geometry | hou.Prim, attribute: str = "id") -> dict[str, hou.Point]:
    result = {}
    point: hou.Point
    for point in geo.points():
        value = point.stringAttribValue(attribute)
        if not value:
            continue
        assert value not in result, f"Duplicate point {attribute}: {value}"
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
        assert value not in result, f"Duplicate point {attribute}: {value}"
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
    assert len(points) == len(values), "Expected matching point and value array sizes"
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
        assert p is not None, f"Expected point with id {v}"
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

            edge = geo.findEdge(opposite_points[0],  opposite_points[1])
            assert edge is not None, f"Expected opposite points of primitive {primitive.number()} to form an edge"
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


def classify_after_inset(
        geo: hou.Geometry,
        prim_count_before: int,
        horizontal_pack_size: int = 1,
        vertical_pack_size: int = 1,
) -> tuple[
        list[tuple[hou.Prim, ...]],
        list[tuple[hou.Prim, ...]],
]:
    """

    :param geo:
    :param prim_count_before:
    :param horizontal_pack_size:
    :param vertical_pack_size:
    :return: [panes, sills]
    """
    assert horizontal_pack_size > 0 and vertical_pack_size > 0
    assert prim_count_before >= horizontal_pack_size * vertical_pack_size
    prims_after: tuple[hou.Prim, ...] = geo.prims(); assert len(prims_after) > prim_count_before
    prims_added = prims_after[prim_count_before:]

    # len(prims_added) = n * (4 * horizontal_pack_size * vertical_pack_size - (horizontal_pack_size - 1) * 2 - (vertical_pack_size - 1) * 2)
    grid_size = horizontal_pack_size * vertical_pack_size
    sill_size = 4 * grid_size - (horizontal_pack_size - 1) * 2 - (vertical_pack_size - 1) * 2
    assert len(prims_added) % sill_size == 0, f"primitives added {len(prims_added)} should be a multiple of sill size {sill_size}"
    group_count = len(prims_added) // sill_size

    assert prim_count_before >= group_count * grid_size
    pane_start = prim_count_before - group_count * grid_size # This is how Houdini internally implements

    panes: list[tuple[hou.Prim, ...]] = []
    sills: list[tuple[hou.Prim, ...]] = []
    for i in range(group_count):
        panes.append(prims_after[pane_start + i * grid_size : pane_start + (i + 1) * grid_size])
        sills.append(prims_added[i * sill_size : (i + 1) * sill_size])

    return panes, sills


def attribute_after_inset(
        node: hou.SopNode,
        attribute: str,
        pane_prefix: str,
        sill_prefix: str,
        horizontal_pack_size: int = 1,
        vertical_pack_size: int = 1,
) -> None:
    assert pane_prefix != sill_prefix
    geo = node.geometry()
    prim_count_before = len(node.input(0).input(0).geometry().prims())
    panes, sills = classify_after_inset(geo, prim_count_before, horizontal_pack_size, vertical_pack_size)
    for prefix, compos in {pane_prefix: panes, sill_prefix: sills}.items():
        i1 = 1; i2 = -1
        for compo in compos:
            centroid = get_prim_centroid(compo)
            i = i2 if centroid.x() < 0 else i1
            if len(compo) == 1:
                compo[0].setAttribValue(attribute, prefix + str(i))
                continue
            for j, part in enumerate(compo, start=1):
                part.setAttribValue(attribute, f"{prefix}{i}_{j}")
            if centroid.x() < 0:
                i2 -= 1
            else:
                i1 += 1

def get_prim_centroid(prims: Sequence[hou.Prim]) -> hou.Vector3:
    center = hou.Vector3()
    for prim in prims:
        center += prim.boundingBox().center()
    return center / len(prims)


def get_point_on_ellipse_2d(
        origin: hou.Vector3,
        upper: hou.Vector3,
        left: hou.Vector3,
        rad_from_y: float,
) -> hou.Vector3:
    assert upper.y() > origin.y(), f"upper ({upper}) must be above origin ({origin})"
    assert left.x() < origin.x(), f"left ({left}) must be to the left of origin ({origin})"

    v_upper = upper - origin
    v_left = left - origin
    assert math.isclose(v_upper.dot(v_left), 0.0, abs_tol=1e-5), f"upper-origin ({v_upper}) and left-origin ({v_left}) must be perpendicular"

    return origin + v_upper * math.cos(rad_from_y) + v_left * math.sin(rad_from_y)
