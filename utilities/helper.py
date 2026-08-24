import hou

from utility.meshing import classify_after_inset
from utility.common import get_prim_centroid


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