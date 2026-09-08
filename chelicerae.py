from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Callable

import hou

import base_sops
from head import headchelicerae
from helper import (
    add_id_attr,
    affix_id,
    deduplicate_id_attr,
    point_from_geo,
    rename_left_ids,
    set_point_id,
    set_points_id,
)
from utilities.common import (
    add_float_param,
    add_heading,
    add_prim_attr,
    fill_face,
    find_prim,
    get_float_parm,
    get_params,
    get_parent,
    get_prim_centroid,
    points_by_attr,
    rotation_to,
)
from utilities.nodes import (
    add_fuse,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import (
    inset,
    interpolate_elliptical,
    loop_cut,
    merge_points,
)


class ID(StrEnum):
    CHELICERAEMEMBRANE = auto()
    CHELICERAESTARTMEMBRANESUPPORT = auto()
    CHELICERAESTART = auto()
    CHELICERAEMIDDLE = auto()
    CHELICERAEEND = auto()


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

def _middle_section(ratio: float, *i: int | str) -> str:
    return affix_id("tmpsection", ratio, *i)

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

    geometry = sopify(chelicerae, chelicerae.indirectInputs()[0], _build_geometry)
    inset_node = sopify(chelicerae, geometry, _inset_flaps)
    classified = sopify(chelicerae, inset_node, _classify_after_inset)
    prepared = sopify(chelicerae, classified, _prepare_extrusion)
    right_membrane = sopify(chelicerae, prepared, _remove_left_membrane)

    start_membrane = sopify(chelicerae, right_membrane, _add_start_membrane)
    inset_start_membrane = sopify(chelicerae, start_membrane, _inset_start_membrane)
    adjusted_start_section = sopify(chelicerae, inset_start_membrane, _adjust_start_section_left)

    end_section = sopify(chelicerae, adjusted_start_section, _add_end_section)
    middle_section = sopify(chelicerae, end_section, _add_middle_section)
    upper_middle_section = sopify(chelicerae, middle_section, _add_upper_middle_section)
    lower_middle_section = sopify(chelicerae, upper_middle_section, _add_lower_middle_section)

    connected = sopify(chelicerae, lower_middle_section, _connect_sections)
    middle_face_removed = sopify(chelicerae, connected, _remove_middle_face)
    cut_tube = sopify(chelicerae, middle_face_removed, _middle_loop_cut)

    merged_membrane = sopify(chelicerae, cut_tube, _merge_membrane_curves)
    adjusted_curve = sopify(chelicerae, merged_membrane, _adjust_start_membrane_curve)
    adjusted_right = sopify(chelicerae, adjusted_curve, _adjust_right_membrane_width)
    upper_inset_start_section = sopify(chelicerae, adjusted_right, _inset_chelicerae_support_loop)

    clamped_membrane = sopify(chelicerae, upper_inset_start_section, _add_start_membrane_support_loops)
    clamped_start = sopify(chelicerae, clamped_membrane, _add_start_section_support_loops)

    mirrored = add_mirror(chelicerae, "mirror_left_chelicerae", clamped_start, (1, 0, 0), True, True)
    renamed = sopify(chelicerae, mirrored, _rename_left_ids)

    fused = add_fuse(chelicerae, "fuse_chelicerae", renamed)
    add_output(chelicerae, "OUT_CHELICERAE", fused)
    chelicerae.layoutChildren()
    return chelicerae


def _add_parameters(chelicerae: hou.SopNode) -> None:
    add_float_param(
        chelicerae,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )
    add_heading(
        chelicerae,
        "End Section",
    )
    add_float_param(
        chelicerae,
        "end_section_ratio",
        2,
        (0.25, 0.25),
        (0.0, None),
        label="Ratio",
    )
    add_float_param(
        chelicerae,
        "end_section_offset",
        3,
        (0.2, 3.5, 0.5),
        label="Offset",
    )
    add_float_param(
        chelicerae,
        "end_section_rotation",
        2,
        (-90.0, 0.0),
        label="Rotation",
    )
    add_heading(
        chelicerae,
        "Middle Section",
    )
    add_float_param(
        chelicerae,
        "middle_section_ratio",
        2,
        (1.0, 1.2),
        (0.0, None),
        label="Ratio",
    )
    add_float_param(
        chelicerae,
        "middle_section_offset",
        2,
        (0.1, 1.0),
        label="Offset",
    )
    add_float_param(
        chelicerae,
        "middle_section_height_ratio",
        1,
        0.5,
        (0.0, 1.0),
        label="Height Ratio",
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
    source_points = point_from_geo(geo, *base_ids)
    base_positions = [point.position() for point in source_points]

    upper_ids = tuple(headchelicerae(i) for i in range(-2, 3))
    upper_source_points = point_from_geo(geo, *upper_ids)
    upper_positions = [point.position() for point in upper_source_points]

    geo.clear()
    add_id_attr(geo)
    add_prim_attr(geo, "region", "")
    base_points = []
    for point_id, position in zip(base_ids, base_positions):
        point = geo.createPoint()
        point.setPosition(position)
        base_points.append(point)
    set_points_id(base_points, list(base_ids))

    upper_points = []
    for point_id, position in zip(upper_ids, upper_positions):
        point = geo.createPoint()
        point.setPosition(position)
        upper_points.append(point)
    set_points_id(upper_points, upper_ids)

    primitive = fill_face(
        geo,
        [
            *base_points,
            *reversed(upper_points),
        ],
    )
    primitive.setAttribValue("region", Region.CHELICERA)


def _inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")

    lower, upper = point_from_geo(
        geo,
        base_sops.basesternum(0),
        headchelicerae(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    chelicera_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == Region.CHELICERA
    ]
    inner = _inset_and_recess(chelicera_prims, dist)
    for prim in inner:
        prim.setAttribValue("region", Region.CHELICERASOCKET)

    for prim in geo.prims():
        if prim.stringAttribValue("region") != Region.CHELICERASOCKET:
            prim.setAttribValue("region", Region.CHELICERAMEMBRANE)


def _classify_after_inset(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == Region.CHELICERASOCKET
    ]
    pts_dict = {}
    for prim in socket_prims:
        for pt in prim.points():
            pts_dict[pt.number()] = pt
    points = list(pts_dict.values())
    points.sort(key=lambda pt: pt.position().x())
    assert len(points) == 10, f"Expected 10 points in the whole socket, got {len(points)}"

    left_outer = sorted(points[:2], key=lambda pt: pt.position().y())
    left_mid = sorted(points[2:4], key=lambda pt: pt.position().y())
    center = sorted(points[4:6], key=lambda pt: pt.position().y())
    right_mid = sorted(points[6:8], key=lambda pt: pt.position().y())
    right_outer = sorted(points[8:], key=lambda pt: pt.position().y())

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
    socket_prims: list[hou.Prim] = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith(Region.CHELICERASOCKET)
    ]
    geo.deletePrims(socket_prims)


def _remove_left_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    left_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == Region.CHELICERAMEMBRANE
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
    params = get_params(parent, use_tuple=False)

    b0, u0, m6 = point_from_geo(
        geo,
        base_sops.basesternum(0),
        headchelicerae(0),
        cheliceraemembrane(6),
    )
    membrane_points = point_from_geo(
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

    pts = [geo.createPoint() for _ in range(4)]
    for j, (pt, start, offset) in enumerate(zip(pts, membrane_points, offsets), start=1):
        pt.setPosition(start.position() + offset)
        set_point_id(pt, cheliceraestart(j))

    fill_face(geo, pts, True)


def _inset_start_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    lower, upper = point_from_geo(
        geo,
        base_sops.basesternum(0),
        headchelicerae(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    start_points = point_from_geo(geo, *(cheliceraestart(j) for j in range(1, 5)))
    start_prim = next(prim for prim in start_points[0].prims() if all(pt in start_points for pt in prim.points()))
    _inset_and_recess([start_prim], dist, delete_inset_prims=True)

    for j, pt in enumerate(start_points, start=1):
        set_point_id(pt, cheliceraestartmembranesupport(j))


def _adjust_start_section_left(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    s1, s2, ss1, ss2 = point_from_geo(
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
    params = get_params(parent, use_tuple=False)
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

    c3_pts = [geo.createPoint() for _ in range(4)]
    for pt, pos in zip(c3_pts, c3_positions):
        pt.setPosition(pos)
    for j, pt in enumerate(c3_pts, start=1):
        set_point_id(pt, cheliceraeend(j))

    end_prim = fill_face(geo, c3_pts, True)
    add_prim_attr(geo, "region", "")
    end_prim.setAttribValue("region", Region.FANG)


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
    c1_1, c1_2, c1_3, c1_4 = point_from_geo(
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
    params = get_params(parent, use_tuple=False)
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
    _add_intermediate_section(node, 0.25, lambda *i: _middle_section(0.25, *i))


def _add_lower_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.75, lambda *i: _middle_section(0.75, *i))


def _add_intermediate_section(
    node: hou.SopNode,
    factor: float,
    id_factory: Callable[[int], str] | None,
) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    params = get_params(parent, use_tuple=False)
    end_section_ratio = params.end_section_ratio
    middle_section_offset = params.middle_section_offset
    middle_section_height_ratio = params.middle_section_height_ratio
    middle_section_ratio = params.middle_section_ratio

    start_section, end_pivot, _, end_surface_normal = _get_end_section_frame(geo, parent)
    offset_baseline = start_section.offset_baseline

    normal0 = start_section.along
    normal2 = -end_surface_normal

    middle_pivot = hou.Vector3(
        start_section.pivot.x() + offset_baseline.x() * middle_section_offset.x(),
        start_section.pivot.y() + (end_pivot.y() - start_section.pivot.y()) * middle_section_height_ratio,
        start_section.pivot.z() - offset_baseline.z() * middle_section_offset.y(),
    )

    evaluate = interpolate_elliptical(
        start_section.pivot,
        middle_pivot,
        end_pivot,
        normal0,
        normal2,
    )

    along_axis = (end_pivot - start_section.pivot).normalized()
    chord_length = (end_pivot - start_section.pivot).length()
    middle_t = (middle_pivot - start_section.pivot).dot(along_axis) / chord_length

    f_upper = min(factor * 2.0, 1.0)
    f_lower = max(factor * 2.0 - 1.0, 0.0)
    w_start = 1.0 - f_upper
    w_mid = f_upper - f_lower
    w_end = f_lower

    t = middle_t * w_mid + w_end

    pivot, direction = evaluate(t)
    normal = rotation_to(normal0, direction).rotate(start_section.normal)

    start_size = hou.Vector2(start_section.height, start_section.width)
    middle_size = hou.Vector2(
        start_section.height * middle_section_ratio.y(),
        start_section.width * middle_section_ratio.x(),
    )
    end_size = hou.Vector2(
        start_section.height * end_section_ratio.y(),
        start_section.width * end_section_ratio.x(),
    )

    size = start_size * w_start + middle_size * w_mid + end_size * w_end

    positions = _construct_section_loop(
        pivot,
        size,
        direction,
        normal,
    )

    for pos in positions:
        assert pos.x() >= 0.0, f"Section loop point at factor {factor} crossed symmetry plane (x={pos.x():.4f} < 0.0). Adjust parameters or ratio."

    pts = [geo.createPoint() for _ in range(4)]
    for pt, pos in zip(pts, positions):
        pt.setPosition(pos)
    if id_factory:
        for j, pt in enumerate(pts, start=1):
            set_point_id(pt, id_factory(j))

    fill_face(geo, pts, True)


def _connect_sections(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    def is_cap_face(prim: hou.Prim) -> bool:
        if prim.stringAttribValue("region") == Region.FANG:
            return False
        pt_ids = [pt.stringAttribValue("id") for pt in prim.points()]
        if not all(pid.startswith((cheliceraestart(), cheliceraemiddle(), "tmpsection")) for pid in pt_ids):
            return False
        prefixes = {pid.rstrip("0123456789-") for pid in pt_ids}
        return len(prefixes) == 1

    middle_prims = [prim for prim in geo.prims() if is_cap_face(prim)]
    geo.deletePrims(middle_prims, keep_points=True)

    # Connect socket membrane (4 corner points) to start membrane support (4 points)
    m1, m3, m4, m6 = point_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraemembrane(6),
    )
    ss1, ss2, ss3, ss4 = point_from_geo(
        geo,
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
    )
    s1, s2, s3, s4 = point_from_geo(
        geo,
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraestart(3),
        cheliceraestart(4),
    )

    # Medial face: (m1, m6, ss2, ss1)
    fill_face(geo, [m1, m6, ss2, ss1], True)
    # Top face: (m6, m4, ss3, ss2)
    fill_face(geo, [m6, m4, ss3, ss2], True)
    # Lateral face: (m4, m3, ss4, ss3)
    fill_face(geo, [m4, m3, ss4, ss3], True)
    # Bottom face: (m3, m1, ss1, ss4)
    fill_face(geo, [m3, m1, ss1, ss4], True)

    tube_loops = [
        (s1, s2, s3, s4),
        point_from_geo(geo, *(_middle_section(0.25, j) for j in range(1, 5))),
        point_from_geo(geo, *(cheliceraemiddle(j) for j in range(1, 5))),
        point_from_geo(geo, *(_middle_section(0.75, j) for j in range(1, 5))),
        point_from_geo(geo, *(cheliceraeend(j) for j in range(1, 5))),
    ]

    for i in range(len(tube_loops) - 1):
        current_loop = tube_loops[i]
        next_loop = tube_loops[i + 1]
        for j in range(4):
            next_j = (j + 1) % 4
            fill_face(
                geo,
                [
                    current_loop[j],
                    current_loop[next_j],
                    next_loop[next_j],
                    next_loop[j],
                ],
                True,
            )


def _remove_middle_face(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    membrane1, membrane6, support1, support2 = point_from_geo(
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
    s2, s3 = point_from_geo(
        geo,
        cheliceraestart(2),
        cheliceraestart(3),
    )
    top_edge = geo.findEdge(s2, s3)
    assert top_edge is not None, "Expected top edge between cheliceraestart(2) and cheliceraestart(3)"
    added_points, _ = loop_cut(top_edge.prims()[0], s2, s3, 0.5, use_ratio=True)
    cut_ids = [
        bottom_middle(cheliceraemembrane, 1),
        bottom_middle(cheliceraestartmembranesupport, 1),
        bottom_middle(cheliceraestart, 1),
        bottom_middle(_middle_section, 1, j=0.25),
        bottom_middle(cheliceraemiddle, 1),
        bottom_middle(_middle_section, 1, j=0.75),
        bottom_middle(cheliceraeend, 1),
        upper_middle(cheliceraeend, 1),
        upper_middle(_middle_section, 1, j=0.75),
        upper_middle(cheliceraemiddle, 1),
        upper_middle(_middle_section, 1, j=0.25),
        upper_middle(cheliceraestart, 1),
        upper_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraemembrane, 1),
    ]
    set_points_id(added_points, cut_ids)


def _add_start_membrane_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    membrane, support = point_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraestartmembranesupport(1),
    )
    _add_support_loop(geo, ratio, support, membrane)

def _add_start_section_support_loops(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")
    start, middle = point_from_geo(
        geo,
        cheliceraestart(2),
        _middle_section(0.25, 2),
    )
    _add_support_loop(geo, ratio, start, middle)


def _merge_membrane_curves(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m2, m5, top_cut, bottom_cut = point_from_geo(
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
    m2, m3, m4, m5, ss3, ss4, s3, s4 = point_from_geo(
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

    support_bottom_mid, support_upper_mid, start_bottom_mid, start_upper_mid = point_from_geo(
        geo,
        bottom_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraestartmembranesupport, 1),
        bottom_middle(cheliceraestart, 1),
        upper_middle(cheliceraestart, 1),
    )
    upper_offset = (m5.position() - support_upper_mid.position()).normalized() * (upper_width * 0.5)
    bottom_offset = (m2.position() - support_bottom_mid.position()).normalized() * (bottom_width * 0.5)

    support_upper_mid.setPosition(support_upper_mid.position() + upper_offset)
    start_upper_mid.setPosition(start_upper_mid.position() + upper_offset)
    support_bottom_mid.setPosition(support_bottom_mid.position() + bottom_offset)
    start_bottom_mid.setPosition(start_bottom_mid.position() + bottom_offset)


def _adjust_right_membrane_width(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    m3, m4, ss3, ss4, s3, s4 = point_from_geo(
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
    ss3.setPosition(ss3.position() + upper_offset)
    s3.setPosition(s3.position() + upper_offset)
    ss4.setPosition(ss4.position() + bottom_offset)
    s4.setPosition(s4.position() + bottom_offset)


def _inset_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    # Boundary vertices along the upper-medial edge (#2) of the chelicera tube
    medial_upper_points = point_from_geo(
        geo,
        cheliceraemembrane(6),
        cheliceraestartmembranesupport(2),
        cheliceraestart(2),
        _middle_section(0.25, 2),
        cheliceraemiddle(2),
        _middle_section(0.75, 2),
        cheliceraeend(2),
    )
    # Opposing vertices along the upper-middle loop cut (#uppermiddle_1)
    upper_middle_points = point_from_geo(
        geo,
        cheliceraemembrane(5),
        upper_middle(cheliceraestartmembranesupport, 1),
        upper_middle(cheliceraestart, 1),
        upper_middle(_middle_section, 1, j=0.25),
        upper_middle(cheliceraemiddle, 1),
        upper_middle(_middle_section, 1, j=0.75),
        upper_middle(cheliceraeend, 1),
    )
    # Boundary vertices along the upper-lateral edge (#3) of the chelicera tube
    lateral_upper_points = point_from_geo(
        geo,
        cheliceraemembrane(4),
        cheliceraestartmembranesupport(3),
        cheliceraestart(3),
        _middle_section(0.25, 3),
        cheliceraemiddle(3),
        _middle_section(0.75, 3),
        cheliceraeend(3),
    )

    # Inset distance evaluated from the start membrane gap (1/3 of gap)
    start_membrane_support, start_point = point_from_geo(
        geo,
        cheliceraestartmembranesupport(2),
        cheliceraestart(2),
    )
    start_membrane_gap = start_membrane_support.position().distanceTo(start_point.position())
    dist = start_membrane_gap / 3.0

    # Form the full upper quad strip (medial and lateral halves) from start membrane to end section
    left_prims = [
        find_prim(medial_upper_points[i], medial_upper_points[i + 1], upper_middle_points[i])
        for i in range(len(medial_upper_points) - 1)
    ]
    right_prims = [
        find_prim(lateral_upper_points[i], lateral_upper_points[i + 1], upper_middle_points[i])
        for i in range(len(lateral_upper_points) - 1)
    ]
    inset(left_prims + right_prims, dist, use_ratio=False)

    _adjust_chelicerae_support_loop(node)

    deduplicate_id_attr(geo, None, keep_first=True)


def _adjust_chelicerae_support_loop(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    # This method adjusts the points position so the topology becomes more natural and smooth at certain places
    by_id = points_by_attr(geo, "id", skip_blank=True)
    _adjust_right_chelicerae_support_points(by_id)
    _adjust_left_chelicerae_support_points(by_id)
    _adjust_bottom_chelicerae_support_points(by_id)

def _adjust_right_chelicerae_support_points(points_by_attr: dict[str, set[hou.Point]]) -> None:
    # For the right half support points, move them along 1/2 towards the upper middle line
    sections = (
        (cheliceraemembrane(4), cheliceraemembrane(5)),
        (cheliceraestartmembranesupport(3), upper_middle(cheliceraestartmembranesupport, 1)),
        (cheliceraestart(3), upper_middle(cheliceraestart, 1)),
        (_middle_section(0.25, 3), upper_middle(_middle_section, 1, j=0.25)),
        (cheliceraemiddle(3), upper_middle(cheliceraemiddle, 1)),
        (_middle_section(0.75, 3), upper_middle(_middle_section, 1, j=0.75)),
        (cheliceraeend(3), upper_middle(cheliceraeend, 1)),
    )
    for support_id, mid_id in sections:
        inset_support = _get_inset_chelicerae_support_point(points_by_attr, support_id)
        inset_mid = _get_inset_chelicerae_support_point(points_by_attr, mid_id)
        inset_support.setPosition((inset_support.position() + inset_mid.position()) * 0.5)

def _adjust_left_chelicerae_support_points(points_by_attr: dict[str, set[hou.Point]]) -> None:
    # For the left half support points, cheliceraemembrane(6), cheliceraestartmembranesupport(2),
    # and cheliceraestart(2) are kept at 0, tmpsection 0.25 is moved by 1/4, and the rest to 1/2
    sections = (
        (cheliceraemembrane(6), cheliceraemembrane(5), 0.0),
        (cheliceraestartmembranesupport(2), upper_middle(cheliceraestartmembranesupport, 1), 0.0),
        (cheliceraestart(2), upper_middle(cheliceraestart, 1), 0.0),
        (_middle_section(0.25, 2), upper_middle(_middle_section, 1, j=0.25), 0.25),
        (cheliceraemiddle(2), upper_middle(cheliceraemiddle, 1), 0.5),
        (_middle_section(0.75, 2), upper_middle(_middle_section, 1, j=0.75), 0.5),
        (cheliceraeend(2), upper_middle(cheliceraeend, 1), 0.5),
    )
    for support_id, mid_id, ratio in sections:
        if ratio == 0.0:
            continue
        inset_support = _get_inset_chelicerae_support_point(points_by_attr, support_id)
        inset_mid = _get_inset_chelicerae_support_point(points_by_attr, mid_id)
        inset_support.setPosition(inset_support.position() * (1.0 - ratio) + inset_mid.position() * ratio)

def _adjust_bottom_chelicerae_support_points(points_by_attr: dict[str, set[hou.Point]]) -> None:
    sections = (
        (cheliceraeend(2), _middle_section(0.75, 2)),
        (upper_middle(cheliceraeend, 1), upper_middle(_middle_section, 1, j=0.75)),
        (cheliceraeend(3), _middle_section(0.75, 3)),
    )
    for end_id, section_id in sections:
        inset_end = _get_inset_chelicerae_support_point(points_by_attr, end_id)
        inset_section = _get_inset_chelicerae_support_point(points_by_attr, section_id)
        inset_end.setPosition((inset_end.position() + inset_section.position()) * 0.5)

def _get_inset_chelicerae_support_point(points_by_attr: dict[str, set[hou.Point]], pt_id: str) -> hou.Point:
    matches = points_by_attr[pt_id]
    return max(matches, key=lambda pt: pt.number())


def _rename_left_ids(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry(), affix_index=-1)


def _inset_and_recess(
        prims: list[hou.Prim],
        dist: float,
        delete_inset_prims: bool = False,
) -> list[hou.Prim]:
    inner = inset(prims, dist, use_ratio=False)
    norm = inner[0].normal()
    inner_pts = list({pt.number(): pt for prim in inner for pt in prim.points()}.values())
    if delete_inset_prims:
        inner[0].geometry().deletePrims(inner, keep_points=True)

    # Move inset points along the face normal backwards by its width to create a seam
    for pt in inner_pts:
        pt.setPosition(pt.position() - norm * dist)
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
    added_points, _ = loop_cut(prim, start_point, end_point, ratio, use_ratio=True)
    return added_points