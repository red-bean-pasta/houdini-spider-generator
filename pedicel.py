from enum import StrEnum, auto

import hou

import abdomen
import spider
from helper import (
    affix_id,
    point_from_geo,
    points_by_id,
    replace_points,
    set_prim_attr_where_blank,
)
from utilities.common import add_prim_attr
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import fill_pentagon_with_buffer


class ID(StrEnum):
    PEDICELMIDDLEUPPER = auto()
    PEDICELMIDDLELOWER = auto()


class Region(StrEnum):
    PEDICEL = auto()


def pedicelmiddleupper(*i: int | str) -> str:
    return affix_id(ID.PEDICELMIDDLEUPPER, *i)
def pedicelmiddlelower(*i: int | str) -> str:
    return affix_id(ID.PEDICELMIDDLELOWER, *i)


def build(spider_node: hou.OpNode, merged_cepha_and_abdomen: hou.SopNode) -> hou.SopNode:
    pedicel = add_reloadable_subnet(spider_node, "pedicel")
    pedicel.setInput(0, merged_cepha_and_abdomen)

    source = pedicel.indirectInputs()[0]
    needed_points = sopify(pedicel, source, _extract_needed_points)
    connected = sopify(pedicel, needed_points, _connect_pedicel)

    cleaned = pedicel.createNode("clean", "clean_unused_points")
    cleaned.setInput(0, connected)

    add_output(pedicel, "OUT_PEDICEL", cleaned)
    pedicel.layoutChildren()
    return pedicel


def _extract_needed_points(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    needed_ids = (
        spider.cephapedicelupper(),
        spider.cephapedicelright(),
        spider.cephapedicelleft(),
        spider.cephapedicellower(),
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

    replace_points(geo, point_data)


def _connect_pedicel(node: hou.SopNode) -> None:
    geo = node.geometry()

    (
        upper,
        right,
        left,
        lower,
        abdomenverticalrim1,
        abdomenverticalrim_neg1,
        abdomenhorizontalrim1,
        abdomenhorizontalrim_neg1,
        abdomensideupper1,
        abdomensideupper_neg1,
        abdomensidelower1,
        abdomensidelower_neg1,
    ) = point_from_geo(
        geo,
        spider.cephapedicelupper(),
        spider.cephapedicelright(),
        spider.cephapedicelleft(),
        spider.cephapedicellower(),
        abdomen.abdomenverticalrim(1),
        abdomen.abdomenverticalrim(-1),
        abdomen.abdomenhorizontalrim(1),
        abdomen.abdomenhorizontalrim(-1),
        abdomen.abdomensideupper(1),
        abdomen.abdomensideupper(-1),
        abdomen.abdomensidelower(1),
        abdomen.abdomensidelower(-1),
    )

    ratio = 1.0 - 0.035
    add_prim_attr(geo, "region", "")

    quadrant_configs = (
        # 1. Upper Right
        (
            [upper, abdomenverticalrim1, abdomensideupper1, abdomenhorizontalrim1, right],
            (upper, right),
            (upper, abdomenverticalrim1),
            False,
            pedicelmiddleupper(0),
            pedicelmiddleupper(1),
        ),
        # 2. Upper Left
        (
            [upper, left, abdomenhorizontalrim_neg1, abdomensideupper_neg1, abdomenverticalrim1],
            (upper, left),
            (upper, abdomenverticalrim1),
            False,
            pedicelmiddleupper(0),
            pedicelmiddleupper(-1),
        ),
        # 3. Lower Right
        (
            [lower, right, abdomenhorizontalrim1, abdomensidelower1, abdomenverticalrim_neg1],
            (lower, right),
            (lower, abdomenverticalrim_neg1),
            False,
            pedicelmiddlelower(0),
            pedicelmiddlelower(1),
        ),
        # 4. Lower Left
        (
            [lower, abdomenverticalrim_neg1, abdomensidelower_neg1, abdomenhorizontalrim_neg1, left],
            (lower, left),
            (lower, abdomenverticalrim_neg1),
            False,
            pedicelmiddlelower(0),
            pedicelmiddlelower(-1),
        ),
    )

    for points, split_edge, buffer_edge, reverse, mid_id, float_id in quadrant_configs:
        mid_pt, float_pt, _, _ = fill_pentagon_with_buffer(
            geo,
            points,
            split_edge,
            ratio,
            buffer_edge,
            reverse=reverse,
        )
        mid_pt.setAttribValue("id", mid_id)
        float_pt.setAttribValue("id", float_id)

    set_prim_attr_where_blank(geo, "region", Region.PEDICEL)
