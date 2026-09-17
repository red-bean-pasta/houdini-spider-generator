from collections.abc import Collection

import hou

from houkit.attributer import points_by_attrib
from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm
from .attributes import (
    Region,
    basecoxamemebrane,
    basecoxamembranemiddle,
    basemaxilla,
    basemaxillamembrane,
    basemouthmembrane,
    basesternum,
    basesternummiddle,
)
from ..helper import (
    deduplicate_id_attr,
    inset_inner_prims,
    points_by_id,
    prims_by_attr,
)
from ..sternums import attributes as sternum_attributes


def inset_membrane(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    ratio = get_float_parm(parent, "membrane_ratio")
    points = points_by_id(geo)

    _inset_coxa_membranes(geo, points, ratio)
    _inset_membrane_region(
        geo,
        Region.LABIUM,
        Region.LABIUMSOCKET,
        Region.LABIUMMEMBRANE,
        (points[sternum_attributes.sternumrim(0)], points[basesternum(0)]),
        ratio,
        follow_existing_edge=False,
    )
    _classify_mouth_membrane_points(geo)
    _inset_membrane_region(
        geo,
        Region.MAXILLA,
        Region.MAXILLASOCKET,
        Region.MAXILLAMEMBRANE,
        (points[sternum_attributes.sternumrim(1)], points[basesternum(1, 1)]),
        ratio,
        follow_existing_edge=False,
    )

    _classify_maxilla_membrane_points(geo)
    deduplicate_id_attr(geo, None, add_affix=False)


def _inset_coxa_membranes(geo: hou.Geometry, points: dict[str, hou.Point], ratio: float) -> None:
    side_indices = (*range(1, 5), *range(-4, 0))
    for index in side_indices:
        sm = points[sternum_attributes.sternummiddle(index)]
        bsm = points[basesternummiddle(index)]
        prims = prims_by_attr(sm.prims(), "region", Region.COXA)

        dist = ratio * sm.position().distanceTo(bsm.position())
        assert dist > 0.0, f"Expected positive coxa membrane inset distance, got {dist}"

        inner_prims = inset_inner_prims(geo, prims, dist, use_ratio=False, follow_existing_edge=True)
        _attribute_coxa_membrane_points(inner_prims, index)

        for prim in inner_prims:
            prim.setAttribValue("region", Region.COXASOCKET)

    for prim in prims_by_attr(geo, "region", Region.COXA):
        prim.setAttribValue("region", Region.COXAMEMBRANE)


def _inset_membrane_region(
    geo: hou.Geometry,
    region: Region,
    socket_region: Region,
    membrane_region: Region,
    baseline: tuple[hou.Point, hou.Point],
    ratio: float,
    follow_existing_edge: bool = True,
) -> None:
    inner_pt, outer_pt = baseline
    dist = ratio * inner_pt.position().distanceTo(outer_pt.position())
    prims = prims_by_attr(geo, "region", region)
    inner_prims = inset_inner_prims(
        geo,
        prims,
        dist,
        use_ratio=False,
        follow_existing_edge=follow_existing_edge,
    )
    for prim in inner_prims:
        prim.setAttribValue("region", socket_region)
    for prim in prims_by_attr(geo, "region", region):
        prim.setAttribValue("region", membrane_region)


def _attribute_coxa_membrane_points(
    prims: Collection[hou.Prim],
    index: int,
) -> None:
    mapping = _coxa_membrane_id_mapping(index)
    points = {
        p
        for prim in prims
        for p in prim.points()
        if p.stringAttribValue("id") in mapping
    }
    assert len(points) == 6, f"Expected 6 coxa membrane points, got {len(points)}"

    for point in points:
        source_id = point.stringAttribValue("id")
        point.setAttribValue("id", mapping[source_id])


def _coxa_membrane_id_mapping(index: int) -> dict[str, str]:
    sign = 1 if index > 0 else -1
    next_idx = 5 if abs(index) == 4 else index + sign

    ant_basesternum = basesternum(index, 2) if abs(index) == 1 else basesternum(index)
    post_basesternum = basesternum(5, 1 if index > 0 else 2) if abs(index) == 4 else basesternum(next_idx)

    return {
        sternum_attributes.sternumrim(index): basecoxamemebrane(index, 1),
        sternum_attributes.sternummiddle(index): basecoxamembranemiddle(index, 1),
        sternum_attributes.sternumrim(next_idx): basecoxamemebrane(index, 2),
        post_basesternum: basecoxamemebrane(index, 3),
        basesternummiddle(index): basecoxamembranemiddle(index, 2),
        ant_basesternum: basecoxamemebrane(index, 4),
    }


def _classify_maxilla_membrane_points(geo: hou.Geometry) -> None:
    points_by_id_dict = points_by_attrib(geo, "id", skip_blank=True)
    for side in (1, -1):
        for index, name in enumerate(
            (sternum_attributes.sternumrim(side), basesternum(side, 1), basemaxilla(side), basesternum(side, 2)),
            start=1
        ):
            _id_last_point(points_by_id_dict[name], basemaxillamembrane(side * index))


def _classify_mouth_membrane_points(geo: hou.Geometry) -> None:
    pts = points_by_attrib(geo, "id", skip_blank=True)
    for side in (1, -1):
        _id_last_point(pts[sternum_attributes.sternumrim(side)], basemouthmembrane("lower", side))
        _id_last_point(pts[basesternum(side, 1)], basemouthmembrane("upper", side))

        _id_last_point(pts[sternum_attributes.sternumrim(0)], basemouthmembrane("lower", 0))
    _id_last_point(pts[basesternum(0)], basemouthmembrane("upper", 0))


def _id_last_point(points: Collection[hou.Point], value: str) -> None:
    p = max(points, key=lambda point: point.number())
    p.setAttribValue("id", value)
