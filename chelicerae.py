from enum import StrEnum, auto

import hou

import base_sops
import hom_helper
from hom_helper import (
    add_point_attr,
    add_new_prim_attr,
    affix_id,
    fill_face,
    get_float_parm,
    get_parent,
    points_by_attribute,
    set_point_id,
    set_points_id,
    sopify,
    add_edge_group,
)
from sop_helper import add_output


class ID(StrEnum):
    CHELICERAEUPPER = auto()

def cheliceraeupper(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEUPPER, *i)


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    chelicerae = cephalothorax.createNode("subnet", "chelicerae")
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
            "middle_section_offset",
            "Middle Section Offset",
            2,
            default_value=(0.1, 1.0),
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "middle_section_rotation",
            "Middle Section Rotation",
            2,
            default_value=(-90.0, 0.0),
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
    templates.append(
        hou.FloatParmTemplate(
            "end_section_offset",
            "End Section Offset",
            2,
            default_value=(0.25, 0.5),
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
            "section_offsets_y",
            "Section Offsets Y",
            2,
            default_value=(1.3, 3.5),
            naming_scheme=hou.parmNamingScheme.XYZW,
            help="Relative to the socket height",
        )
    )
    chelicerae.setParmTemplateGroup(templates)


def _build_geometry(node: hou.SopNode) -> None:
    geo = node.geometry()

    source_points = points_by_attribute(geo)
    base_ids = (
        base_sops.basemaxilla(-1),
        base_sops.basesternum(-1, 1),
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
        base_sops.basemaxilla(1),
    )
    base_positions = [source_points[point_id].position() for point_id in base_ids]

    geo.clear()
    add_point_attr(geo)
    add_new_prim_attr(geo, "region", "")
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
    add_new_prim_attr(geo, "tmp_insetscale", 0.0)

    points = points_by_attribute(geo)
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
    panes, _ = hom_helper.attribute_after_inset(node, "region", "chelicerasocket", "cheliceramembrane", 2)
    assert len(panes) == 2
    assert len(panes[0]) == 2
    assert panes[0][0].boundingBox().center().x() > 0

    right1, right2 = panes[0]
    left1, left2 = panes[1]
    right1_points = right1.points()
    right2_points = right2.points()
    left1_points = left1.points()
    left2_points = left2.points()

    # Right side (affix = 1)
    right_corners = (right1_points[0], right2_points[1], right2_points[2], right1_points[3])
    for subfix, pt in enumerate(right_corners, start=1):
        pt.setAttribValue("id", f"chelicera1_{subfix}")
    right1_points[1].setAttribValue("id", "cheliceramiddlelower1")
    right1_points[2].setAttribValue("id", "cheliceramiddleupper1")

    # Left side (affix = -1)
    left_corners = (left1_points[1], left2_points[0], left2_points[3], left1_points[2])
    for subfix, pt in enumerate(left_corners, start=1):
        pt.setAttribValue("id", f"chelicera-1_{subfix}")
    left1_points[0].setAttribValue("id", "cheliceramiddlelower-1")
    left1_points[3].setAttribValue("id", "cheliceramiddleupper-1")


def _cleanup_inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    hom_helper.remove_attributes(geo, prim_attribs="tmp_insetscale")
    hom_helper.remove_groups(geo, edge_groups="tmp_chelicera_split")
    hom_helper.deduplicate_points(geo, None, "id", False)


def _build_extrusion(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    socket_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith("chelicerasocket")
    ]

    id_points = points_by_attribute(geo)
    c1_1 = id_points["chelicera1_1"]
    c1_2 = id_points["chelicera1_2"]
    c1_3 = id_points["chelicera1_3"]
    c1_4 = id_points["chelicera1_4"]

    x_min, x_max = c1_1.position().x(), c1_2.position().x()
    y_min, y_max = c1_1.position().y(), c1_4.position().y()
    z = c1_1.position().z()
    w = x_max - x_min
    h = y_max - y_min

    up_pivot = hou.Vector3((x_max + x_min) / 2.0, (y_max + y_min) / 2.0, z)
    offset_baseline = hou.Vector3(w, h, h)

    middle_section_ratio = _get_vector2_parm(parent, "middle_section_ratio")
    middle_section_offset = _get_vector2_parm(parent, "middle_section_offset")
    middle_section_rotation = _get_vector2_parm(parent, "middle_section_rotation")
    end_section_ratio = _get_vector2_parm(parent, "end_section_ratio")
    end_section_offset = _get_vector2_parm(parent, "end_section_offset")
    end_section_rotation = _get_vector2_parm(parent, "end_section_rotation")
    section_offsets_y = _get_vector2_parm(parent, "section_offsets_y")

    middle_pivot_offset = hou.Vector3(middle_section_offset.x(), -section_offsets_y.x(), -middle_section_offset.y())
    end_pivot_offset = hou.Vector3(end_section_offset.x(), -section_offsets_y.y(), -end_section_offset.y())

    middle_pivot = up_pivot + hou.Vector3(
        offset_baseline.x() * middle_pivot_offset.x(),
        offset_baseline.y() * middle_pivot_offset.y(),
        offset_baseline.z() * middle_pivot_offset.z(),
    )
    end_pivot = up_pivot + hou.Vector3(
        offset_baseline.x() * end_pivot_offset.x(),
        offset_baseline.y() * end_pivot_offset.y(),
        offset_baseline.z() * end_pivot_offset.z(),
    )

    c2_positions = _construct_section_loop(
        middle_pivot,
        hou.Vector2(w * middle_section_ratio.x(), h * middle_section_ratio.y()),
        middle_section_rotation,
    )
    c4_positions = _construct_section_loop(
        end_pivot,
        hou.Vector2(w * end_section_ratio.x(), h * end_section_ratio.y()),
        end_section_rotation,
    )
    c3_positions = _interpolate_intermediate_loop(c2_positions, c4_positions)

    loops = [
        [c1_1, c1_2, c1_3, c1_4],
        [geo.createPoint() for _ in range(4)],
        [geo.createPoint() for _ in range(4)],
        [geo.createPoint() for _ in range(4)],
    ]
    for pts, positions in zip(loops[1:], (c2_positions, c3_positions, c4_positions)):
        for pt, pos in zip(pts, positions):
            pt.setPosition(pos)

    for i, loop in enumerate(loops[1:], start=2):
        for j, point in enumerate(loop, start=1):
            set_point_id(point, f"chelicera{i}_{j}")

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
            ])

    fill_face(geo, loops[-1])
    geo.deletePrims(socket_prims)

def _get_vector2_parm(node: hou.SopNode, name: str) -> hou.Vector2:
    parm_tuple = node.parmTuple(name)
    assert parm_tuple is not None, f"Expected parameter {name!r} on {node.path()}"
    return hou.Vector2(parm_tuple.eval())

def _construct_section_loop(
    pivot: hou.Vector3,
    size: hou.Vector2,
    rotation: hou.Vector2,
) -> list[hou.Vector3]:
    rot_matrix = hou.hmath.buildRotate(rotation.x(), 0.0, rotation.y())
    half_w, half_h = size.x() / 2.0, size.y() / 2.0
    corners = (
        hou.Vector3(-half_w, -half_h, 0.0),
        hou.Vector3( half_w, -half_h, 0.0),
        hou.Vector3( half_w,  half_h, 0.0),
        hou.Vector3(-half_w,  half_h, 0.0),
    )
    return [pivot + corner * rot_matrix for corner in corners]

def _interpolate_intermediate_loop(
    c2: list[hou.Vector3],
    c4: list[hou.Vector3],
) -> list[hou.Vector3]:
    c3 = []
    for j in range(4):
        x_weight_c2 = 2.0 / 3.0 if j in (0, 3) else 1.0 / 3.0
        x_weight_c4 = 1.0 - x_weight_c2
        c3.append(
            hou.Vector3(
                c2[j].x() * x_weight_c2 + c4[j].x() * x_weight_c4,
                c2[j].y() * (1.0 / 3.0) + c4[j].y() * (2.0 / 3.0),
                c2[j].z() * (1.0 / 3.0) + c4[j].z() * (2.0 / 3.0),
            )
        )
    return c3
