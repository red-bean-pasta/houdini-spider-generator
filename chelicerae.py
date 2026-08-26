from typing import Callable
from dataclasses import dataclass
from enum import StrEnum, auto

import hou

import base_sops
from utilities.common import (
    add_edge_group,
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_parent,
    get_vector2_parm,
    get_vector3_parm,
    remove_attrs,
    remove_groups, rotation_to, fill_face_reversed, add_heading, add_float_param,
)
from utilities.helper import (
    add_id_attr,
    affix_id,
    deduplicate_id_attr,
    points_by_id,
    set_point_id,
    rename_left_ids,
    set_points_id,
)
from utilities.identifying import attribute_after_inset
from utilities.nodes import (
    add_mirror,
    add_merge,
    add_fuse,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import interpolate_elliptical


class ID(StrEnum):
    CHELICERAEUPPER = auto()
    CHELICERAESTART = auto()
    CHELICERAEUPPERMIDDLE = auto()
    CHELICERAEMIDDLE = auto()
    CHELICERAELOWERMIDDLE = auto()
    CHELICERAEEND = auto()

def cheliceraeupper(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEUPPER, *i)

def cheliceraestart(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTART, *i)

def cheliceraeuppermiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEUPPERMIDDLE, *i)

def cheliceraemiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMIDDLE, *i)

def cheliceraelowermiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAELOWERMIDDLE, *i)

def cheliceraeend(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEEND, *i)


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    chelicerae = add_reloadable_subnet(cephalothorax, "chelicerae")
    chelicerae.setInput(0, base)
    _add_parameters(chelicerae)

    geometry = sopify(chelicerae, chelicerae.indirectInputs()[0], _build_geometry)
    regions = sopify(chelicerae, geometry, _identify_inset_split)
    inset = _inset_flaps(chelicerae, regions)
    classified = sopify(chelicerae, inset, _classify_after_inset)
    cleanup = sopify(chelicerae, classified, _cleanup_inset_flaps)
    prepared = sopify(chelicerae, cleanup, _prepare_extrusion)
    end_section = sopify(chelicerae, prepared, _add_end_section)
    middle_section = sopify(chelicerae, end_section, _add_middle_section)
    upper_middle_section = sopify(chelicerae, middle_section, _add_upper_middle_section)
    lower_middle_section = sopify(chelicerae, upper_middle_section, _add_lower_middle_section)
    connected = sopify(chelicerae, lower_middle_section, _connect_sections)
    extrusion = sopify(chelicerae, connected, _extract_extrusion)
    mirrored = add_mirror(chelicerae, "mirror_left_extrusion", extrusion, (1, 0, 0), True, False)
    renamed = sopify(chelicerae, mirrored, _rename_left_ids)
    merged = add_merge(chelicerae, "merge_base_and_extrusion", prepared, renamed)
    fused = add_fuse(chelicerae, "fuse_chelicerae", merged)

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
        (0.5, 0.5),
        (0.0, None),
        label="Ratio"
    )
    add_float_param(
        chelicerae,
        "end_section_offset",
        3,
        (0.25, 3.5, 0.5),
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
        (1.1, 1.2),
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

    source_points = points_by_id(geo)
    base_ids = (
        base_sops.basemaxilla(-1),
        base_sops.basesternum(-1, 1),
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
        base_sops.basemaxilla(1),
    )
    base_positions = [source_points[point_id].position() for point_id in base_ids]

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
    height = base_positions[-1].distanceTo(base_positions[2]) * height_ratio
    height_offset = hou.Vector3(0.0, height, 0.0)

    upper_points = []
    upper_ids = []
    for index, position in enumerate(base_positions):
        point_id = cheliceraeupper(index - 2)
        point = geo.createPoint()
        point.setPosition(position + height_offset)
        upper_points.append(point)
        upper_ids.append(point_id)
    set_points_id(upper_points, upper_ids)

    middle_index = base_ids.index(base_sops.basesternum(0))
    face_indices = (
        list(range(middle_index, len(base_points) - 1))
        + list(range(middle_index - 1, -1, -1))
    )
    for index in face_indices:
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


def _identify_inset_split(node: hou.SopNode) -> None:
    geo = node.geometry()
    add_prim_attr(geo, "tmp_insetscale", 0.0)

    points = points_by_id(geo)
    lower_id = base_sops.basesternum(0)
    upper_id = cheliceraeupper(0)
    lower = points.get(lower_id)
    upper = points.get(upper_id)
    assert lower is not None and upper is not None, f"Expected chelicerae points {lower_id!r} and {upper_id!r}"

    inset_scale = lower.position().distanceTo(upper.position())
    for primitive in geo.prims():
        primitive.setAttribValue("tmp_insetscale", inset_scale)

    edge = geo.findEdge(lower, upper)
    assert edge is not None, f"Expected chelicerae edge {lower_id!r}-{upper_id!r}"
    edge_group = add_edge_group(geo, "tmp_chelicera_split")
    edge_group.add(edge)


def _inset_flaps(parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    inset = parent.createNode("polyextrude", "inset_membrane")
    inset.setInput(0, p_input)
    inset.parm("group").set("@region=chelicera")
    inset.parm("splittype").set(1)
    inset.parm("usesplitgroup").set(1)
    inset.parm("splitgroup").set("tmp_chelicera_split")
    inset.parm("inset").setExpression('ch("../membrane_ratio")')
    inset.parm("uselocalinsetscaleattrib").set(1)
    inset.parm("localinsetscaleattrib").set("tmp_insetscale")
    return inset


def _classify_after_inset(node: hou.SopNode) -> None:
    panes, _ = attribute_after_inset(node, "region", "chelicerasocket", "cheliceramembrane", 2)
    assert len(panes) == 2

    pts_dict = {}
    for pane in (panes[0], panes[1]):
        for prim in pane:
            for pt in prim.points():
                pts_dict[pt.number()] = pt
    points = list(pts_dict.values())
    points.sort(key=lambda pt: (pt.position().x(), pt.position().y()))

    target_ids = (
        cheliceraestart(-4),
        cheliceraestart(-3),
        "cheliceramiddlelower-1",
        "cheliceramiddleupper-1",
        cheliceraestart(-1),
        cheliceraestart(-2),
        cheliceraestart(1),
        cheliceraestart(2),
        "cheliceramiddlelower1",
        "cheliceramiddleupper1",
        cheliceraestart(4),
        cheliceraestart(3),
    )
    set_points_id(points, list(target_ids))


def _cleanup_inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    remove_attrs(geo, prim_attribs="tmp_insetscale")
    remove_groups(geo, edge_groups="tmp_chelicera_split")
    deduplicate_id_attr(geo, None, add_affix=False)


def _prepare_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims: list[hou.Prim] = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith("chelicerasocket")
    ]
    geo.deletePrims(socket_prims)


def _add_end_section(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    end_section_offset = get_vector3_parm(parent, "end_section_offset")
    end_section_rotation = get_vector2_parm(parent, "end_section_rotation")
    end_section_ratio = get_vector2_parm(parent, "end_section_ratio")

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

    c3_pts = [geo.createPoint() for _ in range(4)]
    for pt, pos in zip(c3_pts, c3_positions):
        pt.setPosition(pos)
    for j, pt in enumerate(c3_pts, start=1):
        set_point_id(pt, cheliceraeend(j))

    end_prim = fill_face_reversed(geo, c3_pts)
    add_prim_attr(geo, "region", "")
    end_prim.setAttribValue("region", "fang")


def _add_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, "upper", 1.0, cheliceraemiddle)


def _add_upper_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, "upper", 0.5, cheliceraeuppermiddle)


def _add_lower_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, "lower", 0.5, cheliceraelowermiddle)


def _connect_sections(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    middle_prims = [
        prim for prim in geo.prims()
        if any(pt.stringAttribValue("id").startswith((ID.CHELICERAEMIDDLE, ID.CHELICERAEUPPERMIDDLE, ID.CHELICERAELOWERMIDDLE)) for pt in prim.points())
        and prim.stringAttribValue("region") != "fang"
    ]
    geo.deletePrims(middle_prims, keep_points=True)

    id_points = points_by_id(geo)
    loops = [
        [id_points[cheliceraestart(j)] for j in range(1, 5)],
        [id_points[cheliceraeuppermiddle(j)] for j in range(1, 5)],
        [id_points[cheliceraemiddle(j)] for j in range(1, 5)],
        [id_points[cheliceraelowermiddle(j)] for j in range(1, 5)],
        [id_points[cheliceraeend(j)] for j in range(1, 5)],
    ]

    for i in range(len(loops) - 1):
        current_loop = loops[i]
        next_loop = loops[i + 1]
        for j in range(4):
            next_j = (j + 1) % 4
            fill_face_reversed(geo, [
                current_loop[j],
                current_loop[next_j],
                next_loop[next_j],
                next_loop[j],
            ])


def _extract_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    membrane_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith("cheliceramembrane")
    ]
    geo.deletePrims(membrane_prims)


def _rename_left_ids(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry())


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
    id_points = points_by_id(geo)
    c1_1 = id_points[cheliceraestart(1)]
    c1_2 = id_points[cheliceraestart(2)]
    c1_3 = id_points[cheliceraestart(3)]
    c1_4 = id_points[cheliceraestart(4)]

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
    segment: str,
    factor: float,
    id_factory: Callable[[int], str],
) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    end_section_offset = get_vector3_parm(parent, "end_section_offset")
    end_section_rotation = get_vector2_parm(parent, "end_section_rotation")
    end_section_ratio = get_vector2_parm(parent, "end_section_ratio")
    middle_section_offset = get_vector2_parm(parent, "middle_section_offset")
    middle_section_height_ratio = get_float_parm(parent, "middle_section_height_ratio")
    middle_section_ratio = get_vector2_parm(parent, "middle_section_ratio")

    start_section = _get_start_section_frame(geo)
    offset_baseline = start_section.offset_baseline

    end_pivot_offset = hou.Vector3(end_section_offset.x(), -end_section_offset.y(), -end_section_offset.z())
    end_pivot = start_section.pivot + hou.Vector3(
        offset_baseline.x() * end_pivot_offset.x(),
        offset_baseline.y() * end_pivot_offset.y(),
        offset_baseline.z() * end_pivot_offset.z(),
    )

    middle_pivot = hou.Vector3(
        start_section.pivot.x() + offset_baseline.x() * middle_section_offset.x(),
        start_section.pivot.y() + (end_pivot.y() - start_section.pivot.y()) * middle_section_height_ratio,
        start_section.pivot.z() - offset_baseline.z() * middle_section_offset.y(),
    )

    end_rot_matrix = hou.hmath.buildRotate(end_section_rotation.x(), 0.0, end_section_rotation.y())
    end_surface_normal = start_section.normal * end_rot_matrix
    normal0 = start_section.along
    normal2 = -end_surface_normal

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

    if segment == "upper":
        t = middle_t * factor
    else:
        t = middle_t + (1.0 - middle_t) * factor

    pivot, direction = evaluate(t)
    normal = rotation_to(normal0, direction).rotate(start_section.normal)

    start_size = hou.Vector2(start_section.height, start_section.width)
    middle_size = hou.Vector2(start_section.height * middle_section_ratio.y(), start_section.width * middle_section_ratio.x())
    end_size = hou.Vector2(start_section.height * end_section_ratio.y(), start_section.width * end_section_ratio.x())

    if segment == "upper":
        size = start_size * (1.0 - factor) + middle_size * factor
    else:
        size = middle_size * (1.0 - factor) + end_size * factor

    positions = _construct_section_loop(
        pivot,
        size,
        direction,
        normal,
    )

    pts = [geo.createPoint() for _ in range(4)]
    for pt, pos in zip(pts, positions):
        pt.setPosition(pos)
    for j, pt in enumerate(pts, start=1):
        set_point_id(pt, id_factory(j))

    fill_face_reversed(geo, pts)