from enum import StrEnum, auto

import hou

import abdomen
import main
from utilities.common import (
    add_float_param,
    add_prim_attr,
)
from utilities.helper import (
    add_id_attr,
    affix_id,
    points_by_id,
)
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import fill_pentagon_with_buffer


class ID(StrEnum):
    PEDICELMIDDLEUPPER = auto()
    PEDICELMIDDLELOWER = auto()

def pedicelmiddleupper(*i: int | str) -> str:
    return affix_id(ID.PEDICELMIDDLEUPPER, *i)

def pedicelmiddlelower(*i: int | str) -> str:
    return affix_id(ID.PEDICELMIDDLELOWER, *i)


def build(spider: hou.OpNode, merged_cepha_and_abdomen: hou.SopNode) -> hou.SopNode:
    pedicel = add_reloadable_subnet(spider, "pedicel")
    pedicel.setInput(0, merged_cepha_and_abdomen)
    _add_parameters(pedicel)

    source = pedicel.indirectInputs()[0]
    needed_points = sopify(pedicel, source, _extract_needed_points)
    connected = sopify(pedicel, needed_points, _connect_pedicel)

    cleaned = pedicel.createNode("clean", "clean_unused_points")
    cleaned.setInput(0, connected)

    add_output(pedicel, "OUT_PEDICEL", cleaned)
    pedicel.layoutChildren()
    return pedicel


def _add_parameters(pedicel: hou.SopNode) -> None:
    add_float_param(
        pedicel,
        "size_ratio",
        2,
        (1.0, 1.0),
        (0.0, None),
        help="Pedicel width and height ratio relative to the base pedicel opening.",
    )


def _extract_needed_points(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    needed_ids = (
        main.cephapedicelupper(),
        main.cephapedicelright(),
        main.cephapedicelleft(),
        main.cephapedicellower(),
        abdomen.abdomenverticalrim(1),
        abdomen.abdomenverticalrim(-1),
        abdomen.abdomenhorizontalrim(1),
        abdomen.abdomenhorizontalrim(-1),
        abdomen.abdomensideupper(1),
        abdomen.abdomensideupper(-1),
        abdomen.abdomensidelower(1),
        abdomen.abdomensidelower(-1),
    )

    point_data = []
    for point_id in needed_ids:
        point = points.get(point_id)
        assert point is not None, f"Expected point {point_id!r} in merged geometry"
        point_data.append((point_id, point.position()))

    geo.clear()
    add_id_attr(geo)
    for point_id, position in point_data:
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)


def _connect_pedicel(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    upper = points[main.cephapedicelupper()]
    right = points[main.cephapedicelright()]
    left = points[main.cephapedicelleft()]
    lower = points[main.cephapedicellower()]

    abdomenverticalrim1 = points[abdomen.abdomenverticalrim(1)]
    abdomenverticalrim_neg1 = points[abdomen.abdomenverticalrim(-1)]
    abdomenhorizontalrim1 = points[abdomen.abdomenhorizontalrim(1)]
    abdomenhorizontalrim_neg1 = points[abdomen.abdomenhorizontalrim(-1)]
    abdomensideupper1 = points[abdomen.abdomensideupper(1)]
    abdomensideupper_neg1 = points[abdomen.abdomensideupper(-1)]
    abdomensidelower1 = points[abdomen.abdomensidelower(1)]
    abdomensidelower_neg1 = points[abdomen.abdomensidelower(-1)]

    ratio = 1 - 0.035
    add_prim_attr(geo, "region", "")

    # 1. Upper Right
    mid_ur, flt_ur, _, _ = fill_pentagon_with_buffer(
        geo,
        [upper, abdomenverticalrim1, abdomensideupper1, abdomenhorizontalrim1, right],
        (upper, right),
        ratio,
        (upper, abdomenverticalrim1),
    )
    mid_ur.setAttribValue("id", pedicelmiddleupper(0))
    flt_ur.setAttribValue("id", pedicelmiddleupper(1))

    # 2. Upper Left
    mid_ul, flt_ul, _, _ = fill_pentagon_with_buffer(
        geo,
        [upper, left, abdomenhorizontalrim_neg1, abdomensideupper_neg1, abdomenverticalrim1],
        (upper, left),
        ratio,
        (upper, abdomenverticalrim1),
        True,
    )
    mid_ul.setAttribValue("id", pedicelmiddleupper(0))
    flt_ul.setAttribValue("id", pedicelmiddleupper(-1))

    # 3. Lower Right
    mid_lr, flt_lr, _, _ = fill_pentagon_with_buffer(
        geo,
        [lower, right, abdomenhorizontalrim1, abdomensidelower1, abdomenverticalrim_neg1],
        (lower, right),
        ratio,
        (lower, abdomenverticalrim_neg1),
        True,
    )
    mid_lr.setAttribValue("id", pedicelmiddlelower(0))
    flt_lr.setAttribValue("id", pedicelmiddlelower(1))

    # 4. Lower Left
    mid_ll, flt_ll, _, _ = fill_pentagon_with_buffer(
        geo,
        [lower, abdomenverticalrim_neg1, abdomensidelower_neg1, abdomenhorizontalrim_neg1, left],
        (lower, left),
        ratio,
        (lower, abdomenverticalrim_neg1),
    )
    mid_ll.setAttribValue("id", pedicelmiddlelower(0))
    flt_ll.setAttribValue("id", pedicelmiddlelower(-1))

    for prim in geo.prims():
        if not prim.stringAttribValue("region"):
            prim.setAttribValue("region", "pedicel")
