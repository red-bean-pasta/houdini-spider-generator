import math
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Callable

import hou

from . import base_sops
from .head import headbasesupport, headchelicerae
from .helper import (
    add_id_point,
    affix_id,
    bridge_loops,
    deduplicate_id_attr,
    fill_face_with_attr,
    inset_inner_prims,
    points_from_geo,
    points_from_loop_cut,
    positions_from_geo,
    prims_by_attr,
    rename_left_ids,
    replace_points,
    set_point_id,
    set_points_id,
    sopify_chain,
)
from houkit.attributer import add_prim_attrib, points_by_attrib
from houkit.geomath import interpolate_elliptical, rotation_to
from houkit.noder import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    get_parent,
    sopify,
)
from houkit.parameterizer import add_float_parm, add_heading, get_float_parm, get_parms
from houkit.topology import (
    fill_face,
    find_prim,
    get_prim_centroid,
    loop_cut,
    merge_points,
    offset_point,
    traverse_faces_between_edges,
)


class ID(StrEnum):
    CHELICERAEMEMBRANE = auto()
    CHELICERAESTARTMEMBRANESUPPORT = auto()
    CHELICERAESTART = auto()
    CHELICERAEMIDDLE = auto()
    CHELICERAEEND = auto()
    CHELICERAEINTERMEDIATE = auto()


class Region(StrEnum):
    CHELICERA = auto()
    CHELICERASOCKET = auto()
    CHELICERAMEMBRANE = auto()
    FANG = auto()


def cheliceraemembrane(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMEMBRANE, *i)
def cheliceraestartmembranesupport(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTARTMEMBRANESUPPORT, *i)
def cheliceraestart(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTART, *i)
def cheliceraemiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMIDDLE, *i)
def cheliceraeend(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEEND, *i)
def cheliceraeintermediate(ratio: float | None = None, *i: int | str) -> str:
    if ratio is None:
        return affix_id(ID.CHELICERAEINTERMEDIATE)
    return affix_id(ID.CHELICERAEINTERMEDIATE, ratio, *i)

def bottom_middle(id_factory: Callable[..., str], *i: int | str | float, j: tuple[int | str | float, ...] | int | str | float = ()) -> str:
    j_tuple = j if isinstance(j, tuple) else (j,)
    return id_factory(*j_tuple, "", "bottommiddle", *i)
def upper_middle(id_factory: Callable[..., str], *i: int | str | float, j: tuple[int | str | float, ...] | int | str | float = ()) -> str:
    j_tuple = j if isinstance(j, tuple) else (j,)
    return id_factory(*j_tuple, "", "uppermiddle", *i)


def build(cephalothorax: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    chelicerae = add_reloadable_subnet(cephalothorax, "chelicerae")
    chelicerae.setInput(0, source)
    _add_parameters(chelicerae)

    right_membrane = sopify_chain(
        chelicerae,
        chelicerae.indirectInputs()[0],
        (_build_geometry, _inset_flaps, _classify_after_inset, _prepare_extrusion, _remove_left_membrane),
    )
    adjusted_start_section = sopify_chain(
        chelicerae,
        right_membrane,
        (_add_start_membrane, _inset_start_membrane, _adjust_start_section_left),
    )
    lower_middle_section = sopify_chain(
        chelicerae,
        adjusted_start_section,
        (_add_end_section, _add_middle_section, _add_upper_middle_section, _add_lower_middle_section),
    )
    cut_tube = sopify_chain(
        chelicerae,
        lower_middle_section,
        (_connect_sections, _remove_middle_face, _middle_loop_cut),
    )
    adjusted_right = sopify_chain(
        chelicerae,
        cut_tube,
        (_merge_membrane_curves, _adjust_start_membrane_curve, _adjust_right_membrane_width),
    )
    clamped_start = sopify_chain(
        chelicerae,
        adjusted_right,
        (
            _adjust_head_chelicerae_depth,
            _inset_chelicerae_support_loop,
            _add_start_membrane_support_loops,
            _add_start_section_support_loops,
        ),
    )

    mirrored = add_mirror(chelicerae, "mirror_left_chelicerae", clamped_start, (1, 0, 0), True, True)
    renamed = sopify(chelicerae, mirrored, _rename_left_ids)

    fuse_mirrors = add_fuse(chelicerae, "fuse_mirrors", renamed)
    all_merge = add_merge(chelicerae, "merge_head_and_chelicerae", chelicerae.indirectInputs()[0], fuse_mirrors)
    all_fuse = add_fuse(chelicerae, "fuse_head_and_chelicerae", all_merge)
    deduplicated = sopify(chelicerae, all_fuse, _deduplicate_base_faces)

    add_output(chelicerae, "OUT_CHELICERAE", deduplicated)
    chelicerae.layoutChildren()
    return chelicerae


def _add_parameters(chelicerae: hou.SopNode) -> None:
    add_float_parm(
        chelicerae,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )
    add_heading(
        chelicerae,
        "End Section",
    )
    add_float_parm(
        chelicerae,
        "end_section_ratio",
        2,
        (0.25, 0.25),
        (0.0, None),
        label="End Section Size",
        help="X scales width and Y scales height relative to the start section.",
    )
    add_float_parm(
        chelicerae,
        "end_section_offset",
        3,
        (0.2, 3.15, 1.25),
        label="End Section Offset",
        help="Offsets the end section in its local width, height, and length directions.",
    )
    add_float_parm(
        chelicerae,
        "end_section_rotation",
        2,
        (-90.0, 0.0),
        label="End Section Rotation",
        help="X and Y set the two local rotation directions.",
    )
    add_heading(
        chelicerae,
        "Middle Section",
    )
    add_float_parm(
        chelicerae,
        "middle_section_ratio",
        2,
        (1.0, 1.2),
        (0.0, None),
        label="Middle Section Size",
        help="X scales width and Y scales height relative to the start section.",
    )
    add_float_parm(
        chelicerae,
        "middle_section_offset",
        2,
        (0.1, 2.0),
        label="Middle Section Offset",
        help="Moves the middle section through its local width and length plane.",
    )
    add_float_parm(
        chelicerae,
        "middle_section_height_ratio",
        1,
        0.5,
        (0.0, 1.0),
        label="Middle Section Height",
        help="Vertical placement between the start and end sections.",
    )


def _build_geometry(node: hou.SopNode) -> None:
    geo = node.geometry()

    base_ids = (
        base_sops.basemaxilla(-1),
        base_sops.basesternum(-1, 1),
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
        base_sops.basemaxilla(1),
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


def _inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")

    lower, upper = points_from_geo(
        geo,
        base_sops.basesternum(0),
        headchelicerae(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    chelicera_prims = prims_by_attr(geo, "region", Region.CHELICERA)
    inner = _inset_and_recess(chelicera_prims, dist / 4, dist)
    for prim in inner:
        prim.setAttribValue("region", Region.CHELICERASOCKET)

    for prim in prims_by_attr(geo, "region", Region.CHELICERA):
        prim.setAttribValue("region", Region.CHELICERAMEMBRANE)


def _classify_after_inset(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = prims_by_attr(geo, "region", Region.CHELICERASOCKET)
    pts_dict = {}
    for prim in socket_prims:
        for pt in prim.points():
            pts_dict[pt.number()] = pt
    points = list(pts_dict.values())
    points.sort(key=lambda p: p.position().x())
    assert len(points) == 10, f"Expected 10 points in the whole socket, got {len(points)}"

    left_outer = sorted(points[:2], key=lambda p: p.position().y())
    left_mid = sorted(points[2:4], key=lambda p: p.position().y())
    center = sorted(points[4:6], key=lambda p: p.position().y())
    right_mid = sorted(points[6:8], key=lambda p: p.position().y())
    right_outer = sorted(points[8:], key=lambda p: p.position().y())

    set_point_id(left_outer[0], cheliceraemembrane(-3))
    set_point_id(left_outer[1], cheliceraemembrane(-4))
    set_point_id(left_mid[0], cheliceraemembrane(-2))
    set_point_id(left_mid[1], cheliceraemembrane(-5))
    set_point_id(center[0], cheliceraemembrane(1))
    set_point_id(center[1], cheliceraemembrane(6))
    set_point_id(right_mid[0], cheliceraemembrane(2))
    set_point_id(right_mid[1], cheliceraemembrane(5))
    set_point_id(right_outer[0], cheliceraemembrane(3))
    set_point_id(right_outer[1], cheliceraemembrane(4))
    deduplicate_id_attr(geo, None, add_affix=False)


def _prepare_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims = prims_by_attr(geo, "region", Region.CHELICERASOCKET, startswith=True)
    geo.deletePrims(socket_prims)


def _remove_left_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    left_prims = [
        prim for prim in prims_by_attr(geo, "region", Region.CHELICERAMEMBRANE)
        if get_prim_centroid(prim).x() < 0.0
    ]
    left_points = list({
        pt.number(): pt
        for prim in left_prims
        for pt in prim.points()
        if pt.position().x() < -1e-4
    }.values())
    geo.deletePoints(left_points)


def _add_start_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)

    b0, u0, m6 = points_from_geo(
        geo,
        base_sops.basesternum(0),
        headchelicerae(0),
        cheliceraemembrane(6),
    )
    membrane_points = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(6),
        cheliceraemembrane(4),
        cheliceraemembrane(3),
    )

    end_section_offset = params.end_section_offset
    middle_section_offset = params.middle_section_offset
    middle_section_height_ratio = params.middle_section_height_ratio

    dir_y = -end_section_offset.y() * middle_section_height_ratio
    dir_z = -middle_section_offset.y()
    dir_zy = hou.Vector3(0.0, dir_y, dir_z).normalized()

    target_y = u0.position().y() - (u0.position().y() - b0.position().y()) * (1.0 / 3.0)
    dist = (target_y - m6.position().y()) / dir_zy.y()
    offsets = (
        hou.Vector3(0.0, 0.0, -dist * 0.5),
        dir_zy * dist,
        dir_zy * dist,
        hou.Vector3(0.0, 0.0, -dist * 0.5),
    )

    pts = [
        add_id_point(geo, start.position() + offset, cheliceraestart(j))
        for j, (start, offset) in enumerate(zip(membrane_points, offsets), start=1)
    ]

    fill_face(pts, True)


def _inset_start_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    lower, upper = points_from_geo(
        geo,
        base_sops.basesternum(0),
        headchelicerae(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    start_points = points_from_geo(geo, *(cheliceraestart(j) for j in range(1, 5)))
    start_prim = next(prim for prim in start_points[0].prims() if all(pt in start_points for pt in prim.points()))
    _inset_and_recess([start_prim], dist / 4, dist, delete_inset_prims=True)

    for j, pt in enumerate(start_points, start=1):
        set_point_id(pt, cheliceraestartmembranesupport(j))


def _adjust_start_section_left(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s1, s2, ss1, ss2 = points_from_geo(
        geo,
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
    )
    ratio = 1/3
    for s, ss in ((s1, ss1), (s2, ss2)):
        pos = s.position()
        new_x = pos.x() * ratio + ss.position().x() * (1 - ratio)
        s.setPosition(hou.Vector3(new_x, pos.y(), pos.z()))


def _add_end_section(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)
    end_section_ratio = params.end_section_ratio

    start_section, end_pivot, end_rot_matrix, end_surface_normal = _get_end_section_frame(geo, parent)

    c3_positions = _construct_section_loop(
        end_pivot,
        hou.Vector2(start_section.height * end_section_ratio.y(), start_section.width * end_section_ratio.x()),
        start_section.along * end_rot_matrix,
        end_surface_normal,
    )

    for pos in c3_positions:
        assert pos.x() >= 0.0, f"End section loop point crossed symmetry plane (x={pos.x():.4f} < 0.0). Adjust parameters."

    c3_pts = [
        add_id_point(geo, pos, cheliceraeend(j))
        for j, pos in enumerate(c3_positions, start=1)
    ]

    add_prim_attrib(geo, "region", "")
    fill_face_with_attr(geo, c3_pts, "region", Region.FANG, True)


@dataclass
class Section:
    pivot: hou.Vector3
    points: tuple[hou.Point, hou.Point, hou.Point, hou.Point]
    along: hou.Vector3
    normal: hou.Vector3
    width: float
    height: float

    @property
    def offset_baseline(self) -> hou.Vector3:
        return hou.Vector3(self.width, self.height, self.height)


def _get_start_section_frame(geo: hou.Geometry) -> Section:
    c1_1, c1_2, c1_3, c1_4 = points_from_geo(
        geo,
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraestart(3),
        cheliceraestart(4),
    )

    pivot = (c1_1.position() + c1_2.position() + c1_3.position() + c1_4.position()) / 4.0
    along = (c1_1.position() - c1_2.position()).normalized()
    normal = (c1_2.position() - c1_1.position()).cross(c1_4.position() - c1_1.position()).normalized()
    w = (c1_4.position() - c1_1.position()).length()
    h = (c1_2.position() - c1_1.position()).length()
    return Section(
        pivot,
        (c1_1, c1_2, c1_3, c1_4),
        along,
        normal,
        w,
        h,
    )


def _get_end_section_frame(geo: hou.Geometry, parent: hou.OpNode) -> tuple[Section, hou.Vector3, hou.Matrix3, hou.Vector3]:
    params = get_parms(parent, use_tuple=False)
    end_section_offset = params.end_section_offset
    end_section_rotation = params.end_section_rotation

    start_section = _get_start_section_frame(geo)
    offset_baseline = start_section.offset_baseline

    end_pivot_offset = hou.Vector3(end_section_offset.x(), -end_section_offset.y(), -end_section_offset.z())
    end_pivot = start_section.pivot + hou.Vector3(
        offset_baseline.x() * end_pivot_offset.x(),
        offset_baseline.y() * end_pivot_offset.y(),
        offset_baseline.z() * end_pivot_offset.z(),
    )

    end_rot_matrix = hou.hmath.buildRotate(end_section_rotation.x(), 0.0, end_section_rotation.y())
    end_surface_normal = start_section.normal * end_rot_matrix
    return start_section, end_pivot, end_rot_matrix, end_surface_normal


def _construct_section_loop(
    pivot: hou.Vector3,
    size: hou.Vector2,
    along: hou.Vector3,
    normal: hou.Vector3,
) -> list[hou.Vector3]:
    normal = normal.normalized()
    along = along.normalized()
    along = (along - normal * along.dot(normal)).normalized()
    side = normal.cross(along).normalized()

    half_h, half_w = size.x() / 2.0, size.y() / 2.0
    corners = (
        (half_h, half_w),
        (-half_h, half_w),
        (-half_h, -half_w),
        (half_h, -half_w),
    )
    return [
        pivot + along * ah + side * sw
        for ah, sw in corners
    ]


def _add_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.5, cheliceraemiddle)


def _add_upper_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.25, lambda *i: cheliceraeintermediate(0.25, *i))


def _add_lower_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.75, lambda *i: cheliceraeintermediate(0.75, *i))


def _add_intermediate_section(
    node: hou.SopNode,
    factor: float,
    id_factory: Callable[[int], str] | None,
) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    params = get_parms(parent, use_tuple=False)
    end_section_ratio = params.end_section_ratio
    middle_section_offset = params.middle_section_offset
    middle_section_height_ratio = params.middle_section_height_ratio
    middle_section_ratio = params.middle_section_ratio

    start_section, end_pivot, _, end_surface_normal = _get_end_section_frame(geo, parent)
    offset_baseline = start_section.offset_baseline

    middle_pivot = _get_middle_section_pivot(
        start_section,
        end_pivot,
        offset_baseline,
        middle_section_offset,
        middle_section_height_ratio,
    )
    pivot, direction, normal, weights = _get_intermediate_section_frame(
        start_section.pivot,
        middle_pivot,
        end_pivot,
        start_section.along,
        end_surface_normal,
        start_section.normal,
        factor,
    )

    start_size = hou.Vector2(start_section.height, start_section.width)
    size = _get_intermediate_section_size(
        start_size,
        middle_section_ratio,
        end_section_ratio,
        weights,
    )

    positions = _construct_section_loop(
        pivot,
        size,
        direction,
        normal,
    )

    for pos in positions:
        assert pos.x() >= 0.0, f"Section loop point at factor {factor} crossed symmetry plane (x={pos.x():.4f} < 0.0). Adjust parameters or ratio."

    pts = _add_intermediate_section_points(geo, positions, id_factory)
    fill_face(pts, True)


def _get_middle_section_pivot(
    start_section: Section,
    end_pivot: hou.Vector3,
    offset_baseline: hou.Vector3,
    middle_section_offset: hou.Vector2,
    middle_section_height_ratio: float,
) -> hou.Vector3:
    return hou.Vector3(
        start_section.pivot.x() + offset_baseline.x() * middle_section_offset.x(),
        start_section.pivot.y() + (end_pivot.y() - start_section.pivot.y()) * middle_section_height_ratio,
        start_section.pivot.z() - offset_baseline.z() * middle_section_offset.y(),
    )


def _get_intermediate_section_frame(
    start_pivot: hou.Vector3,
    middle_pivot: hou.Vector3,
    end_pivot: hou.Vector3,
    start_along: hou.Vector3,
    end_surface_normal: hou.Vector3,
    start_normal: hou.Vector3,
    factor: float,
) -> tuple[hou.Vector3, hou.Vector3, hou.Vector3, tuple[float, float, float]]:
    evaluate = interpolate_elliptical(
        start_pivot,
        middle_pivot,
        end_pivot,
        start_along,
        -end_surface_normal,
    )

    along_axis = (end_pivot - start_pivot).normalized()
    chord_length = (end_pivot - start_pivot).length()
    middle_t = (middle_pivot - start_pivot).dot(along_axis) / chord_length

    f_upper = min(factor * 2.0, 1.0)
    f_lower = max(factor * 2.0 - 1.0, 0.0)
    w_start = 1.0 - f_upper
    w_mid = f_upper - f_lower
    w_end = f_lower
    t = middle_t * w_mid + w_end

    pivot, direction = evaluate(t)
    normal = rotation_to(start_along, direction).rotate(start_normal)
    return pivot, direction, normal, (w_start, w_mid, w_end)


def _get_intermediate_section_size(
    start_size: hou.Vector2,
    middle_section_ratio: hou.Vector2,
    end_section_ratio: hou.Vector2,
    weights: tuple[float, float, float],
) -> hou.Vector2:
    w_start, w_mid, w_end = weights
    middle_size = hou.Vector2(
        start_size.x() * middle_section_ratio.y(),
        start_size.y() * middle_section_ratio.x(),
    )
    end_size = hou.Vector2(
        start_size.x() * end_section_ratio.y(),
        start_size.y() * end_section_ratio.x(),
    )
    return start_size * w_start + middle_size * w_mid + end_size * w_end


def _add_intermediate_section_points(
    geo: hou.Geometry,
    positions: list[hou.Vector3],
    id_factory: Callable[[int], str] | None,
) -> list[hou.Point]:
    if id_factory:
        return [
            add_id_point(geo, pos, id_factory(j))
            for j, pos in enumerate(positions, start=1)
        ]

    pts = [geo.createPoint() for _ in positions]
    for pt, pos in zip(pts, positions):
        pt.setPosition(pos)
    return pts


def _connect_sections(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    _remove_section_cap_faces(geo)
    _connect_membrane_to_start_support(geo)
    _bridge_chelicerae_section_loops(geo)


def _remove_section_cap_faces(geo: hou.Geometry) -> None:
    def is_cap_face(prim: hou.Prim) -> bool:
        if prim.stringAttribValue("region") == Region.FANG:
            return False
        pt_ids = [pt.stringAttribValue("id") for pt in prim.points()]
        if not all(pid.startswith((cheliceraestart(), cheliceraemiddle(), cheliceraeintermediate())) for pid in pt_ids):
            return False
        prefixes = {pid.rstrip("0123456789-") for pid in pt_ids}
        return len(prefixes) == 1

    middle_prims = [prim for prim in geo.prims() if is_cap_face(prim)]
    geo.deletePrims(middle_prims, keep_points=True)


def _connect_membrane_to_start_support(geo: hou.Geometry) -> None:
    # Connect socket membrane (4 corner points) to start membrane support (4 points)
    m1, m3, m4, m6 = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraemembrane(6),
    )
    ss1, ss2, ss3, ss4 = points_from_geo(
        geo,
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
    )

    # Medial face: (m1, m6, ss2, ss1)
    fill_face([m1, m6, ss2, ss1], True)
    # Top face: (m6, m4, ss3, ss2)
    fill_face([m6, m4, ss3, ss2], True)
    # Lateral face: (m4, m3, ss4, ss3)
    fill_face([m4, m3, ss4, ss3], True)
    # Bottom face: (m3, m1, ss1, ss4)
    fill_face([m3, m1, ss1, ss4], True)


def _bridge_chelicerae_section_loops(geo: hou.Geometry) -> None:
    tube_loops = [
        points_from_geo(
            geo,
            cheliceraestart(1),
            cheliceraestart(2),
            cheliceraestart(3),
            cheliceraestart(4),
        ),
        points_from_geo(geo, *(cheliceraeintermediate(0.25, j) for j in range(1, 5))),
        points_from_geo(geo, *(cheliceraemiddle(j) for j in range(1, 5))),
        points_from_geo(geo, *(cheliceraeintermediate(0.75, j) for j in range(1, 5))),
        points_from_geo(geo, *(cheliceraeend(j) for j in range(1, 5))),
    ]

    for i in range(len(tube_loops) - 1):
        current_loop = tube_loops[i]
        next_loop = tube_loops[i + 1]
        bridge_loops(geo, current_loop, next_loop, reverse=True)


def _remove_middle_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    membrane1, membrane6, support1, support2 = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(6),
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
    )
    middle_face = find_prim(membrane1, membrane6, support1, support2)
    geo.deletePrims([middle_face], keep_points=True)


def _middle_loop_cut(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s2, s3 = points_from_geo(
        geo,
        cheliceraestart(2),
        cheliceraestart(3),
    )
    top_edge = geo.findEdge(s2, s3)
    assert top_edge is not None, "Expected top edge between cheliceraestart(2) and cheliceraestart(3)"
    added_points = points_from_loop_cut(loop_cut(top_edge.prims()[0], s2, s3, 1 / 3, use_ratio=True))
    cut_ids = [
        bottom_middle(cheliceraemembrane, 1),
        bottom_middle(cheliceraestartmembranesupport, 1),
        bottom_middle(cheliceraestart, 1),
        bottom_middle(cheliceraeintermediate, 1, j=0.25),
        bottom_middle(cheliceraemiddle, 1),
        bottom_middle(cheliceraeintermediate, 1, j=0.75),
        bottom_middle(cheliceraeend, 1),
        upper_middle(cheliceraeend, 1),
        upper_middle(cheliceraeintermediate, 1, j=0.75),
        upper_middle(cheliceraemiddle, 1),
        upper_middle(cheliceraeintermediate, 1, j=0.25),
        upper_middle(cheliceraestart, 1),
        upper_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraemembrane, 1),
    ]
    set_points_id(added_points, cut_ids)


def _merge_membrane_curves(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m2, m5, top_cut, bottom_cut = points_from_geo(
        geo,
        cheliceraemembrane(2),
        cheliceraemembrane(5),
        upper_middle(cheliceraemembrane, 1),
        bottom_middle(cheliceraemembrane, 1),
    )
    merge_points([
        (m5, top_cut),
        (m2, bottom_cut),
    ])


def _adjust_start_membrane_curve(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m2, m3, m4, m5, ss3, ss4, s3, s4 = points_from_geo(
        geo,
        cheliceraemembrane(2),
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraemembrane(5),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
        cheliceraestart(3),
        cheliceraestart(4),
    )
    upper_width = m4.position().distanceTo(ss3.position())
    bottom_width = m3.position().distanceTo(ss4.position())

    support_bottom_mid, support_upper_mid, start_bottom_mid, start_upper_mid = points_from_geo(
        geo,
        bottom_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraestartmembranesupport, 1),
        bottom_middle(cheliceraestart, 1),
        upper_middle(cheliceraestart, 1),
    )
    upper_offset = (
        (m5.position() - support_upper_mid.position()).normalized()
        * upper_width
        * 1/2
    )
    bottom_offset = (
        (m2.position() - support_bottom_mid.position()).normalized()
        * bottom_width
        * 1/2
    )

    for point in (support_upper_mid, start_upper_mid):
        offset_point(point, upper_offset)
    for point in (support_bottom_mid, start_bottom_mid):
        offset_point(point, bottom_offset)


def _adjust_right_membrane_width(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m3, m4, ss3, ss4, s3, s4 = points_from_geo(
        geo,
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
        cheliceraestart(3),
        cheliceraestart(4),
    )
    upper_offset = (ss3.position() - m4.position()) * 0.5
    bottom_offset = (ss4.position() - m3.position()) * 0.5
    for point in (ss3, s3):
        offset_point(point, upper_offset)
    for point in (ss4, s4):
        offset_point(point, bottom_offset)


def _adjust_head_chelicerae_depth(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    # h0: headchelicerae0, hs0: headbasesupport_headchelicerae0
    # c6: cheliceraemembrane6, cs6: cheliceraestartmembranesupport2
    h0, hs0, c6, cs6 = points_from_geo(
        geo,
        headchelicerae(0),
        headbasesupport(headchelicerae(0)),
        cheliceraemembrane(6),
        cheliceraestartmembranesupport(2),
    )
    for pt in (h0, hs0, c6, cs6):
        assert abs(pt.position().x()) < 1e-4

    dh = (h0.position() - hs0.position()).normalized()
    dc = (cs6.position() - c6.position()).normalized()

    v0 = h0.position() - c6.position()
    v_perp = (v0 - dc * v0.dot(dc)).normalized()
    angle = math.radians(10)
    d_target = dc * math.cos(angle) + v_perp * math.sin(angle)

    denom = (d_target.cross(dh)).x()
    assert abs(denom) > 1e-6, "Target direction and head direction are nearly parallel"
    t = (v0.cross(d_target)).x() / denom
    offset_point(h0, dh * t)


def _inset_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    support_prims = _get_chelicerae_support_strip_prims(geo)

    # Inset distance evaluated from the start membrane gap (1/3 of gap)
    start_membrane_support, start_point = points_from_geo(
        geo,
        cheliceraestartmembranesupport(2),
        cheliceraestart(2),
    )
    start_membrane_gap = start_membrane_support.position().distanceTo(start_point.position())
    dist = start_membrane_gap / 3.0
    inset_inner_prims(geo, support_prims, dist, use_ratio=False)

    _adjust_chelicerae_support_loop(node)
    deduplicate_id_attr(geo, None, keep_first=True)


def _get_chelicerae_support_strip_prims(geo: hou.Geometry) -> list[hou.Prim]:
    # Boundary vertices along the upper-medial edge (#2) of the chelicera tube
    medial_upper_points = points_from_geo(
        geo,
        headbasesupport(headchelicerae(0)),
        cheliceraeend(2),
    )
    # Opposing vertices along the upper-middle loop cut (#uppermiddle_1)
    upper_middle_points = points_from_geo(
        geo,
        headbasesupport(headchelicerae(1)),
        upper_middle(cheliceraeend, 1),
    )
    # Boundary vertices along the upper-lateral edge (#3) of the chelicera tube
    lateral_upper_points = points_from_geo(
        geo,
        headbasesupport(headchelicerae(2)),
        cheliceraeend(3),
    )
    side_points = points_from_geo(
        geo,
        headchelicerae(0),
        headchelicerae(2),
    )
    # Form the full upper quad strip (medial and lateral halves)
    left_prims = [
        prim
        for prim in traverse_faces_between_edges(
            (medial_upper_points[0], upper_middle_points[0]),
            (medial_upper_points[1], upper_middle_points[1]),
            side_points[0],
        )
    ]
    right_prims = [
        prim
        for prim in traverse_faces_between_edges(
            (lateral_upper_points[0], upper_middle_points[0]),
            (lateral_upper_points[1], upper_middle_points[1]),
            side_points[1],
        )
    ]
    return left_prims + right_prims

def _adjust_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    # This method adjusts the points position so the topology becomes more natural and smooth at certain places
    by_id = points_by_attrib(geo, "id", skip_blank=True)
    _adjust_right_chelicerae_support_points(by_id)
    _adjust_right_chelicerae_membrane_points(by_id)
    _adjust_left_chelicerae_support_points(by_id)
    _adjust_bottom_chelicerae_support_points(by_id)

def _adjust_right_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # For the right half support points, move them along 1/2 towards the upper middle line
    sections = (
        (headbasesupport(headchelicerae(2)), headbasesupport(headchelicerae(1))),
        (headchelicerae(2), headchelicerae(1)),
        (cheliceraemembrane(4), cheliceraemembrane(5)),
        (cheliceraestartmembranesupport(3), upper_middle(cheliceraestartmembranesupport, 1)),
        (cheliceraestart(3), upper_middle(cheliceraestart, 1)),
        (cheliceraeintermediate(0.25, 3), upper_middle(cheliceraeintermediate, 1, j=0.25)),
        (cheliceraemiddle(3), upper_middle(cheliceraemiddle, 1)),
        (cheliceraeintermediate(0.75, 3), upper_middle(cheliceraeintermediate, 1, j=0.75)),
        (cheliceraeend(3), upper_middle(cheliceraeend, 1)),
    )
    for support_id, mid_id in sections:
        inset_support = _get_inset_chelicerae_support_point(points_by_id, support_id)
        inset_mid = _get_inset_chelicerae_support_point(points_by_id, mid_id)
        inset_support.setPosition((inset_support.position() + inset_mid.position()) * 0.5)

def _adjust_right_chelicerae_membrane_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # for inset_cheliceraestartmambranesupport3
    # move it along inset_cheliceraestartmambranesupport3-inset_cheliceraemembrane4
    # so that it's y is at 1/4 of the y_offset of cheliceraestartmambranesupport_uppermiddle1-cheliceraestartmambranesupport3
    # apply the same offset to inset_cheliceraestart3
    inset_support3 = _get_inset_chelicerae_support_point(points_by_id, cheliceraestartmembranesupport(3))
    inset_membrane4 = _get_inset_chelicerae_support_point(points_by_id, cheliceraemembrane(4))
    inset_start3 = _get_inset_chelicerae_support_point(points_by_id, cheliceraestart(3))

    support3 = _get_original_chelicerae_point(points_by_id, cheliceraestartmembranesupport(3))
    support_uppermid = _get_original_chelicerae_point(points_by_id, upper_middle(cheliceraestartmembranesupport, 1))

    target_y = (
       support_uppermid.position().y() * 3/4
       + support3.position().y() * 1/4
    )
    direction = inset_support3.position() - inset_membrane4.position()
    assert abs(direction.y()) > 1e-6, "Expected non-zero y component in direction"
    offset = direction * ((target_y - inset_support3.position().y()) / direction.y())

    for point in (inset_support3, inset_start3):
        offset_point(point, offset)

def _adjust_left_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    # For the left half support points, new cuts at headbasesupport and headchelicerae are moved to 1/2
    sections = (
        (headbasesupport(headchelicerae(0)), headbasesupport(headchelicerae(1)), 0.0),
        (headchelicerae(0), headchelicerae(1), 0.0),
        (cheliceraemembrane(6), cheliceraemembrane(5), 0.0),
        (cheliceraestartmembranesupport(2), upper_middle(cheliceraestartmembranesupport, 1), 0.0),
        (cheliceraestart(2), upper_middle(cheliceraestart, 1), 0.0),
        (cheliceraeintermediate(0.25, 2), upper_middle(cheliceraeintermediate, 1, j=0.25), 0.25),
        (cheliceraemiddle(2), upper_middle(cheliceraemiddle, 1), 0.5),
        (cheliceraeintermediate(0.75, 2), upper_middle(cheliceraeintermediate, 1, j=0.75), 0.5),
        (cheliceraeend(2), upper_middle(cheliceraeend, 1), 0.5),
    )
    for support_id, mid_id, ratio in sections:
        if ratio == 0.0:
            continue
        inset_support = _get_inset_chelicerae_support_point(points_by_id, support_id)
        inset_mid = _get_inset_chelicerae_support_point(points_by_id, mid_id)
        inset_support.setPosition(inset_support.position() * (1.0 - ratio) + inset_mid.position() * ratio)

def _adjust_bottom_chelicerae_support_points(points_by_id: dict[str, set[hou.Point]]) -> None:
    sections = (
        (cheliceraeend(2), cheliceraeintermediate(0.75, 2)),
        (upper_middle(cheliceraeend, 1), upper_middle(cheliceraeintermediate, 1, j=0.75)),
        (cheliceraeend(3), cheliceraeintermediate(0.75, 3)),
    )
    for end_id, section_id in sections:
        inset_end = _get_inset_chelicerae_support_point(points_by_id, end_id)
        inset_section = _get_inset_chelicerae_support_point(points_by_id, section_id)
        inset_end.setPosition((inset_end.position() + inset_section.position()) * 0.5)

def _get_original_chelicerae_point(points_by_id: dict[str, set[hou.Point]], pt_id: str) -> hou.Point:
    return min(points_by_id[pt_id], key=lambda pt: pt.number())

def _get_inset_chelicerae_support_point(points_by_id: dict[str, set[hou.Point]], pt_id: str) -> hou.Point:
    return max(points_by_id[pt_id], key=lambda pt: pt.number())


def _add_start_membrane_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    membrane, support = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraestartmembranesupport(1),
    )
    _added = _add_support_loop(geo, ratio, membrane, support)
    _add_support_loop(geo, ratio, support, _added[0])


def _add_start_section_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    start, middle = points_from_geo(
        geo,
        cheliceraestart(2),
        cheliceraeintermediate(0.25, 2),
    )
    _add_support_loop(geo, ratio, start, middle)


def _rename_left_ids(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry(), affix_index=-1)


def _deduplicate_base_faces(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    base_id_sets = []
    for sign in (1, -1):
        base_id_sets.append({
            headchelicerae(0),
            headchelicerae(sign * 1),
            headbasesupport(headchelicerae(sign * 1)),
            headbasesupport(headchelicerae(0)),
        })
        base_id_sets.append({
            headchelicerae(sign * 1),
            headchelicerae(sign * 2),
            headbasesupport(headchelicerae(sign * 2)),
            headbasesupport(headchelicerae(sign * 1)),
        })

    duplicate_prims = [
        prim for prim in geo.prims()
        if {pt.stringAttribValue("id") for pt in prim.points()} in base_id_sets
    ]
    geo.deletePrims(duplicate_prims, keep_points=False)


def _inset_and_recess(
        prims: list[hou.Prim],
        inset_dist: float,
        recess_dist: float,
        delete_inset_prims: bool = False,
) -> list[hou.Prim]:
    geo = prims[0].geometry()
    inner = inset_inner_prims(geo, prims, inset_dist, use_ratio=False)
    norm = inner[0].normal()
    inner_pts = list({pt.number(): pt for prim in inner for pt in prim.points()}.values())
    if delete_inset_prims:
        inner[0].geometry().deletePrims(inner, keep_points=True)

    # Move inset points along the face normal backwards by its width to create a seam
    for pt in inner_pts:
        pt.setPosition(pt.position() - norm * recess_dist)
    return inner


def _add_support_loop(
        geo: hou.Geometry,
        ratio: float,
        start_point: hou.Point,
        end_point: hou.Point,
) -> list[hou.Point]:
    edge = geo.findEdge(start_point, end_point)
    assert edge is not None, "Expected start membrane support edge"
    prim = edge.prims()[0]
    added_points = points_from_loop_cut(loop_cut(prim, start_point, end_point, ratio, use_ratio=True))
    return added_points
