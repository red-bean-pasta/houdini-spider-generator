from typing import Callable
from functools import partial
from dataclasses import dataclass
from enum import StrEnum, auto

import hou

import base_sops
from utilities.common import (
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_params,
    get_parent,
    rotation_to,
    add_heading,
    add_float_param,
)
from helper import (
    add_id_attr,
    affix_id,
    deduplicate_id_attr,
    point_from_geo,
    points_by_id,
    rename_left_ids,
    set_point_id,
    set_points_id,
)
from utilities.nodes import (
    add_mirror,
    add_fuse,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import fill_pentagon, inset, interpolate_elliptical


class ID(StrEnum):
    CHELICERAEMEMBRANEUPPER = auto()
    CHELICERAESTART = auto()
    CHELICERAEMIDDLE = auto()
    CHELICERAEEND = auto()

def cheliceraemembraneupper(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMEMBRANEUPPER, *i)
def cheliceraestart(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTART, *i)
def cheliceraemiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMIDDLE, *i)
def cheliceraeend(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEEND, *i)

def _middle_section(ratio: float, *i: int | str) -> str:
    return affix_id("tmpsection", ratio, *i)
def _support_section(*i: int | str) -> str:
    return affix_id("tmpsection", "support", *i)

def _tmp_membrane_inner_upper(*i: int | str) -> str:
    return affix_id("tmpmembraneinnerupper", *i)
def _tmp_membrane_inner_lower(*i: int | str) -> str:
    return affix_id("tmpmembraneinnerlower", *i)
def _retopo(*i: int | str) -> str:
    return affix_id("tmpretopo", *i)
def _retopo_float(*i: int | str) -> str:
    return _retopo("float", *i)
def _retopo_back(*i: int | str) -> str:
    return _retopo_float("back", *i)
def _retopo_side(*i: int | str) -> str:
    return _retopo_float("side", *i)


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    chelicerae = add_reloadable_subnet(cephalothorax, "chelicerae")
    chelicerae.setInput(0, base)
    _add_parameters(chelicerae)

    geometry = sopify(chelicerae, chelicerae.indirectInputs()[0], _build_geometry)
    inset_node = sopify(chelicerae, geometry, _inset_flaps)
    classified = sopify(chelicerae, inset_node, _classify_after_inset)
    prepared = sopify(chelicerae, classified, _prepare_extrusion)
    retopology_upper_membrane = sopify(chelicerae, prepared, _retopology_upper_membrane)
    start_support = sopify(chelicerae, retopology_upper_membrane, _add_start_support_section)
    end_section = sopify(chelicerae, start_support, _add_end_section)
    middle_section = sopify(chelicerae, end_section, _add_middle_section)
    upper_section = sopify(chelicerae, middle_section, _add_upper_section)
    upper_middle_section = sopify(chelicerae, upper_section, _add_upper_middle_section)
    lower_middle_section = sopify(chelicerae, upper_middle_section, _add_lower_middle_section)
    connect_support = sopify(chelicerae, lower_middle_section, _connect_support_section)
    retopo_middle = sopify(chelicerae, connect_support, _retopo_middle_membrane)
    connected = sopify(chelicerae, retopo_middle, _connect_sections)
    mirrored = add_mirror(chelicerae, "mirror_left_chelicerae", connected, (1, 0, 0), True, False)
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
        "Start Section",
    )
    add_float_param(
        chelicerae,
        "start_section_height_ratio",
        1,
        0.35,
        (0.0, None),
        label="Height Ratio"
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
        label="Ratio"
    )
    add_float_param(
        chelicerae,
        "end_section_offset",
        3,
        (0.2, 3.5, 0.5),
        label="Offset"
    )
    add_float_param(
        chelicerae,
        "end_section_rotation",
        2,
        (-90.0, 0.0),
        label="Rotation"
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
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
        base_sops.basemaxilla(1),
    )
    source_points = point_from_geo(geo, *base_ids)
    base_positions = [point.position() for point in source_points]

    geo.clear()
    add_id_attr(geo)
    add_prim_attr(geo, "region", "")
    base_points = []
    for point_id, position in zip(base_ids, base_positions):
        point = geo.createPoint()
        point.setPosition(position)
        base_points.append(point)
    set_points_id(base_points, list(base_ids))

    height_ratio = get_float_parm(get_parent(node), "start_section_height_ratio")
    height = base_positions[-1].distanceTo(base_positions[0]) * height_ratio
    height_offset = hou.Vector3(0.0, height, 0.0)

    upper_points = []
    upper_ids = []
    for index, position in enumerate(base_positions):
        point_id = cheliceraemembraneupper(index)
        point = geo.createPoint()
        point.setPosition(position + height_offset)
        upper_points.append(point)
        upper_ids.append(point_id)
    set_points_id(upper_points, upper_ids)

    for index in range(len(base_points) - 1):
        primitive = fill_face(
            geo,
            [
                base_points[index],
                base_points[index + 1],
                upper_points[index + 1],
                upper_points[index],
            ],
        )
        primitive.setAttribValue("region", "chelicera")


def _inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    ratio = get_float_parm(get_parent(node), "membrane_ratio")

    lower, upper = point_from_geo(
        geo,
        base_sops.basesternum(0),
        cheliceraemembraneupper(0),
    )
    dist = ratio * lower.position().distanceTo(upper.position())

    inner = inset(list(geo.prims()), dist, use_ratio=False)
    for prim in inner:
        prim.setAttribValue("region", "chelicerasocket")

    for prim in geo.prims():
        if prim.stringAttribValue("region") != "chelicerasocket":
            prim.setAttribValue("region", "cheliceramembrane")


def _classify_after_inset(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == "chelicerasocket"
    ]
    pts_dict = {}
    for prim in socket_prims:
        for pt in prim.points():
            pts_dict[pt.number()] = pt
    points = list(pts_dict.values())
    points.sort(key=lambda pt: (round(pt.position().x(), 2), pt.position().y()))

    target_ids = (
        cheliceraestart(1),
        cheliceraestart(2),
        _tmp_membrane_inner_lower(1),
        _tmp_membrane_inner_upper(1),
        cheliceraestart(4),
        cheliceraestart(3),
    )
    set_points_id(points, list(target_ids))
    deduplicate_id_attr(geo, None, add_affix=False)


def _prepare_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims: list[hou.Prim] = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith("chelicerasocket")
    ]
    geo.deletePrims(socket_prims)


def _retopology_upper_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    id_points = points_by_id(geo)

    target_pt_ids = [
        cheliceraemembraneupper(1),
        _tmp_membrane_inner_upper(1),
    ]
    to_del_pts = [id_points[name] for name in target_pt_ids if name in id_points]
    to_del_prims = [p for p in geo.prims() if any(pt in to_del_pts for pt in p.points())]
    geo.deletePrims(to_del_prims, keep_points=True)
    geo.deletePoints(to_del_pts)

    (upper2,) = point_from_geo(geo, cheliceraemembraneupper(2))
    set_point_id(upper2, cheliceraemembraneupper(1))

    upper0, upper1, start3, start2 = point_from_geo(
        geo,
        cheliceraemembraneupper(0),
        cheliceraemembraneupper(1),
        cheliceraestart(3),
        cheliceraestart(2),
    )
    f1 = fill_face(geo, [upper0, upper1, start3, start2], True)
    f1.setAttribValue("region", "cheliceramembrane")


def _add_start_support_section(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    upper1, start2, start1, start3, start4 = point_from_geo(
        geo,
        cheliceraemembraneupper(1),
        cheliceraestart(2),
        cheliceraestart(1),
        cheliceraestart(3),
        cheliceraestart(4),
    )
    dist = upper1.position().y() - start2.position().y()
    pts = [geo.createPoint() for _ in range(4)]
    for j, (pt, start) in enumerate(zip(pts, (start1, start2, start3, start4)), start=1):
        start_pos = start.position()
        pt.setPosition(start_pos + hou.Vector3(0.0, 0.0, -dist))
        set_point_id(pt, _support_section(j))

    fill_face(geo, pts, True)


def _add_end_section(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    params = get_params(parent, use_tuple=False)
    end_section_offset = params.end_section_offset
    end_section_rotation = params.end_section_rotation
    end_section_ratio = params.end_section_ratio

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
    end_prim.setAttribValue("region", "fang")


def _add_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.5, cheliceraemiddle)


def _add_upper_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.1, partial(_middle_section, 0.1))


def _add_upper_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.25, partial(_middle_section, 0.25))


def _add_lower_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.75, partial(_middle_section, 0.75))


def _connect_support_section(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    st1, st2, st3, st4, sup1, sup2, sup3, sup4, mem1 = point_from_geo(
        geo,
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraestart(3),
        cheliceraestart(4),
        _support_section(1),
        _support_section(2),
        _support_section(3),
        _support_section(4),
        _tmp_membrane_inner_lower(1),
    )

    fill_face(geo, [st2, st3, sup3, sup2], True)
    fill_face(geo, [st3, st4, sup4, sup3], True)

    mid_edge, float_back = fill_pentagon(geo, [sup4, sup1, st1, mem1, st4], (sup1, st1), reverse=True)
    mid_start, float_side = fill_pentagon(geo, [sup2, sup1, mid_edge, st1, st2], (st1, st2), reverse=False)

    set_point_id(mid_edge, _retopo(1))
    set_point_id(float_back, _retopo_back(1))
    set_point_id(mid_start, _retopo(2))
    set_point_id(float_side, _retopo_side(1))


def _retopo_middle_membrane(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    basesternum_0, cheliceraestart_1, cheliceraestart_2, cheliceraemembraneupper_0 = point_from_geo(
        geo,
        base_sops.basesternum(0),
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraemembraneupper(0),
    )

    # Query midpoint on socket edge (cheliceraestart1 - cheliceraestart2) by position
    target_position = (cheliceraestart_1.position() + cheliceraestart_2.position()) * 0.5
    midpoint_socket = None
    for point in geo.points():
        if (point.position() - target_position).length() < 1e-4:
            midpoint_socket = point
            break
    assert midpoint_socket is not None, "Socket midpoint on cheliceraestart(1)-cheliceraestart(2) not found"

    # Delete original middle membrane primitive
    middle_primitives = [
        prim for prim in geo.prims()
        if basesternum_0 in prim.points() and cheliceraemembraneupper_0 in prim.points()
    ]
    assert len(middle_primitives) == 1, f"Expected 1 middle membrane primitive, found {len(middle_primitives)}"
    geo.deletePrims(middle_primitives, keep_points=True)

    # Add midpoint along the symmetry seam (basesternum0 - cheliceraemembraneupper0)
    midpoint_seam = geo.createPoint()
    midpoint_seam.setPosition((basesternum_0.position() + cheliceraemembraneupper_0.position()) * 0.5)
    set_point_id(midpoint_seam, _retopo(0))

    # Connect the two quads with region attribute
    quad_lower = fill_face(geo, [basesternum_0, cheliceraestart_1, midpoint_socket, midpoint_seam])
    quad_upper = fill_face(geo, [midpoint_seam, midpoint_socket, cheliceraestart_2, cheliceraemembraneupper_0])

    add_prim_attr(geo, "region", "")
    quad_lower.setAttribValue("region", "cheliceramembrane")
    quad_upper.setAttribValue("region", "cheliceramembrane")


def _connect_sections(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    def is_cap_face(prim: hou.Prim) -> bool:
        if prim.stringAttribValue("region") == "fang":
            return False
        pt_ids = [pt.stringAttribValue("id") for pt in prim.points()]
        if not all(pid.startswith((cheliceraemiddle(), "tmpsection")) for pid in pt_ids):
            return False
        prefixes = {pid.rstrip("0123456789-") for pid in pt_ids}
        return len(prefixes) == 1

    middle_prims = [prim for prim in geo.prims() if is_cap_face(prim)]
    geo.deletePrims(middle_prims, keep_points=True)

    loops = [
        point_from_geo(geo, *(_support_section(j) for j in range(1, 5))),
        point_from_geo(geo, *(_middle_section(0.1, j) for j in range(1, 5))),
        point_from_geo(geo, *(_middle_section(0.25, j) for j in range(1, 5))),
        point_from_geo(geo, *(cheliceraemiddle(j) for j in range(1, 5))),
        point_from_geo(geo, *(_middle_section(0.75, j) for j in range(1, 5))),
        point_from_geo(geo, *(cheliceraeend(j) for j in range(1, 5))),
    ]

    for i in range(len(loops) - 1):
        current_loop = loops[i]
        next_loop = loops[i + 1]
        for j in range(4):
            next_j = (j + 1) % 4
            fill_face(geo, [
                current_loop[j],
                current_loop[next_j],
                next_loop[next_j],
                next_loop[j],
            ], True)


def _rename_left_ids(node: hou.SopNode) -> None:
    geo = node.geometry()
    rename_left_ids(geo, affix_index=0)
    for pt in geo.points():
        if pt.position().x() < 0.0:
            pid = pt.stringAttribValue("id")
            if pid and not any(pid.endswith(f"-{d}") for d in range(1, 5)):
                for d in ("1", "2", "3", "4"):
                    if pid.endswith(d):
                        set_point_id(pt, pid[:-1] + f"-{d}")
                        break


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

    x_min, x_max = c1_1.position().x(), c1_4.position().x()
    y_min, y_max = c1_1.position().y(), c1_2.position().y()
    z = c1_1.position().z()
    w = x_max - x_min
    h = y_max - y_min

    pivot = hou.Vector3((x_max + x_min) / 2.0, (y_max + y_min) / 2.0, z)
    along = (c1_1.position() - c1_2.position()).normalized()
    normal = (c1_2.position() - c1_1.position()).cross(c1_4.position() - c1_1.position()).normalized()
    return Section(
        pivot,
        (c1_1, c1_2, c1_3, c1_4),
        along,
        normal,
        w,
        h
    )

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
        ( half_h,  half_w),
        (-half_h,  half_w),
        (-half_h, -half_w),
        ( half_h, -half_w),
    )
    return [
        pivot + along * ah + side * sw
        for ah, sw in corners
    ]


def _add_intermediate_section(
    node: hou.SopNode,
    factor: float,
    id_factory: Callable[[int], str] | None,
) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    params = get_params(parent, use_tuple=False)
    end_section_offset = params.end_section_offset
    end_section_rotation = params.end_section_rotation
    end_section_ratio = params.end_section_ratio
    middle_section_offset = params.middle_section_offset
    middle_section_height_ratio = params.middle_section_height_ratio
    middle_section_ratio = params.middle_section_ratio

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
    normal0 = start_section.along
    normal2 = -end_surface_normal

    evaluate = interpolate_elliptical(
        start_section.pivot,
        middle_pivot := hou.Vector3(
            start_section.pivot.x() + offset_baseline.x() * middle_section_offset.x(),
            start_section.pivot.y() + (end_pivot.y() - start_section.pivot.y()) * middle_section_height_ratio,
            start_section.pivot.z() - offset_baseline.z() * middle_section_offset.y(),
        ),
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
    middle_size = hou.Vector2(start_section.height * middle_section_ratio.y(), start_section.width * middle_section_ratio.x())
    end_size = hou.Vector2(start_section.height * end_section_ratio.y(), start_section.width * end_section_ratio.x())

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
