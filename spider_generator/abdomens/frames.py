import math

import hou

from houkit.attributer import add_global_attrib
from houkit.geomath import get_point_on_ellipse_2d
from houkit.noder import get_control, get_parent
from houkit.parameterizer import get_parms
from ..spiders import attributes as spider_attributes
from ..helper import add_id_point, points_by_id, positions_from_geo, replace_points
from .attributes import (
    abdomenend,
    abdomenhorizontalrim,
    abdomenorigin,
    abdomensidelower,
    abdomensideupper,
    abdomenverticalrim,
)


def prepare_cephalothorax_info(node: hou.SopNode) -> None:
    geo = node.geometry()
    bbox = geo.boundingBox()
    size = bbox.sizevec()
    cw, ch, cl = size.x(), size.y(), size.z()

    y_max = bbox.maxvec().y()
    y_min = bbox.minvec().y()

    points = points_by_id(geo)
    upper = points.get(spider_attributes.cephapedicelupper())
    assert upper is not None, f"Expected {spider_attributes.cephapedicelupper()!r} in cephalothorax"
    right = points.get(spider_attributes.cephapedicelright())
    assert right is not None, f"Expected {spider_attributes.cephapedicelright()!r} in cephalothorax"
    lower = points.get(spider_attributes.cephapedicellower())
    assert lower is not None, f"Expected {spider_attributes.cephapedicellower()!r} in cephalothorax"

    origin_y = 0.0
    upper_span = y_max - origin_y
    lower_span = origin_y - y_min
    assert lower_span > 1e-6, "Expected positive cephalothorax lower span"
    upper_lower_ratio = upper_span / lower_span

    tmp_pedicel_length = right.position().x() - upper.position().x()
    tmp_pedicel_height = upper.position().y() - origin_y

    add_global_attrib(geo, "tmp_cepha_size", (0.0, 0.0, 0.0))
    geo.setGlobalAttribValue("tmp_cepha_size", (cw, ch, cl))

    add_global_attrib(geo, "tmp_cepha_upper_lower_ratio", 0.0)
    geo.setGlobalAttribValue("tmp_cepha_upper_lower_ratio", upper_lower_ratio)

    add_global_attrib(geo, "tmp_pedicel_length", 0.0)
    geo.setGlobalAttribValue("tmp_pedicel_length", tmp_pedicel_length)

    add_global_attrib(geo, "tmp_pedicel_height", 0.0)
    geo.setGlobalAttribValue("tmp_pedicel_height", tmp_pedicel_height)


def add_width_frame(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    tmp_cepha_size = geo.attribValue("tmp_cepha_size")
    assert tmp_cepha_size is not None, "Expected tmp_cepha_size attribute"
    cw, _, cl = tmp_cepha_size

    tmp_pedicel_length = geo.attribValue("tmp_pedicel_length")
    assert tmp_pedicel_length is not None, "Expected tmp_pedicel_length attribute"

    params = get_parms(parent)
    control_params = get_parms(get_control(node, "CONTROL"))

    size_ratio_x, _, size_ratio_z = params.size_ratios
    plateau_start, plateau_end = params.width_hold_ratios
    end_ratio = control_params.end_size_ratio

    length = cl * size_ratio_z
    half_width = cw * size_ratio_x / 2.0

    origin = hou.Vector3(0.0, 0.0, 0.0)
    r1 = hou.Vector3(tmp_pedicel_length, 0.0, 0.0)
    r2 = hou.Vector3(half_width, 0.0, plateau_start * length)
    r3 = hou.Vector3(half_width, 0.0, plateau_end * length)
    r4 = hou.Vector3(half_width * end_ratio, 0.0, length)
    end = hou.Vector3(0.0, 0.0, length)

    points_data = [
        (abdomenorigin(), origin),
        (abdomenhorizontalrim(1), r1),
        (abdomenhorizontalrim(2), r2),
        (abdomenhorizontalrim(3), r3),
        (abdomenhorizontalrim(4), r4),
        (abdomenend(), end),
    ]
    replace_points(geo, points_data)


def add_height_frame(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    tmp_cepha_size = geo.attribValue("tmp_cepha_size")
    assert tmp_cepha_size is not None, "Expected tmp_cepha_size attribute"
    _, ch, cl = tmp_cepha_size

    upper_lower_ratio = geo.attribValue("tmp_cepha_upper_lower_ratio")
    assert upper_lower_ratio is not None, "Expected tmp_cepha_upper_lower_ratio attribute"

    tmp_pedicel_height = geo.attribValue("tmp_pedicel_height")
    assert tmp_pedicel_height is not None, "Expected tmp_pedicel_height attribute"

    params = get_parms(parent)
    control_params = get_parms(get_control(node, "CONTROL"))

    _, size_ratio_y, size_ratio_z = params.size_ratios
    plateau_start, plateau_end = params.width_hold_ratios
    end_ratio = control_params.end_size_ratio

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
    replace_points(geo, points_data)


def add_upper_middle_frame(node: hou.SopNode) -> None:
    add_middle_frame(node, negative=False)


def add_lower_middle_frame(node: hou.SopNode) -> None:
    add_middle_frame(node, negative=True)


def add_middle_frame(node: hou.SopNode, negative: bool = False) -> None:
    geo = node.geometry()

    sign = -1 if negative else 1
    side_attr = abdomensidelower if negative else abdomensideupper

    o, v1, h1 = positions_from_geo(
        geo,
        abdomenorigin(),
        abdomenverticalrim(sign * 1),
        abdomenhorizontalrim(1),
    )
    s1 = get_point_on_ellipse_2d(o, v1, h1, math.pi / 4)

    s_points = [s1]
    for i in range(2, 5):
        vi, hi = positions_from_geo(
            geo,
            abdomenverticalrim(sign * i),
            abdomenhorizontalrim(i),
        )
        center = hou.Vector3(0.0, 0.0, vi.z())
        s_points.append(get_point_on_ellipse_2d(center, vi, hi))

    for i, pos in enumerate(s_points, start=1):
        add_id_point(geo, pos, side_attr(i))
