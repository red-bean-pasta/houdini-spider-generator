import math
from enum import StrEnum, auto

import hou

import spider
from utilities.common import (
    add_float_param,
    add_global_attr,
    add_prim_attr,
    fill_face,
    get_params,
    get_parent,
    remove_attrs,
)
from helper import (
    add_id_attr,
    affix_id,
    points_by_id,
    rename_left_ids,
)
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_outside_recalculation,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import get_point_on_ellipse_2d


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


def build(spider_node: hou.OpNode, cephalothorax: hou.SopNode) -> hou.SopNode:
    abdomen = add_reloadable_subnet(spider_node, "abdomen")
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
    _ = add_merge(abdomen, "merge_frames_and_points", lower_middle_frame, connected)

    mirrored = add_mirror(abdomen, "mirror_left_faces", right_side_faces, (1, 0, 0), True, False)
    renamed = sopify(abdomen, mirrored, _rename_left_ids)
    regions = sopify(abdomen, renamed, _add_regions)
    cleaned = sopify(abdomen, regions, _cleanup_temp_attributes)

    recalculate = add_outside_recalculation(abdomen, "recalculate_normals", cleaned)
    add_output(abdomen, "OUT_ABDOMEN", recalculate)
    abdomen.layoutChildren()
    return abdomen


def _add_parameters(abdomen: hou.SopNode) -> None:
    add_float_param(
        abdomen,
        "size_ratio",
        3,
        (1.2, 1.0, 1.2),
        (0.0, None),
    )
    add_float_param(
        abdomen,
        "plateau_duration",
        2,
        (0.1, 0.5),
        (0.0, None),
    )


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_param(
        control,
        "end_ratio",
        1,
        0.2,
        (0.0, None),
    )
    return control


def _prepare_cephalothorax_info(node: hou.SopNode) -> None:
    geo = node.geometry()
    bbox = geo.boundingBox()
    size = bbox.sizevec()
    cw, ch, cl = size.x(), size.y(), size.z()

    y_max = bbox.maxvec().y()
    y_min = bbox.minvec().y()

    points = points_by_id(geo)
    upper = points.get(spider.cephapedicelupper())
    assert upper is not None, f"Expected {spider.cephapedicelupper()!r} in cephalothorax"
    right = points.get(spider.cephapedicelright())
    assert right is not None, f"Expected {spider.cephapedicelright()!r} in cephalothorax"
    lower = points.get(spider.cephapedicellower())
    assert lower is not None, f"Expected {spider.cephapedicellower()!r} in cephalothorax"

    origin_y = 0.0
    upper_span = y_max - origin_y
    lower_span = origin_y - y_min
    assert lower_span > 1e-6, "Expected positive cephalothorax lower span"
    upper_lower_ratio = upper_span / lower_span

    tmp_pedicel_length = right.position().x() - upper.position().x()
    tmp_pedicel_height = upper.position().y() - origin_y

    add_global_attr(geo, "tmp_cepha_size", (0.0, 0.0, 0.0))
    geo.setGlobalAttribValue("tmp_cepha_size", (cw, ch, cl))

    add_global_attr(geo, "tmp_cepha_upper_lower_ratio", 0.0)
    geo.setGlobalAttribValue("tmp_cepha_upper_lower_ratio", upper_lower_ratio)

    add_global_attr(geo, "tmp_pedicel_length", 0.0)
    geo.setGlobalAttribValue("tmp_pedicel_length", tmp_pedicel_length)

    add_global_attr(geo, "tmp_pedicel_height", 0.0)
    geo.setGlobalAttribValue("tmp_pedicel_height", tmp_pedicel_height)


def _add_width_frame(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    control = parent.node("CONTROL")
    assert control is not None, "Expected CONTROL node"

    tmp_cepha_size = geo.attribValue("tmp_cepha_size")
    assert tmp_cepha_size is not None, "Expected tmp_cepha_size attribute"
    cw, _, cl = tmp_cepha_size

    tmp_pedicel_length = geo.attribValue("tmp_pedicel_length")
    assert tmp_pedicel_length is not None, "Expected tmp_pedicel_length attribute"

    params = get_params(parent)
    control_params = get_params(control)

    size_ratio_x, _, size_ratio_z = params.size_ratio
    plateau_start, plateau_end = params.plateau_duration
    end_ratio = control_params.end_ratio

    length = cl * size_ratio_z
    half_width = cw * size_ratio_x / 2.0

    origin = hou.Vector3(0.0, 0.0, 0.0)
    r1 = hou.Vector3(tmp_pedicel_length, 0.0, 0.0)
    r2 = hou.Vector3(half_width, 0.0, plateau_start * length)
    r3 = hou.Vector3(half_width, 0.0, plateau_end * length)
    r4 = hou.Vector3(half_width * end_ratio, 0.0, length)
    end = hou.Vector3(0.0, 0.0, length)

    geo.clear()
    add_id_attr(geo)
    points_data = [\
        (abdomenorigin(), origin),\
        (abdomenhorizontalrim(1), r1),\
        (abdomenhorizontalrim(2), r2),\
        (abdomenhorizontalrim(3), r3),\
        (abdomenhorizontalrim(4), r4),\
        (abdomenend(), end),\
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

    tmp_pedicel_height = geo.attribValue("tmp_pedicel_height")
    assert tmp_pedicel_height is not None, "Expected tmp_pedicel_height attribute"

    params = get_params(parent)
    control_params = get_params(control)

    _, size_ratio_y, size_ratio_z = params.size_ratio
    plateau_start, plateau_end = params.plateau_duration
    end_ratio = control_params.end_ratio

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

    r1 = r2 * (tmp_pedicel_height / r2.y())
    rn1 = rn2 * (tmp_pedicel_height / abs(rn2.y()))

    geo.clear()
    add_id_attr(geo)
    points_data = [\
        (abdomenorigin(), o),\
        (abdomenverticalrim(1), r1),\
        (abdomenverticalrim(2), r2),\
        (abdomenverticalrim(3), r3),\
        (abdomenverticalrim(4), r4),\
        (abdomenend(), end),\
        (abdomenverticalrim(-4), rn4),\
        (abdomenverticalrim(-3), rn3),\
        (abdomenverticalrim(-2), rn2),\
        (abdomenverticalrim(-1), rn1),\
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


def _fill_right_side_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    add_prim_attr(geo, "region", "abdomen")

    o = points[abdomenorigin()]
    e = points[abdomenend()]
    v = lambda i: points[abdomenverticalrim(i)]
    vn = lambda i: points[abdomenverticalrim(-i)]
    h = lambda i: points[abdomenhorizontalrim(i)]
    su = lambda i: points[abdomensideupper(i)]
    sl = lambda i: points[abdomensidelower(i)]

    fill_face(geo, [o, v(1), su(1), h(1)])
    fill_face(geo, [o, h(1), sl(1), vn(1)])

    for j in range(1, 4):
        fill_face(geo, [v(j), v(j + 1), su(j + 1), su(j)])
        fill_face(geo, [su(j), su(j + 1), h(j + 1), h(j)])
        fill_face(geo, [h(j), h(j + 1), sl(j + 1), sl(j)])
        fill_face(geo, [sl(j), sl(j + 1), vn(j + 1), vn(j)])

    fill_face(geo, [e, h(4), su(4), v(4)])
    fill_face(geo, [e, vn(4), sl(4), h(4)])


def _rename_left_ids(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry())\


def _add_regions(node: hou.SopNode) -> None:
    geo = node.geometry()
    add_prim_attr(geo, "region", "abdomen")
    for prim in geo.prims():
        prim.setAttribValue("region", "abdomen")


def _connect_frames_tmp(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    o = abdomenorigin()
    e = abdomenend()

    chains = [\
        [o] + [abdomenhorizontalrim(i) for i in range(1, 5)] + [e],\
        [o] + [abdomenverticalrim(i) for i in range(1, 5)] + [e],\
        [o] + [abdomenverticalrim(-i) for i in range(1, 5)] + [e],\
        [o] + [abdomensideupper(i) for i in range(1, 5)] + [e],\
        [o] + [abdomensidelower(i) for i in range(1, 5)] + [e],\
    ]

    for chain in chains:
        poly = geo.createPolygon(is_closed=False)
        for point_id in chain:
            point = points.get(point_id)
            assert point is not None, f"Expected point {point_id!r}"
            poly.addVertex(point)


def _cleanup_temp_attributes(node: hou.SopNode) -> None:
    remove_attrs(
        node.geometry(),
        global_attribs=("tmp_cepha_size", "tmp_cepha_upper_lower_ratio", "tmp_pedicel_length", "tmp_pedicel_height"),
    )
