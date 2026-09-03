import math

import hou

import abdomen
import base_sops
import head
import sternum_sops
from abdomen import build as build_abdomen
from cephalothorax import build as build_cephalothorax
from leg import build as build_legs
from pedicel import build as build_pedicel
from utilities.common import (
    add_float_param,
    add_folder,
    fill_face,
    get_params,
    get_parent,
)
from helper import points_by_id
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_outside_recalculation,
    add_reload_button,
    sopify,
)
from utilities.topology import (
    fill_pentagon,
    fill_pentagon_with_buffer,
)


def cephapedicelupper() -> str:
    return "cephapedicelupper"
def cephapedicellower() -> str:
    return "cephapedicellower"
def cephapedicelright() -> str:
    return "cephapedicelright"
def cephapedicelleft() -> str:
    return "cephapedicelleft"


def build(parent: hou.OpNode) -> hou.SopNode:
    spider = _add_spider(parent)

    cephalothorax = build_cephalothorax(spider)
    opened_cepha = sopify(spider, cephalothorax, _open_cepha_pedicel)

    abdomen_node = build_abdomen(spider, opened_cepha)

    opened_abdomen = sopify(spider, abdomen_node, _open_abdomen_pedicel)
    merged_c_a = add_merge(spider, "merge_cephalothorax_and_abdomen", opened_cepha, opened_abdomen)

    pedicel = build_pedicel(spider, merged_c_a)
    merged_ca_p = add_merge(spider, "merge_main_and_pedicel", merged_c_a, pedicel)
    removed_sockets = sopify(spider, merged_ca_p, _remove_coxa_sockets)

    legs = build_legs(spider, merged_ca_p)
    merged_all = add_merge(spider, "merge_main_and_legs", removed_sockets, legs)
    fused = add_fuse(spider, "fuse_main_and_legs", merged_all)
    recalculated = add_outside_recalculation(spider, "recalculate_normals", fused)

    recalculated.setDisplayFlag(True)
    recalculated.setRenderFlag(True)
    spider.layoutChildren()
    return spider


def _add_spider(parent: hou.OpNode) -> hou.SopNode:
    spider = parent.node("spider")
    if not spider:
        spider = parent.createNode("geo", "spider")
        for child in spider.children():
            child.destroy()
        add_reload_button(spider)

    _add_parameters(spider)
    return spider


def _add_parameters(spider: hou.OpNode) -> None:
    add_folder(
        spider,
        "build"
    )
    add_float_param(
        spider,
        "pedicel_size_ratio",
        2,
        (0.5, 0.5),
        (0.0, 1.0),
        folder_label="Build",
        help="Pedicel width and height ratio relative to the base pedicel opening."
    )


def _open_abdomen_pedicel(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    points = points_by_id(geo)
    origin_point = points.get(abdomen.abdomenorigin())
    assert origin_point is not None, "Expected abdomenorigin point in abdomen"
    prims = list(origin_point.prims())
    geo.deletePrims(prims, keep_points=True)
    if origin_point in geo.points():
        geo.deletePoints([origin_point])


def _remove_coxa_sockets(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region").startswith(base_sops.Region.COXASOCKET)
    ]
    assert len(socket_prims) == 16, f"Expected 16 coxa socket prims, got {len(socket_prims)}"
    geo.deletePrims(socket_prims, keep_points=True)


def _open_cepha_pedicel(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)
    params = get_params(parent)
    pedicel_size_ratio = params.pedicel_size_ratio
    pedicel_size_ratio_x, _ = pedicel_size_ratio

    points = points_by_id(geo)

    baseend0 = points.get(base_sops.baseend(0))
    assert baseend0 is not None, "Expected baseend0 point in cephalothorax"
    headback0 = points.get(head.headback(0))
    assert headback0 is not None, "Expected headback0 point in cephalothorax"
    sternumrim5 = points.get(sternum_sops.sternumrim(5))
    assert sternumrim5 is not None, "Expected sternumrim5 point in cephalothorax"
    bs5_1 = points.get(base_sops.basesternum(5, 1))
    assert bs5_1 is not None, "Expected basesternum5_1 point in cephalothorax"
    bs5_2 = points.get(base_sops.basesternum(5, 2))
    assert bs5_2 is not None, "Expected basesternum5_2 point in cephalothorax"

    p_lower, right_inner, left_inner = _identify_pedicel_membrane_points(geo)
    _adjust_side_coxa_points(bs5_1, bs5_2, right_inner, left_inner)
    cp_right, cp_left = _add_side_cepha_pedicel_points(geo, baseend0, bs5_1, bs5_2, pedicel_size_ratio_x)
    cp_upper = _position_vertical_pedicel_points(geo, baseend0, headback0, sternumrim5, p_lower, pedicel_size_ratio)
    _reconnect_sternum_pedicel_loop(
        geo,
        cp_upper,
        cp_right,
        cp_left,
        p_lower,
        left_inner,
        right_inner,
        bs5_1,
        bs5_2,
        sternumrim5,
        baseend0,
    )

def _identify_pedicel_membrane_points(geo: hou.Geometry) -> tuple[hou.Point, hou.Point, hou.Point]:
    membrane_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == "basepedicelmembrane"
    ]
    assert len(membrane_prims) == 1, f"Expected 1 basepedicelmembrane prim, got {len(membrane_prims)}"
    mem_prim = membrane_prims[0]

    p_lower = None
    right_inner = None
    left_inner = None
    for pt in mem_prim.points():
        pt_id = pt.stringAttribValue("id")
        if pt_id == sternum_sops.sternumrim(5):
            continue
        if abs(pt.position().x()) < 1e-4:
            p_lower = pt
            pt.setAttribValue("id", cephapedicellower())
        elif pt.position().x() > 0:
            right_inner = pt
        else:
            left_inner = pt

    assert p_lower is not None, "Expected lower p point in basepedicelmembrane"
    assert right_inner is not None, "Expected right inner point in basepedicelmembrane"
    assert left_inner is not None, "Expected left inner point in basepedicelmembrane"
    return p_lower, right_inner, left_inner

def _adjust_side_coxa_points(
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    right_inner: hou.Point,
    left_inner: hou.Point,
) -> None:
    for r, c1 in ((bs5_1, right_inner), (bs5_2, left_inner)):
        offset = r.position() - c1.position()
        dx, dz = offset.x(), offset.z()
        len_xz = math.sqrt(dx**2 + dz**2)
        new_z = c1.position().z() + math.copysign(len_xz, dz)
        r.setPosition(hou.Vector3(c1.position().x(), r.position().y(), new_z))

def _add_side_cepha_pedicel_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    size_ratio_x: float,
) -> tuple[hou.Point, hou.Point]:
    pos_baseend0 = baseend0.position()
    pos_bs5_1 = bs5_1.position()
    pos_bs5_2 = bs5_2.position()

    pos_right = pos_bs5_1 * size_ratio_x + pos_baseend0 * (1 - size_ratio_x)
    pos_left = pos_bs5_2 * size_ratio_x + pos_baseend0 * (1 - size_ratio_x)

    pt_right = geo.createPoint()
    pt_right.setPosition(pos_right)
    pt_right.setAttribValue("id", cephapedicelright())

    pt_left = geo.createPoint()
    pt_left.setPosition(pos_left)
    pt_left.setAttribValue("id", cephapedicelleft())

    return pt_right, pt_left

def _position_vertical_pedicel_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    headback0: hou.Point,
    sternumrim5: hou.Point,
    lower: hou.Point,
    pedicel_size_ratio: tuple[float, float],
) -> hou.Point:
    ratio_x, ratio_y = pedicel_size_ratio

    p_end = baseend0.position()
    p_head = headback0.position()
    p_sternum = sternumrim5.position()

    p_lower = p_sternum * ratio_y + p_end * (1 - ratio_y)
    lower.setPosition(p_lower)

    target_height = p_end.y() - p_lower.y()
    dy = p_head.y() - p_end.y()
    assert abs(dy) > 1e-6, "Expected non-zero y delta between baseend0 and headback0"
    t = target_height / dy
    new_end = p_end + t * (p_head - p_end)

    baseend0.setPosition(new_end)

    p_upper = new_end * (1 - ratio_x) + p_end * ratio_x
    upper = geo.createPoint()
    upper.setPosition(p_upper)
    upper.setAttribValue("id", cephapedicelupper())

    return upper

def _reconnect_sternum_pedicel_loop(
    geo: hou.Geometry,
    cp_upper: hou.Point,
    cp_right: hou.Point,
    cp_left: hou.Point,
    cp_lower: hou.Point,
    left_inner: hou.Point,
    right_inner: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    s5: hou.Point,
    baseend0: hou.Point,
) -> None:
    p_prims = list(cp_lower.prims())
    geo.deletePrims(p_prims, keep_points=True)

    buffer_ratio = 0.035

    _, _, b_lower, b_right = fill_pentagon_with_buffer(
        geo,
        [cp_right, bs5_1, right_inner, s5, cp_lower],
        (cp_lower, cp_right),
        buffer_ratio,
        (cp_lower, s5),
        reverse=True,
    )

    b_left_pos = cp_left.position() * (1 - buffer_ratio) + bs5_2.position() * buffer_ratio
    b_left = geo.createPoint()
    b_left.setPosition(b_left_pos)

    b_upper_pos = cp_upper.position() * (1 - buffer_ratio) + baseend0.position() * buffer_ratio
    b_upper = geo.createPoint()
    b_upper.setPosition(b_upper_pos)

    _adjust_opening_points_depth(cp_right, cp_left, cp_upper)

    fill_face(geo, [cp_lower, cp_left, b_left, b_lower], reverse=False)
    fill_pentagon(geo, [b_left, bs5_2, left_inner, s5, b_lower], (b_lower, s5), reverse=False)

    fill_face(geo, [cp_upper, cp_right, b_right, b_upper], reverse=True)
    fill_face(geo, [b_upper, b_right, bs5_1, baseend0], reverse=True)
    fill_face(geo, [cp_upper, cp_left, b_left, b_upper], reverse=False)
    fill_face(geo, [b_upper, b_left, bs5_2, baseend0], reverse=False)

    for prim in geo.prims():
        if not prim.stringAttribValue("region"):
            prim.setAttribValue("region", base_sops.Region.BASEBUFFERMEMBRANE)

def _adjust_opening_points_depth(
    cp_right: hou.Point,
    cp_left: hou.Point,
    cp_upper: hou.Point,
) -> None:
    offset_z = (cp_right.position().x() - cp_left.position().x()) / 4.0
    for pt in (cp_right, cp_left, cp_upper):
        pos = pt.position()
        pt.setPosition(hou.Vector3(pos.x(), pos.y(), pos.z() - offset_z))
