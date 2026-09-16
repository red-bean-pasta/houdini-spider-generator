import hou

from ..bases import attributes as base_attributes
from ..helper import fill_face_by_id_with_attr, points_from_geo, set_point_id, set_prim_attr_where_blank
from houkit.attributer import add_prim_attrib
from houkit.topology import fill_pentagon, offset_point
from .attributes import Region, headback, headchelicerae, headfront, headfrontfloat, headfrontmid, headtopmiddle, headsupport
from .helper import get_head_base_loop_width

def add_head_dent(node: hou.SopNode) -> None:
    geo = node.geometry()
    headfront0, headsupport0 = points_from_geo(
        geo,
        headfront(0),
        headsupport(0),
    )
    dist = headfront0.position().distanceTo(headsupport0.position())
    direction = (headsupport0.position() - headfront0.position()).normalized()
    offset = direction * (dist * 1/3)
    offset_point(headfront0, offset)
    offset_point(headsupport0, offset)


def curve_lip(node: hou.SopNode) -> None:
    geo = node.geometry()
    dist = get_head_base_loop_width(node)
    headchelicerae1, headsupport1 = points_from_geo(geo, headchelicerae(1), headsupport(1))
    offset = hou.Vector3(0.0, dist * 2, 0.0)
    for point in (headchelicerae1, headsupport1):
        offset_point(point, offset)


def fill_back_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    add_prim_attrib(geo, "region", "")

    fill_head_front_faces(geo)
    add_head_front_pentagon(geo)
    fill_head_top_and_back_faces(geo)
    set_prim_attr_where_blank(geo, "region", Region.HEADTOP)


def fill_head_front_faces(geo: hou.Geometry) -> None:
    fill_face_by_id_with_attr(
        geo,
        (
            headchelicerae(0),
            headsupport(0),
            headsupport(1),
            headchelicerae(1),
        ),
        "region",
        Region.HEADFRONTMAIN,
        True,
    )

    fill_face_by_id_with_attr(
        geo,
        (
            headchelicerae(1),
            headsupport(1),
            headsupport(2),
            headchelicerae(2),
        ),
        "region",
        Region.HEADFRONTMAIN,
        True,
    )

    fill_face_by_id_with_attr(
        geo,
        (
            headchelicerae(2),
            headsupport(2),
            base_attributes.basesternum(1, 2),
            base_attributes.basemaxilla(1),
        ),
        "region",
        Region.HEADFRONTCHEEK,
        True,
    )


def add_head_front_pentagon(geo: hou.Geometry) -> None:
    hf0, hf1, hs2, hs1, hs0 = points_from_geo(
        geo,
        headfront(0),
        headfront(1),
        headsupport(2),
        headsupport(1),
        headsupport(0),
    )
    midpoint, floatpoint = fill_pentagon(
        [hf0, hf1, hs2, hs1, hs0],
        (hf0, hs0),
    )
    set_point_id(midpoint, headfrontmid(0))
    set_point_id(floatpoint, headfrontfloat(1))


def fill_head_top_and_back_faces(geo: hou.Geometry) -> None:
    faces = {
        (
            headfront(0),
            headfront(1),
            headtopmiddle(1),
            headtopmiddle(0),
        ): (False, Region.HEADTOP),
        (
            headtopmiddle(0),
            headtopmiddle(1),
            headback(1),
            headback(0),
        ): (False, Region.HEADTOP),
        (
            headback(1),
            headback(0),
            headsupport(5),
            headsupport(4),
        ): (True, Region.HEADTOP),
        (
            headsupport(4),
            headsupport(5),
            base_attributes.baseend(0),
            base_attributes.basesternum(5, 1),
        ): (True, Region.HEADBACK),
    }

    for face, (reverse, region) in faces.items():
        fill_face_by_id_with_attr(geo, face, "region", region, reverse)


def fill_support_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    faces = {
        (
            headfront(1),
            headtopmiddle(1),
            headsupport(3),
            headsupport(2),
        ): True,
        (
            headtopmiddle(1),
            headback(1),
            headsupport(4),
            headsupport(3),
        ): True,
    }
    regions = (Region.HEADTOP, Region.HEADTOP)

    for i, (face, reverse) in enumerate(faces.items()):
        fill_face_by_id_with_attr(geo, face, "region", regions[i], reverse)

