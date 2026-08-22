from enum import StrEnum, auto

import hou

import base_sops
import hom_helper
from hom_helper import (
    add_new_id_attr,
    add_new_prim_attr,
    affix_id,
    fill_face,
    get_float_parm,
    get_parent,
    points_by_id,
    set_points_id,
    sopify, add_edge_group,
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

    add_output(chelicerae, "OUT_CHELICERAE", cleanup)
    chelicerae.layoutChildren()
    return chelicerae


def _add_parameters(chelicerae: hou.SopNode) -> None:
    templates = chelicerae.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "height_ratio",
            "Height Ratio",
            1,
            default_value=(0.35,),
            min=0.0,
            min_is_strict=True,
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
    add_new_id_attr(geo)
    add_new_prim_attr(geo, "region", "")
    base_points = []
    for point_id, position in zip(base_ids, base_positions):
        point = geo.createPoint()
        point.setPosition(position)
        base_points.append(point)
    set_points_id(base_points, list(base_ids))

    height_ratio = get_float_parm(get_parent(node), "height_ratio")
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
    hom_helper.attribute_after_inset(node, "region", "chelicerasocket", "cheliceramembrane", 2)


def _cleanup_inset_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()

    inset_scale = geo.findPrimAttrib("tmp_insetscale")
    if inset_scale is not None:
        inset_scale.destroy()

    edge_group = geo.findEdgeGroup("tmp_chelicera_split")
    if edge_group is not None:
        edge_group.destroy()

    seen_ids: set[str] = set()
    for point in geo.points():
        point_id = point.stringAttribValue("id")
        if not point_id:
            continue
        if point_id in seen_ids:
            point.setAttribValue("id", "")
        else:
            seen_ids.add(point_id)
