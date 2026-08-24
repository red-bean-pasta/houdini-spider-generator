import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, Any, Sequence

import hou


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
    node.parm
    assert parm is not None, f"Expected parameter {name!r} on {node.path()}"
    return parm.evalAsFloat()

def get_vector2_parm(node: hou.SopNode, name: str) -> hou.Vector2:
    parm_tuple = node.parmTuple(name)
    assert parm_tuple is not None, f"Expected parameter {name!r} on {node.path()}"
    return hou.Vector2(parm_tuple.eval())


def add_edge_group(geo: hou.Geometry, name: str) -> hou.EdgeGroup:
    group = geo.findEdgeGroup(name)
    if group is None:
        group = geo.createEdgeGroup(name)
    return group


def add_new_id_attr(geo: hou.Geometry) -> hou.Attrib:
    return add_new_attr(geo, hou.attribType.Point, "id", "")

def add_point_attr(geo: hou.Geometry, name: str, default: Any) -> hou.Attrib:
    return add_new_attr(geo, hou.attribType.Point, name, default)

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


def points_by_attribute(
        geo: hou.Geometry | hou.Prim | Sequence[hou.Prim],
        attribute: str = "id"
) -> dict[str, hou.Point]:
    result = {}
    point: hou.Point
    if not isinstance(geo, Sequence):
        geo = (geo, )
    for g in geo:
        for point in g.points():
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


def rename_left_ids(geo: hou.Geometry) -> None:
    for point in geo.points():
        if point.position()[0] >= 0.0:
            continue
        point_id = point.stringAttribValue("id")
        if not point_id:
            continue
        first_digit = next(
            (index for index, character in enumerate(point_id) if character.isdigit()),
            None,
        )
        if first_digit is None:
            continue
        point.setAttribValue(
            "id",
            f"{point_id[:first_digit]}-{point_id[first_digit:]}",
        )


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
    all_points = points_by_attribute(geo, attribute)
    face_points = []
    for v in values:
        p = all_points.get(v)
        assert p is not None, f"Expected point with id {v}"
        face_points.append(p)
    return fill_face(geo, face_points)


def fill_pentagon(
    geo: hou.Geometry,
    points: Sequence[hou.Point],
    mid_edge: tuple[hou.Point, hou.Point],
) -> tuple[hou.Point, hou.Point]:
    assert len(set(points)) == 5, "Expected 5 distinct points for fill_pentagon"

    p_a, p_b = mid_edge; assert p_a in points and p_b in points and p_a != p_b, f"mid_edge {mid_edge} must be in points"
    idx_a = points.index(p_a)
    idx_b = points.index(p_b)
    diff = (idx_b - idx_a) % 5; assert diff in (1, 4), f"mid_edge points must be adjacent in points sequence, got diff {diff}"
    if diff == 1:
        ordered = [points[(idx_a + k) % 5] for k in range(5)]
    else:
        ordered = [points[(idx_a - k) % 5] for k in range(5)]

    p0, p1, p2, p3, p4 = ordered

    m_pos = (p0.position() + p1.position()) / 2.0
    midpoint = geo.createPoint()
    midpoint.setPosition(m_pos)

    v_edge = p1.position() - p0.position()
    edge_len = v_edge.length(); assert edge_len > 1e-6, "Expected nonzero mid_edge length"
    def dist_to_line(pt: hou.Point) -> float:
        v = pt.position() - p0.position()
        return v.cross(v_edge).length() / edge_len
    dist_p2 = dist_to_line(p2)
    dist_p4 = dist_to_line(p4)
    if dist_p2 <= dist_p4:
        m_base = (p0.position() + p4.position()) / 2.0
        f_pos = (p2.position() + m_base) / 2.0
    else:
        m_base = (p1.position() + p2.position()) / 2.0
        f_pos = (p4.position() + m_base) / 2.0

    floatpoint = geo.createPoint()
    floatpoint.setPosition(f_pos)

    fill_face(geo, [p1, midpoint, floatpoint, p2])
    fill_face(geo, [midpoint, p0, p4, floatpoint])
    fill_face(geo, [floatpoint, p4, p3, p2])

    return midpoint, floatpoint


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
        prefix: tuple[str, ...] | str | None,
        attribute: str = "id",
        affix: bool = False,
) -> None:
    """

    :param geo:
    :param prefix:
    :param attribute:
    :param affix: If true, affix like "_1" will be added, else later duplicates will simply be clear
    :return:
    """
    points = points_starting_with(geo, prefix, attribute) if prefix else geo.points()
    grouped: defaultdict[str, list[hou.Point]] = defaultdict(list)
    for p in points:
        v = p.stringAttribValue(attribute)
        grouped[v].append(p)
    for value, duplicates in grouped.items():
        if len(duplicates) <= 1:
            continue
        if affix:
            for i, point in enumerate(duplicates):
                set_point_id(point, f"{value}_{i+1}", attribute)
        else:
            for point in duplicates[1:]:
                point.setAttribValue(attribute, "")


def classify_after_inset(
        geo: hou.Geometry,
        prim_count_before: int,
        horizontal_pack_size: int = 1,
        vertical_pack_size: int = 1,
) -> tuple[
        list[tuple[hou.Prim, ...]],
        list[tuple[hou.Prim, ...]],
]:
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
) -> tuple[
        list[tuple[hou.Prim, ...]],
        list[tuple[hou.Prim, ...]],
]:
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
    return panes, sills


def get_prim_centroid(prims: hou.Prim | Sequence[hou.Prim]) -> hou.Vector3:
    center = hou.Vector3()
    if isinstance(prims, hou.Prim):
        prims = (prims,)
    for prim in prims:
        center += prim.boundingBox().center()
    return center / len(prims)


def get_point_on_ellipse_2d(
        origin: hou.Vector3,
        vertical_end: hou.Vector3,
        side_end: hou.Vector3,
        rad_from_y: float = math.pi / 4,
) -> hou.Vector3:
    assert not math.isclose(vertical_end.y(), origin.y(), abs_tol=1e-5), f"upper ({vertical_end}) and origin ({origin}) must have different y"
    assert not math.isclose(side_end.x(), origin.x(), abs_tol=1e-5), f"left ({side_end}) and origin ({origin}) must have different x"

    v_upper = vertical_end - origin
    v_left = side_end - origin
    assert math.isclose(v_upper.dot(v_left), 0.0, abs_tol=1e-5), f"upper-origin ({v_upper}) and left-origin ({v_left}) must be perpendicular"

    return origin + v_upper * math.cos(rad_from_y) + v_left * math.sin(rad_from_y)


def interpolate_conic(
        p0: hou.Vector3 | hou.Point,
        p1: hou.Vector3 | hou.Point,
        p2: hou.Vector3 | hou.Point,
        slope0: hou.Vector3,
        slope1: hou.Vector3,
) -> Callable[[float], tuple[hou.Vector3, ...]]:
    """
    Construct the planar conic passing through p0, p1, p2, with the specified tangent directions at p0 and p1.
    :param p0:
    :param p1:
    :param p2:
    :param slope0:
    :param slope1:
    :return: A function that accepts a signed distance along the p0 to p1 axis,
             and returns the 0, 1, or 2 points on the conic.
    """
    vector0 = p0.position() if isinstance(p0, hou.Point) else hou.Vector3(p0)
    vector1 = p1.position() if isinstance(p1, hou.Point) else hou.Vector3(p1)
    vector2 = p2.position() if isinstance(p2, hou.Point) else hou.Vector3(p2)

    delta01 = vector1 - vector0
    delta02 = vector2 - vector0
    assert delta01.length() != 0.0, "p0 and p1 must be distinct"

    along_axis = delta01.normalized()
    normal = along_axis.cross(delta02); assert normal.length() != 0.0, "p0, p1, and p2 must not be collinear"
    normal = normal.normalized()
    across_axis = normal.cross(along_axis).normalized()

    along1 = delta01.length()
    along2 = delta02.dot(along_axis)
    across2 = delta02.dot(across_axis)

    def project_slope(slope: hou.Vector3) -> tuple[float, float]:
        tangent = slope - slope.dot(normal) * normal
        assert tangent.length() != 0.0, "Slope must have a non-zero component in the conic plane"
        tangent = tangent.normalized()
        return tangent.dot(along_axis), tangent.dot(across_axis)
    along_slope0, across_slope0 = project_slope(slope0)
    along_slope1, across_slope1 = project_slope(slope1)

    import numpy as np
    # A*x² + B*x*y + C*y² + D*x + E*y = 0
    matrix = np.array([
        [along1**2, 0.0, 0.0, along1, 0.0],
        [along2**2, along2 * across2, across2**2, along2, across2],
        [0.0, 0.0, 0.0, along_slope0, across_slope0],
        [2.0 * along1 * along_slope1, along1 * across_slope1, 0.0, along_slope1, across_slope1],
    ], dtype=float)
    _, singular_values, vh = np.linalg.svd(matrix)
    A, B, C, D, E = map(float, vh[-1])

    tolerance = np.finfo(float).eps * max(matrix.shape) * singular_values[0]
    assert np.sum(singular_values > tolerance) == 4, "The supplied points and slopes do not determine a unique conic"

    coefficient_scale = max(abs(A), abs(B), abs(C), abs(D), abs(E))
    assert coefficient_scale != 0.0, "Failed to construct a valid conic"
    A /= coefficient_scale
    B /= coefficient_scale
    C /= coefficient_scale
    D /= coefficient_scale
    E /= coefficient_scale

    def to_3d(along: float, across: float) -> hou.Vector3:
        return vector0 + along * along_axis + across * across_axis

    def evaluate(along: float) -> tuple[hou.Vector3, ...]:
        quadratic = C
        linear = B * along + E
        constant = A * along**2 + D * along
        eps = 1e-12

        if abs(quadratic) <= eps:
            if abs(linear) <= eps:
                return ()
            across = -constant / linear
            return (to_3d(along, across),)

        discriminant = linear**2 - 4.0 * quadratic * constant
        if discriminant < -eps:
            return ()

        if abs(discriminant) <= eps:
            across = -linear / (2.0 * quadratic)
            return (to_3d(along, across),)

        sqrt_discriminant = math.sqrt(discriminant)
        across0 = (-linear + sqrt_discriminant) / (2.0 * quadratic)
        across1 = (-linear - sqrt_discriminant) / (2.0 * quadratic)
        return to_3d(along, across0), to_3d(along, across1)

    return evaluate


def remove_attributes(
        geo: hou.Geometry,
        point_attribs: str | tuple[str, ...] | None = None,
        prim_attribs: str | tuple[str, ...] | None = None,
        global_attribs: str | tuple[str, ...] | None = None,
) -> None:
    for attribs, finder in zip(
        (point_attribs, prim_attribs, global_attribs),
        (geo.findPointAttrib, geo.findPrimAttrib, geo.findGlobalAttrib),
    ):
        if attribs is None:
            continue
        if isinstance(attribs, str):
            attribs = (attribs,)
        for name in attribs:
            attrib = finder(name)
            if attrib is not None:
                attrib.destroy()


def remove_groups(
        geo: hou.Geometry,
        point_groups: str | tuple[str, ...] | None = None,
        edge_groups: str | tuple[str, ...] | None = None,
        prim_groups: str | tuple[str, ...] | None = None,
) -> None:
    for groups, finder in zip(
        (point_groups, edge_groups, prim_groups),
        (geo.findPointGroup, geo.findEdgeGroup, geo.findPrimGroup),
    ):
        if groups is None:
            continue
        if isinstance(groups, str):
            groups = (groups,)
        for name in groups:
            group = finder(name)
            if group is not None:
                group.destroy()
