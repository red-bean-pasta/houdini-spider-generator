import hou

from houkit.attributer import add_prim_attrib
from houkit.topology import fill_face
from ..bases import attributes as base_attributes
from ..heads.attributes import headbasesupport, headchelicerae
from ..helper import add_id_point, fill_face_with_attr, positions_from_geo, replace_points
from .attributes import Region


def build_geometry(node: hou.SopNode) -> None:
    geo = node.geometry()

    base_ids = (
        base_attributes.basemaxilla(-1),
        base_attributes.basesternum(-1, 1),
        base_attributes.basesternum(0),
        base_attributes.basesternum(1, 1),
        base_attributes.basemaxilla(1),
    )
    base_positions = positions_from_geo(geo, *base_ids)

    upper_ids = tuple(headchelicerae(i) for i in range(-2, 3))
    upper_positions = positions_from_geo(geo, *upper_ids)

    headbase_positions = positions_from_geo(
        geo,
        headbasesupport(headchelicerae(0)),
        headbasesupport(headchelicerae(1)),
        headbasesupport(headchelicerae(2)),
    )

    all_point_data = [
        *zip(base_ids, base_positions),
        *zip(upper_ids, upper_positions),
    ]
    all_points = replace_points(geo, all_point_data)
    base_points = all_points[:len(base_ids)]
    upper_points = all_points[len(base_ids):]
    add_prim_attrib(geo, "region", "")

    fill_face_with_attr(
        geo,
        [
            *base_points,
            *reversed(upper_points),
        ],
        "region",
        Region.CHELICERA,
    )

    _retain_headbase_faces(geo, upper_points[2], upper_points[3], upper_points[4], headbase_positions)


def _retain_headbase_faces(
    geo: hou.Geometry,
    h0: hou.Point,
    h1: hou.Point,
    h2: hou.Point,
    headbase_positions: list[hou.Vector3],
) -> None:
    hb0 = add_id_point(geo, headbase_positions[0], headbasesupport(headchelicerae(0)))
    hb1 = add_id_point(geo, headbase_positions[1], headbasesupport(headchelicerae(1)))
    hb2 = add_id_point(geo, headbase_positions[2], headbasesupport(headchelicerae(2)))

    fill_face([h0, h1, hb1, hb0])
    fill_face([h1, h2, hb2, hb1])
