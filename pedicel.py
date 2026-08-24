from enum import StrEnum, auto

import hou

import abdomen
import base_sops
import sternum_sops
from hom_helper import (
    add_point_attr,
    add_new_prim_attr,
    affix_id,
    fill_pentagon,
    points_by_attribute,
    sopify,
)
from sop_helper import add_output


class ID(StrEnum):
    PEDICELMIDDLEUPPER = auto()
    PEDICELMIDDLELOWER = auto()

def pedicelmiddleupper(*i: int | str) -> str:
    return affix_id(ID.PEDICELMIDDLEUPPER, *i)

def pedicelmiddlelower(*i: int | str) -> str:
    return affix_id(ID.PEDICELMIDDLELOWER, *i)


def build(spider: hou.OpNode, merged_cepha_and_abdomen: hou.SopNode) -> hou.SopNode:
    pedicel = spider.createNode("subnet", "pedicel")
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
    points = points_by_attribute(geo)

    needed_ids = (
        base_sops.baseend(0),
        base_sops.basesternum(5, 1),
        base_sops.basesternum(5, 2),
        sternum_sops.sternumrim(5),
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
    add_point_attr(geo)
    for point_id, position in point_data:
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)


def _connect_pedicel(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_attribute(geo)

    baseend0 = points[base_sops.baseend(0)]
    basesternum5_1 = points[base_sops.basesternum(5, 1)]
    basesternum5_2 = points[base_sops.basesternum(5, 2)]
    sternumrim5 = points[sternum_sops.sternumrim(5)]

    abdomenverticalrim1 = points[abdomen.abdomenverticalrim(1)]
    abdomenverticalrim_neg1 = points[abdomen.abdomenverticalrim(-1)]
    abdomenhorizontalrim1 = points[abdomen.abdomenhorizontalrim(1)]
    abdomenhorizontalrim_neg1 = points[abdomen.abdomenhorizontalrim(-1)]
    abdomensideupper1 = points[abdomen.abdomensideupper(1)]
    abdomensideupper_neg1 = points[abdomen.abdomensideupper(-1)]
    abdomensidelower1 = points[abdomen.abdomensidelower(1)]
    abdomensidelower_neg1 = points[abdomen.abdomensidelower(-1)]

    add_new_prim_attr(geo, "region", "")

    # 1. Upper Right
    mid_ur, flt_ur = fill_pentagon(
        geo,
        [baseend0, abdomenverticalrim1, abdomensideupper1, abdomenhorizontalrim1, basesternum5_1],
        (baseend0, abdomenverticalrim1),
    )
    mid_ur.setAttribValue("id", pedicelmiddleupper(0))
    flt_ur.setAttribValue("id", pedicelmiddleupper(1))

    # 2. Upper Left
    mid_ul, flt_ul = fill_pentagon(
        geo,
        [baseend0, basesternum5_2, abdomenhorizontalrim_neg1, abdomensideupper_neg1, abdomenverticalrim1],
        (baseend0, abdomenverticalrim1),
    )
    mid_ul.setAttribValue("id", pedicelmiddleupper(0))
    flt_ul.setAttribValue("id", pedicelmiddleupper(-1))

    # 3. Lower Right
    mid_lr, flt_lr = fill_pentagon(
        geo,
        [sternumrim5, basesternum5_1, abdomenhorizontalrim1, abdomensidelower1, abdomenverticalrim_neg1],
        (sternumrim5, abdomenverticalrim_neg1),
    )
    mid_lr.setAttribValue("id", pedicelmiddlelower(0))
    flt_lr.setAttribValue("id", pedicelmiddlelower(1))

    # 4. Lower Left
    mid_ll, flt_ll = fill_pentagon(
        geo,
        [sternumrim5, abdomenverticalrim_neg1, abdomensidelower_neg1, abdomenhorizontalrim_neg1, basesternum5_2],
        (sternumrim5, abdomenverticalrim_neg1),
    )
    mid_ll.setAttribValue("id", pedicelmiddlelower(0))
    flt_ll.setAttribValue("id", pedicelmiddlelower(-1))

    for prim in geo.prims():
        if not prim.stringAttribValue("region"):
            prim.setAttribValue("region", "pedicel")