from enum import StrEnum, auto

import hou

import sternum_sops
from hom_helper import (
    add_new_attr,
    add_new_id_attr,
    affix_id,
    get_float_parm,
    get_parent,
    points_by_id,
    sopify,
)
from sop_helper import add_fuse, add_merge, add_mirror, add_output


class ID(StrEnum):
    ABDOMENRIM = auto()
    ABDOMENHORIZONTALRIM = auto()
    ABDOMENVERTICALRIM = auto()

def abdomenrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENRIM, *i)

def abdomenhorizontalrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENHORIZONTALRIM, *i)

def abdomenverticalrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENVERTICALRIM, *i)


def build(spider: hou.OpNode, cephalothorax: hou.SopNode) -> hou.SopNode:
    abdomen = spider.createNode("subnet", "abdomen")
    abdomen.setInput(0, cephalothorax)
    _add_parameters(abdomen)
    _add_controls(abdomen)

    source = abdomen.indirectInputs()[0]
    cepha_info = sopify(abdomen, source, _prepare_cephalothorax_info)
    width_frame = sopify(abdomen, cepha_info, _add_width_frame)
    height_frame = sopify(abdomen, cepha_info, _add_height_frame)

    merged = add_merge(abdomen, "merge_frames", width_frame, height_frame)
    fused = add_fuse(abdomen, "fuse_frames", merged)

    # connected = sopify(abdomen, fused, _connect_frames_tmp)

    # mirrored_width = add_mirror(abdomen, "mirror_width_frame", width_frame, (1, 0, 0), True, False)

    add_output(abdomen, "OUT_ABDOMEN", fused)
    abdomen.layoutChildren()
    return abdomen


def _add_parameters(abdomen: hou.SopNode) -> hou.SopNode:
    templates = abdomen.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "size_ratio",
            "Size Ratio",
            3,
            default_value=(1.2, 1.0, 1.5),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "plateau_duration",
            "Plateau Duration",
            2,
            default_value=(0.1, 0.5),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "pedicel_flatness",
            "Pedicel Flatness",
            1,
            default_value=(0.5,),
            min=0.0,
            min_is_strict=True,
        )
    )
    abdomen.setParmTemplateGroup(templates)
    return abdomen


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    templates = control.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "end_ratio",
            "End Ratio",
            1,
            default_value=(0.2,),
            min=0.0,
            min_is_strict=True,
        )
    )
    control.setParmTemplateGroup(templates)
    return control


def _prepare_cephalothorax_info(node: hou.SopNode) -> None:
    geo = node.geometry()
    bbox = geo.boundingBox()
    size = bbox.sizevec()
    cw, ch, cl = size.x(), size.y(), size.z()

    y_max = bbox.maxvec().y()
    y_min = bbox.minvec().y()

    points = points_by_id(geo)
    sternumrim5_id = sternum_sops.sternumrim(5)
    sternumrim5_point = points.get(sternumrim5_id)
    assert sternumrim5_point is not None, f"Expected {sternumrim5_id!r} in cephalothorax"
    sternumrim5_y = sternumrim5_point.position().y()

    upper_span = y_max - sternumrim5_y
    lower_span = sternumrim5_y - y_min
    assert lower_span > 1e-6, "Expected positive cephalothorax lower span"
    upper_lower_ratio = upper_span / lower_span

    add_new_attr(geo, hou.attribType.Global, "tmp_cepha_size", (0.0, 0.0, 0.0))
    geo.setGlobalAttribValue("tmp_cepha_size", (cw, ch, cl))

    add_new_attr(geo, hou.attribType.Global, "tmp_cepha_upper_lower_ratio", 0.0)
    geo.setGlobalAttribValue("tmp_cepha_upper_lower_ratio", upper_lower_ratio)


def _add_width_frame(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    control = parent.node("CONTROL")
    assert control is not None, "Expected CONTROL node"

    tmp_cepha_size = geo.attribValue("tmp_cepha_size")
    assert tmp_cepha_size is not None, "Expected tmp_cepha_size attribute"
    cw, _, cl = tmp_cepha_size

    size_ratio_x = get_float_parm(parent, "size_ratiox")
    size_ratio_z = get_float_parm(parent, "size_ratioz")
    plateau_start = get_float_parm(parent, "plateau_durationx")
    plateau_end = get_float_parm(parent, "plateau_durationy")
    pedicel_flatness = get_float_parm(parent, "pedicel_flatness")
    end_ratio = get_float_parm(control, "end_ratio")

    length = cl * size_ratio_z
    half_width = cw * size_ratio_x / 2.0

    r0 = hou.Vector3(0.0, 0.0, 0.0)
    r1 = hou.Vector3(half_width * pedicel_flatness, 0.0, 0.0)
    r2 = hou.Vector3(half_width, 0.0, plateau_start * length)
    r3 = hou.Vector3(half_width, 0.0, plateau_end * length)
    r4 = hou.Vector3(half_width * end_ratio, 0.0, length)
    r5 = hou.Vector3(0.0, 0.0, length)

    geo.clear()
    add_new_id_attr(geo)
    points_data = [
        (abdomenrim, r0),
        (abdomenhorizontalrim, [r1, r2, r3, r4]),
        (abdomenrim, r5)
    ]
    i = 0
    for attr, points in points_data:
        if isinstance(points, hou.Vector3):
            points = [points]
        for pos in points:
            point = geo.createPoint()
            point.setPosition(pos)
            point.setAttribValue("id", attr(i))
            i+=1


def _add_height_frame(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    control = parent.node("CONTROL")
    assert control is not None, "Expected CONTROL node"

    tmp_cepha_size = geo.attribValue("tmp_cepha_size")
    assert tmp_cepha_size is not None, "Expected tmp_cepha_size attribute"
    _, ch, cl = tmp_cepha_size

    upper_lower_ratio = geo.attribValue("tmp_cepha_upper_lower_ratio")
    assert upper_lower_ratio is not None, "Expected tmp_cepha_upper_lower_ratio attribute"

    size_ratio_y = get_float_parm(parent, "size_ratioy")
    size_ratio_z = get_float_parm(parent, "size_ratioz")
    plateau_start = get_float_parm(parent, "plateau_durationx")
    plateau_end = get_float_parm(parent, "plateau_durationy")
    pedicel_flatness = get_float_parm(parent, "pedicel_flatness")
    end_ratio = get_float_parm(control, "end_ratio")

    length = cl * size_ratio_z
    height = ch * size_ratio_y
    lower_height = height / (upper_lower_ratio + 1.0)
    upper_height = height - lower_height

    r0 = hou.Vector3(0.0, 0.0, 0.0)
    r2 = hou.Vector3(0.0, upper_height, plateau_start * length)
    r3 = hou.Vector3(0.0, upper_height, plateau_end * length)
    r4 = hou.Vector3(0.0, height * end_ratio / 2.0, length)
    r5 = hou.Vector3(0.0, 0.0, length)
    rn4 = hou.Vector3(0.0, -height * end_ratio / 2.0, length)
    rn3 = hou.Vector3(0.0, -lower_height, plateau_end * length)
    rn2 = hou.Vector3(0.0, -lower_height, plateau_start * length)

    r1 = r2 * pedicel_flatness
    rn1 = rn2 * pedicel_flatness

    geo.clear()
    add_new_id_attr(geo)
    points_data = [
        (abdomenrim(0), r0),
        (abdomenverticalrim(1), r1),
        (abdomenverticalrim(2), r2),
        (abdomenverticalrim(3), r3),
        (abdomenverticalrim(4), r4),
        (abdomenrim(5), r5),
        (abdomenverticalrim(-4), rn4),
        (abdomenverticalrim(-3), rn3),
        (abdomenverticalrim(-2), rn2),
        (abdomenverticalrim(-1), rn1),
    ]
    for point_id, position in points_data:
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)


def _connect_frames_tmp(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    chains = [
        [abdomenrim(0)] + [abdomenhorizontalrim(i) for i in range(1, 5)] + [abdomenrim(5)],
        [abdomenrim(0)] + [abdomenverticalrim(i) for i in range(1, 5)] + [abdomenrim(5)],
        [abdomenrim(0)] + [abdomenverticalrim(-i) for i in range(1, 5)] + [abdomenrim(5)],
    ]

    for chain in chains:
        poly = geo.createPolygon(is_closed=False)
        for point_id in chain:
            point = points.get(point_id)
            assert point is not None, f"Expected point {point_id!r}"
            poly.addVertex(point)
