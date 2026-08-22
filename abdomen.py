import math
from enum import StrEnum, auto

import hou

import hom_helper
import sternum_sops
from hom_helper import (
    add_new_attr,
    add_new_id_attr,
    affix_id,
    fill_face,
    get_float_parm,
    get_parent,
    get_point_on_ellipse_2d,
    points_by_id,
    sopify,
)
from sop_helper import add_fuse, add_merge, add_mirror, add_output


class ID(StrEnum):
    ABDOMENORIGIN = auto()
    ABDOMENEND = auto()
    ABDOMENHORIZONTALRIM = auto()
    ABDOMENVERTICALRIM = auto()
    ABDOMENSIDEUPPER = auto()
    ABDOMENSIDELOWER = auto()

def abdomenorigin() -> str:
    return affix_id(ID.ABDOMENORIGIN)
def abdomenend() -> str:
    return affix_id(ID.ABDOMENEND)
def abdomenhorizontalrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENHORIZONTALRIM, *i)
def abdomenverticalrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENVERTICALRIM, *i)
def abdomensideupper(*i: int | str) -> str:
    return affix_id(ID.ABDOMENSIDEUPPER, *i)
def abdomensidelower(*i: int | str) -> str:
    return affix_id(ID.ABDOMENSIDELOWER, *i)


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
    upper_middle_frame = sopify(abdomen, fused, _add_upper_middle_frame)
    lower_middle_frame = sopify(abdomen, upper_middle_frame, _add_lower_middle_frame)
    right_side_faces = sopify(abdomen, lower_middle_frame, _fill_right_side_faces)

    # Kept for in-editor debug and visualize purpose
    connected = sopify(abdomen, lower_middle_frame, _connect_frames_tmp)
    connection_point_merge = add_merge(abdomen, "merge_frames_and_points", lower_middle_frame, connected)

    mirrored = add_mirror(abdomen, "mirror_left_faces", right_side_faces, (1, 0, 0), True, False)
    cleaned = sopify(abdomen, mirrored, _cleanup_temp_attributes)

    add_output(abdomen, "OUT_ABDOMEN", cleaned)
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

    origin = hou.Vector3(0.0, 0.0, 0.0)
    r1 = hou.Vector3(half_width * pedicel_flatness, 0.0, 0.0)
    r2 = hou.Vector3(half_width, 0.0, plateau_start * length)
    r3 = hou.Vector3(half_width, 0.0, plateau_end * length)
    r4 = hou.Vector3(half_width * end_ratio, 0.0, length)
    end = hou.Vector3(0.0, 0.0, length)

    geo.clear()
    add_new_id_attr(geo)
    points_data = [
        (abdomenorigin(), origin),
        (abdomenhorizontalrim(1), r1),
        (abdomenhorizontalrim(2), r2),
        (abdomenhorizontalrim(3), r3),
        (abdomenhorizontalrim(4), r4),
        (abdomenend(), end),
    ]
    for point_id, position in points_data:
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)


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

    o = hou.Vector3(0.0, 0.0, 0.0)
    r2 = hou.Vector3(0.0, upper_height, plateau_start * length)
    r3 = hou.Vector3(0.0, upper_height, plateau_end * length)
    r4 = hou.Vector3(0.0, height * end_ratio / 2.0, length)
    end = hou.Vector3(0.0, 0.0, length)
    rn4 = hou.Vector3(0.0, -height * end_ratio / 2.0, length)
    rn3 = hou.Vector3(0.0, -lower_height, plateau_end * length)
    rn2 = hou.Vector3(0.0, -lower_height, plateau_start * length)

    r1 = r2 * pedicel_flatness
    rn1 = rn2 * pedicel_flatness

    geo.clear()
    add_new_id_attr(geo)
    points_data = [
        (abdomenorigin(), o),
        (abdomenverticalrim(1), r1),
        (abdomenverticalrim(2), r2),
        (abdomenverticalrim(3), r3),
        (abdomenverticalrim(4), r4),
        (abdomenend(), end),
        (abdomenverticalrim(-4), rn4),
        (abdomenverticalrim(-3), rn3),
        (abdomenverticalrim(-2), rn2),
        (abdomenverticalrim(-1), rn1),
    ]
    for point_id, position in points_data:
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)


def _add_middle_frame(node: hou.SopNode, negative: bool = False) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    sign = -1 if negative else 1
    side_attr = abdomensidelower if negative else abdomensideupper

    o = points[abdomenorigin()].position()
    v1 = points[abdomenverticalrim(sign * 1)].position()
    h1 = points[abdomenhorizontalrim(1)].position()
    s1 = get_point_on_ellipse_2d(o, v1, h1, math.pi / 4)

    s_points = [s1]
    for i in range(2, 5):
        vi = points[abdomenverticalrim(sign * i)].position()
        hi = points[abdomenhorizontalrim(i)].position()
        center = hou.Vector3(0.0, 0.0, vi.z())
        s_points.append(get_point_on_ellipse_2d(center, vi, hi))

    for i, pos in enumerate(s_points, start=1):
        point = geo.createPoint()
        point.setPosition(pos)
        point.setAttribValue("id", side_attr(i))


def _add_upper_middle_frame(node: hou.SopNode) -> None:
    _add_middle_frame(node, negative=False)


def _add_lower_middle_frame(node: hou.SopNode) -> None:
    _add_middle_frame(node, negative=True)


_add_lowe_middle_frame = _add_lower_middle_frame


def _fill_right_side_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    o = points[abdomenorigin()]
    e = points[abdomenend()]
    v = lambda i: points[abdomenverticalrim(i)]
    vn = lambda i: points[abdomenverticalrim(-i)]
    h = lambda i: points[abdomenhorizontalrim(i)]
    su = lambda i: points[abdomensideupper(i)]
    sl = lambda i: points[abdomensidelower(i)]

    fill_face(geo, [o, v(1), su(1), h(1)])
    fill_face(geo, [o, h(1), sl(1), vn(1)])

    for i in range(1, 4):
        fill_face(geo, [v(i), v(i + 1), su(i + 1), su(i)])
        fill_face(geo, [su(i), su(i + 1), h(i + 1), h(i)])
        fill_face(geo, [h(i), h(i + 1), sl(i + 1), sl(i)])
        fill_face(geo, [sl(i), sl(i + 1), vn(i + 1), vn(i)])

    fill_face(geo, [e, h(4), su(4), v(4)])
    fill_face(geo, [e, vn(4), sl(4), h(4)])


def _connect_frames_tmp(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    o = abdomenorigin()
    e = abdomenend()

    chains = [
        [o] + [abdomenhorizontalrim(i) for i in range(1, 5)] + [e],
        [o] + [abdomenverticalrim(i) for i in range(1, 5)] + [e],
        [o] + [abdomenverticalrim(-i) for i in range(1, 5)] + [e],
        [o] + [abdomensideupper(i) for i in range(1, 5)] + [e],
        [o] + [abdomensidelower(i) for i in range(1, 5)] + [e],
    ]

    for chain in chains:
        poly = geo.createPolygon(is_closed=False)
        for point_id in chain:
            point = points.get(point_id)
            assert point is not None, f"Expected point {point_id!r}"
            poly.addVertex(point)


def _cleanup_temp_attributes(node: hou.SopNode) -> None:
    geo = node.geometry()
    hom_helper.remove_attributes(geo, global_attribs=("tmp_cepha_size", "tmp_cepha_upper_lower_ratio"))
