from enum import StrEnum, auto

import hou

from houkit.attributer import deduplicate_point_attribs, points_by_attrib, latest_points_by_attrib
from houkit.noder import add_output, add_reloadable_subnet
from houkit.topology import extrude, offset_point
from . import base_sops, sternum
from .base_sops import basemouthmembrane
from .helper import (
    affix_id,
    points_by_id,
    prims_by_attr,
    sopify_chain,
)


class ID(StrEnum):
    MOUTH = auto()

class Region(StrEnum):
    MOUTH = auto()

def mouth(*i: int | str) -> str:
    return affix_id(ID.MOUTH, *i)


def build(parent: hou.OpNode, source: hou.SopNode) -> hou.SopNode:
    mouth_subnet = add_reloadable_subnet(parent, "mouth")
    mouth_subnet.setInput(0, source)

    source = mouth_subnet.indirectInputs()[0]
    built = sopify_chain(mouth_subnet, source, (_add_mouth_geometry, _adjust_mouth_points))
    add_output(mouth_subnet, "OUT_MOUTH", built)
    mouth_subnet.layoutChildren()
    return mouth_subnet


def _add_mouth_geometry(node: hou.SopNode) -> None:
    geo = node.geometry()
    mouth_prims = _query_mouth_prims(geo)
    depth = _get_sternum_depth(points_by_id(geo))
    extruded_prims = extrude(mouth_prims, depth)
    for prim in extruded_prims:
        prim.setAttribValue("region", Region.MOUTH)
    _rename_extruded_mouth_points(geo)
    deduplicate_point_attribs(geo, "id", None, keep_first=True)


def _adjust_mouth_points(node: hou.SopNode) -> None:
    geo = node.geometry()
    upper_pts = list(latest_points_by_attrib(geo, "id", *(mouth("upper", i) for i in range(-1, 2))))
    lower_pts = list(latest_points_by_attrib(geo, "id", *(mouth("lower", i) for i in range(-1, 2))))

    vertical_dir = lower_pts[1].position() - upper_pts[1].position()
    assert vertical_dir.length() > 1e-6
    _move_points(1 / 3, vertical_dir, *upper_pts)
    _move_points(-1 / 6, vertical_dir, *lower_pts)

    for pts in (upper_pts, lower_pts):
        horizontal_dir = pts[0].position() - pts[2].position()
        assert horizontal_dir.length() > 1e-6
        _move_points(1 / 6, horizontal_dir, pts[2])
        _move_points(-1 / 6, horizontal_dir, pts[0])

def _move_points(
    ratio: float,
    direction: hou.Vector3,
    *points: hou.Point,
) -> None:
    offset = direction * ratio
    for p in points:
        offset_point(p, offset)


def _query_mouth_prims(geo: hou.Geometry) -> list[hou.Prim]:
    mouth_prims = prims_by_attr(geo, "region", base_sops.Region.LABIUMSOCKET)
    assert len(mouth_prims) == 2, f"Expected two inset mouth primitives, got {len(mouth_prims)}"
    return mouth_prims


def _rename_extruded_mouth_points(geo: hou.Geometry) -> None:
    points = points_by_attrib(geo, "id", skip_blank=True)
    for base_id, mouth_id in _mouth_point_id_pairs():
        candidates = points.get(base_id)
        assert candidates is not None, f"Expected mouth point {base_id!r}"
        point = max(candidates, key=lambda candidate: candidate.number())
        point.setAttribValue("id", mouth_id)


def _get_sternum_depth(points: dict[str, hou.Point]) -> float:
    spine_points = [
        point
        for point_id, point in points.items()
        if point_id.startswith(sternum.ID.STERNUMSPINE)
    ]
    assert spine_points, "Expected attributed sternum spine points"
    y_values = [point.position().y() for point in spine_points]
    depth = abs(max(y_values) - min(y_values))
    assert depth > 1e-6, "Expected a nonzero sternum depth"
    return depth


def _mouth_point_id_pairs() -> tuple[tuple[str, str], ...]:
    return (
        (basemouthmembrane("lower", 0), mouth("lower", 0)),
        (basemouthmembrane("lower", 1), mouth("lower", 1)),
        (basemouthmembrane("lower", -1), mouth("lower", -1)),
        (basemouthmembrane("upper", 0), mouth("upper", 0)),
        (basemouthmembrane("upper", 1), mouth("upper", 1)),
        (basemouthmembrane("upper", -1), mouth("upper", -1)),
    )
