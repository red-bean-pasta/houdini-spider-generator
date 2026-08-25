import math
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
    remove_groups, get_prim_normal, rotation_to,
)
from utilities.helper import (
    add_id_attr,
    affix_id,
    deduplicate_id_attr,
    points_by_id,
    set_point_id,
    set_points_id,
)
from utilities.identifying import attribute_after_inset
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import interpolate_conic


class ID(StrEnum):
    CHELICERAEUPPER = auto()
    CHELICERAESTART = auto()
    CHELICERAEMIDDLE = auto()
    CHELICERAEEND = auto()

def cheliceraeupper(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEUPPER, *i)

def cheliceraestart(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTART, *i)

def cheliceraemiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMIDDLE, *i)

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
    extrusion = sopify(chelicerae, cleanup, _build_extrusion)

    add_output(chelicerae, "OUT_CHELICERAE", extrusion)
    chelicerae.layoutChildren()
    return chelicerae


def _add_parameters(chelicerae: hou.SopNode) -> None:
    templates = chelicerae.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "socket_height_ratio",
            "Socket Height Ratio",
            1,
            default_value=(0.35,),
            min=0.0,
            min_is_strict=True,
            help="Relative to the chelicerae region width",
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "membrane_ratio",
            "Membrane Ratio",
            1,
            default_value=(0.035,),
            min=0.0,
            min_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "end_section_offset",
            "End Section Offset",
            3,
            default_value=(0.25, 3.5, 0.5),
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "end_section_rotation",
            "End Section Rotation",
            2,
            default_value=(-90.0, 0.0),
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "middle_section_offset",
            "Middle Section Offset",
            3,
            default_value=(0.1, 1.3, 1.0),
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "middle_section_ratio",
            "Middle Section Ratio",
            2,
            default_value=(1.1, 1.2),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "end_section_ratio",
            "End Section Ratio",
            2,
            default_value=(0.5, 0.5),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    chelicerae.setParmTemplateGroup(templates)


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

    height_ratio = get_float_parm(get_parent(node), "socket_height_ratio")
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


def _build_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    parent = get_parent(node)
    end_section_offset = get_vector3_parm(parent, "end_section_offset")
    end_section_rotation = get_vector2_parm(parent, "end_section_rotation")
    end_section_ratio = get_vector2_parm(parent, "end_section_ratio")
    middle_section_offset = get_vector3_parm(parent, "middle_section_offset")
    middle_section_ratio = get_vector2_parm(parent, "middle_section_ratio")

    socket_prims: list[hou.Prim] = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith("chelicerasocket")
    ]; assert len(socket_prims) == 4
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

    up_pivot = hou.Vector3((x_max + x_min) / 2.0, (y_max + y_min) / 2.0, z)
    offset_baseline = hou.Vector3(w, h, h)

    end_pivot_offset = hou.Vector3(end_section_offset.x(), -end_section_offset.y(), -end_section_offset.z())
    end_pivot = up_pivot + hou.Vector3(
        offset_baseline.x() * end_pivot_offset.x(),
        offset_baseline.y() * end_pivot_offset.y(),
        offset_baseline.z() * end_pivot_offset.z(),
    )

    middle_pivot_offset = hou.Vector3(middle_section_offset.x(), -middle_section_offset.y(), -middle_section_offset.z())
    middle_pivot = up_pivot + hou.Vector3(
        offset_baseline.x() * middle_pivot_offset.x(),
        offset_baseline.y() * middle_pivot_offset.y(),
        offset_baseline.z() * middle_pivot_offset.z(),
    )

    start_face_along = (c1_4.position() - c1_1.position()).normalized()
    start_face_normal = get_prim_normal(socket_prims[0])
    end_rot_matrix = hou.hmath.buildRotate(end_section_rotation.x(), 0.0, end_section_rotation.y())
    end_surface_normal = start_face_normal * end_rot_matrix
    conic_normal0 = -start_face_along # Normal0 is not the face normal
    conic_normal1 = -end_surface_normal
    middle_section_dir = _interpolate_middle_section_direction(
        up_pivot,
        end_pivot,
        middle_pivot,
        conic_normal0,
        conic_normal1,
    )
    middle_section_normal = rotation_to(conic_normal0, middle_section_dir).rotate(start_face_normal)

    c2_positions = _construct_section_loop(
        middle_pivot,
        hou.Vector2(h * middle_section_ratio.y(), w * middle_section_ratio.x()),
        middle_section_dir,
        middle_section_normal,
    )
    c3_positions = _construct_section_loop(
        end_pivot,
        hou.Vector2(h * end_section_ratio.y(), w * end_section_ratio.x()),
        start_face_along * end_rot_matrix,
        end_surface_normal,
    )

    loops = [
        [c1_1, c1_2, c1_3, c1_4],
        [geo.createPoint() for _ in range(4)],
        [geo.createPoint() for _ in range(4)],
    ]
    for pts, positions in zip(loops[1:], (c2_positions, c3_positions)):
        for pt, pos in zip(pts, positions):
            pt.setPosition(pos)
    for j, point in enumerate(loops[1], start=1):
        set_point_id(point, cheliceraemiddle(j))
    for j, point in enumerate(loops[2], start=1):
        set_point_id(point, cheliceraeend(j))

    # for i in range(len(loops) - 1):
    #     current_loop = loops[i]
    #     next_loop = loops[i + 1]
    #     for j in range(4):
    #         next_j = (j + 1) % 4
    #         fill_face(geo, [
    #             current_loop[j],
    #             current_loop[next_j],
    #             next_loop[next_j],
    #             next_loop[j],
    #         ])
    fill_face(geo, loops[-2])
    fill_face(geo, loops[-1])

    geo.deletePrims(socket_prims)

def _construct_section_loop(
    pivot: hou.Vector3,
    size: hou.Vector2,
    along: hou.Vector3,
    normal: hou.Vector3,
) -> list[hou.Vector3]:
    """

    :param pivot:
    :param size:
    :param along: For the x-axis in size
    :param normal:
    :return:
    """
    normal = normal.normalized()
    along = along.normalized()
    along = (along - normal * along.dot(normal)).normalized()
    side = normal.cross(along).normalized()

    half_w, half_h = size.x() / 2.0, size.y() / 2.0
    corners = (
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    )
    return [
        pivot + along * x + side * y
        for x, y in corners
    ]

def _interpolate_middle_section_direction(
    up_pivot: hou.Vector3,
    end_pivot: hou.Vector3,
    middle_pivot: hou.Vector3,
    normal0: hou.Vector3,
    normal1: hou.Vector3,
) -> hou.Vector3:
    evaluate = interpolate_conic(up_pivot, end_pivot, middle_pivot, normal0, normal1)
    along_axis = (end_pivot - up_pivot).normalized()
    along = (middle_pivot - up_pivot).dot(along_axis)
    results = evaluate(along)
    assert len(results) > 0, "Failed to evaluate intermediate point on conic"
    _, normal = min(results, key=lambda pair: pair[0].distanceTo(middle_pivot))
    return normal
