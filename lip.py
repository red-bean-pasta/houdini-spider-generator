from enum import StrEnum, auto

import hou

from base_sops import basemaxilla, basesternum
from chelicerae import cheliceraemembraneupper
from head import headbasesupport, headfront, headsupport
from helper import affix_id, point_from_geo, set_point_id
from utilities.common import (
    add_float_param,
    fill_face,
    find_prim,
    get_params,
    get_parent,
)
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import loop_cut


LOOP_RATIOS = (1/6, 2/6, 3/6, 5/6)
TRANSITION_UVS = (
    (0.77, 0.045),
    (0.59, 0.07),
    (0.40, 0.07),
    (0.24, 0.045),
)


class ID(StrEnum):
    LIPSUPPORT = auto()
    LIPBASESUPPORT = auto()
    I = auto()

def lip_support(*i: int | str) -> str:
    return affix_id(ID.LIPSUPPORT, *i)
def lip_base_support(*i: int | str) -> str:
    return affix_id(ID.LIPBASESUPPORT, *i)
def lip_intermediate(*i: int | str) -> str:
    return affix_id(ID.I, *i)


def build(cephalothorax: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    lip = add_reloadable_subnet(cephalothorax, "lip")
    lip.setInput(0, source)
    _add_parameters(lip)

    source_node = lip.indirectInputs()[0]
    loops = sopify(lip, source_node, _add_loops)
    faces_removed = sopify(lip, loops, _remove_faces)
    retopo = sopify(lip, faces_removed, _retopo_faces)
    extruded = sopify(lip, retopo, _extrude_lip)
    width_adjusted = sopify(lip, extruded, _adjust_lip_width)

    add_output(lip, "OUT_LIP", width_adjusted)
    lip.layoutChildren()
    return lip


def _add_parameters(lip: hou.SopNode) -> None:
    add_float_param(
        lip,
        "extrusion_ratio",
        2,
        (5.0, 1.0),
        (-10.0, 10.0),
        naming_scheme=hou.parmNamingScheme.XYZW,
        help="Lip refers to the touching line between chelicerae and head, and the ratio is relative to the base support loop (membrane) height",
    )
    add_float_param(
        lip,
        "lip_width_ratio",
        1,
        1.0,
        (0.0, None),
        help="Evaluated against the height of head support loop",
    )


def _add_loops(node: hou.SopNode) -> None:
    geo = node.geometry()

    (
        c0,
        h0,
        c1,
        h1,
        c_neg1,
        h_neg1,
        b1,
        hb1,
        b_neg1,
        hb_neg1,
    ) = point_from_geo(
        geo,
        cheliceraemembraneupper(0),
        headbasesupport(cheliceraemembraneupper(0)),
        cheliceraemembraneupper(1),
        headbasesupport(cheliceraemembraneupper(1)),
        cheliceraemembraneupper(-1),
        headbasesupport(cheliceraemembraneupper(-1)),
        basemaxilla(1),
        headbasesupport(basemaxilla(1)),
        basemaxilla(-1),
        headbasesupport(basemaxilla(-1)),
    )

    prim_right = find_prim(c0, h0, c1, h1)
    prim_left = find_prim(c0, h0, c_neg1, h_neg1)
    cheek_right = find_prim(c1, h1, b1, hb1)
    cheek_left = find_prim(c_neg1, h_neg1, b_neg1, hb_neg1)

    ratios = LOOP_RATIOS
    delta_ratios = [
        ratios[i]
        if i < 1 else
        (ratios[i] - ratios[i - 1]) / (1 - (ratios[i - 1]))
        for i in range(len(ratios))
    ]

    current_start = h0
    scope = [prim_right, prim_left, cheek_right, cheek_left]
    end_points = {c0, c1, c_neg1, b1, b_neg1}
    reference_edges = (
        (lip_support, 0, h0, c0),
        (lip_support, 1, h1, c1),
        (lip_support, -1, h_neg1, c_neg1),
        (lip_base_support, 1, hb1, b1),
        (lip_base_support, -1, hb_neg1, b_neg1),
    )
    for loop_idx, (ratio, delta) in enumerate(zip(LOOP_RATIOS, delta_ratios), start=1):
        prim_to_cut = find_prim(current_start, c0)
        added_pts, _ = loop_cut(
            prim_to_cut,
            current_start,
            c0,
            delta,
            use_ratio=True,
            scope=scope,
        )
        assert len(added_pts) == len(reference_edges), "Expected cuts across the center and both cheek faces"

        unmatched = set(added_pts)
        for id_builder, side, start, end in reference_edges:
            expected = start.position() * (1.0 - ratio) + end.position() * ratio
            point = min(unmatched, key=lambda pt: pt.position().distanceTo(expected))
            assert point.position().distanceTo(expected) < 1e-4, "Expected loop point on reference edge"
            set_point_id(point, id_builder(loop_idx, side))
            unmatched.remove(point)

        (current_start,) = point_from_geo(geo, lip_support(loop_idx, 0))
        cut_points = set(added_pts)
        scope = [
            prim
            for prim in geo.prims()
            if len(cut_points.intersection(prim.points())) == 2
            and any(point in end_points for point in prim.points())
        ]


def _remove_faces(node: hou.SopNode) -> None:
    geo = node.geometry()

    prims_to_delete = []
    for side in (1, -1):
        b, hb, s, hs = point_from_geo(
            geo,
            basemaxilla(side),
            headbasesupport(basemaxilla(side)),
            basesternum(side, 2),
            headbasesupport(basesternum(side, 2)),
        )
        prim = find_prim(b, hb, s, hs)
        prims_to_delete.append(prim)

    geo.deletePrims(prims_to_delete, keep_points=True)


def _extrude_lip(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    ratio_x, ratio_y = get_params(parent).extrusion_ratio

    h0, c0 = point_from_geo(
        geo,
        headbasesupport(cheliceraemembraneupper(0)),
        cheliceraemembraneupper(0),
    )
    baseline = h0.position().y() - c0.position().y()

    z_offset = -baseline * ratio_x
    y_offset = -baseline * ratio_y
    offset = hou.Vector3(0.0, y_offset, z_offset)

    for side in (0, 1, -1):
        pt1, pt2, pt3, pt4, c, hb, hf, hs = point_from_geo(
            geo,
            lip_support(1, side),
            lip_support(2, side),
            lip_support(3, side),
            lip_support(4, side),
            cheliceraemembraneupper(side),
            headbasesupport(cheliceraemembraneupper(side)),
            headfront(side),
            headsupport(side),
        )

        pos2_orig = pt2.position()
        dist_2_3 = (pt3.position() - pos2_orig).length()
        dist_4_c = (c.position() - pt4.position()).length()

        for pt in (pt1, pt2, hb, hf, hs):
            pt.setPosition(pt.position() + offset)

        pos2 = pt2.position()
        pos_c = c.position()
        dir_2_to_c = (pos_c - pos2).normalized()
        pt3.setPosition(pos2 + dir_2_to_c * dist_2_3)
        pt4.setPosition(pos_c - dir_2_to_c * dist_4_c)


def _adjust_lip_width(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    lip_width_ratio = get_params(parent).lip_width_ratio

    hb1, b1 = point_from_geo(
        geo,
        headbasesupport(basemaxilla(1)),
        basemaxilla(1),
    )
    baseline = hb1.position().y() - b1.position().y()

    loop1_0, loop2_0 = point_from_geo(geo, lip_support(1, 0), lip_support(2, 0))
    existing_width = loop1_0.position().y() - loop2_0.position().y()

    delta_y = lip_width_ratio * baseline - existing_width

    for side in (0, 1, -1):
        pt1, pt2, hb = point_from_geo(
            geo,
            lip_support(1, side),
            lip_support(2, side),
            headbasesupport(cheliceraemembraneupper(side)),
        )

        line_dir = pt1.position() - pt2.position()
        assert abs(line_dir.y()) > 1e-6, "Line direction is perpendicular to Y"
        offset = line_dir * (delta_y / line_dir.y())

        pt1.setPosition(pt1.position() + offset)
        hb.setPosition(hb.position() + offset)


def _retopo_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    for side in (1, -1):
        _retopo_side(geo, side)

def _retopo_side(geo: hou.Geometry, side: int) -> None:
    b, hb, s, hs, lip1, lip2, lip3, lip4 = point_from_geo(
        geo,
        basemaxilla(side),
        headbasesupport(basemaxilla(side)),
        basesternum(side, 2),
        headbasesupport(basesternum(side, 2)),
        lip_base_support(1, side),
        lip_base_support(2, side),
        lip_base_support(3, side),
        lip_base_support(4, side),
    )

    corners = tuple(point.position() for point in (s, hs, b, hb))
    intermediates = [
        _add_named_point(
            geo,
            _position_in_quad(*corners, u, v),
            lip_intermediate(index, side),
        )
        for index, (u, v) in enumerate(TRANSITION_UVS, start=1)
    ]
    i1, i2, i3, i4 = intermediates

    quads = [
        [b, s, i4, lip4],
        [lip4, i4, i3, lip3],
        [lip3, i3, i2, lip2],
        [lip2, i2, i1, lip1],
        [lip1, i1, hs, hb],
        [s, hs, i1, i4],
        [i4, i1, i2, i3],
    ]
    for quad in quads:
        _add_quad(geo, quad if side > 0 else list(reversed(quad)))

def _position_in_quad(
    bottom_left: hou.Vector3,
    bottom_right: hou.Vector3,
    top_left: hou.Vector3,
    top_right: hou.Vector3,
    u: float,
    v: float,
) -> hou.Vector3:
    bottom = bottom_left * (1.0 - u) + bottom_right * u
    top = top_left * (1.0 - u) + top_right * u
    return bottom * (1.0 - v) + top * v

def _add_named_point(
    geo: hou.Geometry,
    position: hou.Vector3,
    point_id: str,
) -> hou.Point:
    point = geo.createPoint()
    point.setPosition(position)
    set_point_id(point, point_id)
    return point

def _add_quad(
    geo: hou.Geometry,
    pts: list[hou.Point],
    region: str = "headfrontcheek",
) -> hou.Polygon:
    poly = fill_face(geo, pts)
    if geo.findPrimAttrib("region") is not None and region:
        poly.setAttribValue("region", region)
    return poly
