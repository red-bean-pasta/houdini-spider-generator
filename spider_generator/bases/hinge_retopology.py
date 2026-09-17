"""Legacy"""
from hou import Point, Geometry, SopNode

from houkit.topology import split_point, get_line_intersection, is_neighbor, find_prim, fill_face

from ..helper import points_from_geo, set_point_id
from .attributes import basecoxamemebrane, basesternum, basemouthmembrane, basemaxillamembrane
from ..sternums.attributes import sternummiddle, sternumrim, sternumriminner


def retopo_corners(node: SopNode) -> None:
    geo = node.geometry()
    for i, reverse in ((1, True), (-1, False)):
        for j in range(2, 5):
            _retopo_sternum_corner(geo, i * j, reverse)
        _retopo_front_sternum_corner(geo, i, reverse)


def _retopo_sternum_corner(
    geo: Geometry,
    index: int,
    reverse: bool = False,
) -> tuple[Point, ...]:
    assert 1 < abs(index) < 5

    previous_index = index - (1 if index > 0 else -1)
    s, si, cm1, cm2, sm1, sm2, bm = points_from_geo(
        geo,
        sternumrim(index),
        sternumriminner(index),
        basecoxamemebrane(previous_index, 2),
        basecoxamemebrane(index, 1),
        sternummiddle(previous_index),
        sternummiddle(index),
        basesternum(index),
    )

    return _split_and_fill_corners(
        s,
        (
            (si, cm1, sm1),
            (cm2, si, sm2),
            (cm1, cm2, bm)
        ),
        reverse
    )


def _retopo_front_sternum_corner(
    geo: Geometry,
    index: int,
    reverse: bool = False,
) -> tuple[Point, ...]:
    assert index == -1 or index == 1

    s, mm, mx, cm, si, sm1, sm2, bm1, bm2 = points_from_geo(
        geo,
        sternumrim(index),
        basemouthmembrane("lower", index),
        basemaxillamembrane(index),
        basecoxamemebrane(index, 1),
        sternumriminner(index),
        sternumrim(0),
        sternummiddle(index),
        basesternum(index, 1),
        basesternum(index, 2),
    )

    return _split_and_fill_corners(
        s,
        (
            (si, mm, sm1),
            (cm, si, sm2),
            (mx, cm, bm2),
            (mm, mx, bm1)
        ),
        reverse
    )


def _split_and_fill_corners(
    center: Point,
    sides: tuple[tuple[Point, Point, Point], ...],
    reverse: bool = False
) -> tuple[Point, ...]:
    return tuple(
        _split_and_fill_corner(center, side, reverse)
        for side in sides
    )


def _split_and_fill_corner(
    center: Point,
    connected: tuple[Point, Point, Point],
    reverse: bool = False
) -> Point:
    """

    :param center:
    :param connected: The last point defines the split edge withe ``center``
    :return:
    """
    p1, p2, p_end = connected
    assert all(is_neighbor(center, p) for p in connected), f'{center.stringAttribValue("id")} is not neighbors with {tuple(p.stringAttribValue("id") for p in connected)}'

    pos = get_line_intersection(
        (center, p_end),
        (p1, p2),
    )

    prim1 = find_prim(center, p1, p_end)
    prim2 = find_prim(center, p2, p_end)
    p_split, split_prims = split_point((prim1, prim2), center)
    p_split.setPosition(pos)
    set_point_id(p_split, "")

    fill_face((center, p1, p_split, p2), reverse)
    return p_split
