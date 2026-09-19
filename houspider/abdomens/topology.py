from houkit.attributer import add_prim_attrib, remove_attribs
from houkit.topology import fill_face
import hou

from ..helper import points_by_id, points_from_geo
from . import frames
from .attributes import (
    Region,
    abdomenend,
    abdomenhorizontalrim,
    abdomenorigin,
    abdomensidelower,
    abdomensideupper,
    abdomenverticalrim,
)


def prepare_cephalothorax_info(node: hou.SopNode) -> None:
    frames.prepare_cephalothorax_info(node)


def add_width_frame(node: hou.SopNode) -> None:
    frames.add_width_frame(node)


def add_height_frame(node: hou.SopNode) -> None:
    frames.add_height_frame(node)


def add_upper_middle_frame(node: hou.SopNode) -> None:
    frames.add_upper_middle_frame(node)


def add_lower_middle_frame(node: hou.SopNode) -> None:
    frames.add_lower_middle_frame(node)


def fill_right_side_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    add_prim_attrib(geo, "region", "")

    o, e = points_from_geo(geo, abdomenorigin(), abdomenend())
    v = lambda i: points[abdomenverticalrim(i)]
    vn = lambda i: points[abdomenverticalrim(-i)]
    h = lambda i: points[abdomenhorizontalrim(i)]
    su = lambda i: points[abdomensideupper(i)]
    sl = lambda i: points[abdomensidelower(i)]

    fill_face([o, v(1), su(1), h(1)])
    fill_face([o, h(1), sl(1), vn(1)])

    for j in range(1, 4):
        fill_face([v(j), v(j + 1), su(j + 1), su(j)])
        fill_face([su(j), su(j + 1), h(j + 1), h(j)])
        fill_face([h(j), h(j + 1), sl(j + 1), sl(j)])
        fill_face([sl(j), sl(j + 1), vn(j + 1), vn(j)])

    fill_face([e, h(4), su(4), v(4)])
    fill_face([e, vn(4), sl(4), h(4)])


def connect_frames_tmp(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    o = abdomenorigin()
    e = abdomenend()

    chains = [
        [o] + [abdomenhorizontalrim(i) for i in range(1, 5)] + [e],
        [o] + [abdomenverticalrim(i) for i in range(1, 5)] + [e],
        [o] + [abdomenverticalrim(-i) for i in range(1, 5)] + [e],
        [o] + [abdomensideupper(i) for i in range(1, 5)] + [e],
        [o] + [abdomensidelower(i) for i in range(1, 5)] + [e],
    ]

    for chain in chains:
        poly = geo.createPolygon(is_closed=False)
        for point_id in chain:
            point = points.get(point_id)
            assert point is not None, f"Expected point {point_id!r}"
            poly.addVertex(point)


def add_regions(node: hou.SopNode) -> None:
    geo = node.geometry()
    add_prim_attrib(geo, "region", "")
    for prim in geo.prims():
        prim.setAttribValue("region", Region.ABDOMEN)


def cleanup_temp_attributes(node: hou.SopNode) -> None:
    remove_attribs(
        node.geometry(),
        global_attributes=("tmp_cepha_size", "tmp_cepha_upper_lower_ratio", "tmp_pedicel_length", "tmp_pedicel_height"),
    )
