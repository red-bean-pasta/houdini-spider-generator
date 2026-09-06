from enum import StrEnum, auto

import hou

from base_sops import basemaxilla
from chelicerae import cheliceraemembraneupper
from head import headbasesupport, headfront, headsupport
from helper import affix_id, points_by_id, set_point_id
from utilities.common import (
    add_float_param,
    fill_face,
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
    I = auto()

def lip_support(*i: int | str) -> str:
    return affix_id(ID.LIPSUPPORT, *i)
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
    points = points_by_id(geo)

    c0 = points[cheliceraemembraneupper(0)]
    h0 = points[headbasesupport(cheliceraemembraneupper(0))]
    c1 = points[cheliceraemembraneupper(1)]
    h1 = points[headbasesupport(cheliceraemembraneupper(1))]
    c_neg1 = points[cheliceraemembraneupper(-1)]
    h_neg1 = points[headbasesupport(cheliceraemembraneupper(-1))]

    prim_right = next(
        p for p in c0.prims()
        if h0 in p.points() and c1 in p.points() and h1 in p.points()
    )
    prim_left = next(
        p for p in c0.prims()
        if h0 in p.points() and c_neg1 in p.points() and h_neg1 in p.points()
    )

    ratios = LOOP_RATIOS
    delta_ratios = [
        ratios[i]
        if i < 1 else
        (ratios[i] - ratios[i - 1]) / (1 - (ratios[i - 1]))
        for i in range(len(ratios))
    ]

    current_start = h0
    scope = [prim_right, prim_left]
    for loop_idx, delta in enumerate(delta_ratios, start=1):
        prim_to_cut = scope[0]
        added_pts, _ = loop_cut(
            prim_to_cut,
            current_start,
            c0,
            delta,
            use_ratio=True,
            scope=scope,
        )
        for pt in added_pts:
            x = pt.position().x()
            side = 1 if x > 1e-4 else (-1 if x < -1e-4 else 0)
            set_point_id(pt, lip_support(loop_idx, side))

        current_start = next(pt for pt in added_pts if abs(pt.position().x()) < 1e-4)
        scope = [p for p in current_start.prims() if c0 in p.points()]


def _remove_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    prims_to_delete = []
    for side in (1, -1):
        c = points[cheliceraemembraneupper(side)]
        hc = points[headbasesupport(cheliceraemembraneupper(side))]
        b = points[basemaxilla(side)]
        hb = points[headbasesupport(basemaxilla(side))]
        face_pts = {c, hc, b, hb}

        prim = next(p for p in c.prims() if face_pts.issubset(set(p.points())))
        prims_to_delete.append(prim)

    geo.deletePrims(prims_to_delete, keep_points=True)


def _extrude_lip(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    parent = get_parent(node)
    ratio_x, ratio_y = get_params(parent).extrusion_ratio

    h0 = points[headbasesupport(cheliceraemembraneupper(0))]
    c0 = points[cheliceraemembraneupper(0)]
    baseline = h0.position().y() - c0.position().y()

    z_offset = -baseline * ratio_x
    y_offset = -baseline * ratio_y
    offset = hou.Vector3(0.0, y_offset, z_offset)

    for side in (0, 1, -1):
        pt1 = points[lip_support(1, side)]
        pt2 = points[lip_support(2, side)]
        pt3 = points[lip_support(3, side)]
        pt4 = points[lip_support(4, side)]
        c = points[cheliceraemembraneupper(side)]
        hb = points[headbasesupport(cheliceraemembraneupper(side))]
        hf = points[headfront(side)]
        hs = points[headsupport(side)]

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
    points = points_by_id(geo)
    parent = get_parent(node)
    lip_width_ratio = get_params(parent).lip_width_ratio

    hb1 = points[headbasesupport(basemaxilla(1))]
    b1 = points[basemaxilla(1)]
    baseline = hb1.position().y() - b1.position().y()

    loop1_0 = points[lip_support(1, 0)]
    loop2_0 = points[lip_support(2, 0)]
    existing_width = loop1_0.position().y() - loop2_0.position().y()

    delta_y = lip_width_ratio * baseline - existing_width

    for side in (0, 1, -1):
        pt1 = points[lip_support(1, side)]
        pt2 = points[lip_support(2, side)]
        hb = points[headbasesupport(cheliceraemembraneupper(side))]

        line_dir = pt1.position() - pt2.position()
        assert abs(line_dir.y()) > 1e-6, "Line direction is perpendicular to Y"
        offset = line_dir * (delta_y / line_dir.y())

        pt1.setPosition(pt1.position() + offset)
        hb.setPosition(hb.position() + offset)


def _retopo_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    for side in (1, -1):
        _retopo_side(geo, points, side)

def _retopo_side(geo: hou.Geometry, points: dict[str, hou.Point], side: int) -> None:
    b = points[basemaxilla(side)]
    c = points[cheliceraemembraneupper(side)]
    hb = points[headbasesupport(basemaxilla(side))]
    hc = points[headbasesupport(cheliceraemembraneupper(side))]

    lip1 = points[lip_support(1, side)]
    lip2 = points[lip_support(2, side)]
    lip3 = points[lip_support(3, side)]
    lip4 = points[lip_support(4, side)]

    corners = tuple(point.position() for point in (b, hb, c, hc))
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
        [c, b, i4, lip4],
        [lip4, i4, i3, lip3],
        [lip3, i3, i2, lip2],
        [lip2, i2, i1, lip1],
        [lip1, i1, hb, hc],
        [b, hb, i1, i4],
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
