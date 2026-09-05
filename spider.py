import math

import hou

import abdomen
import base_sops
import head
import sternum
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
from utilities.topology import fill_pentagon


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

    abdomen_node = abdomen.build(spider, opened_cepha)

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
    headsupport3 = points.get(head.headsupport(3))
    assert headsupport3 is not None, "Expected headsupport3 point in cephalothorax"
    headsupport_minus3 = points.get(head.headsupport(-3))
    assert headsupport_minus3 is not None, "Expected headsupport-3 point in cephalothorax"
    headsupport4 = points.get(head.headsupport(4))
    assert headsupport4 is not None, "Expected headsupport4 point in cephalothorax"
    sternumrim5 = points.get(sternum.sternumrim(5))
    assert sternumrim5 is not None, "Expected sternumrim5 point in cephalothorax"
    bs5_1 = points.get(base_sops.basesternum(5, 1))
    assert bs5_1 is not None, "Expected basesternum5_1 point in cephalothorax"
    bs5_2 = points.get(base_sops.basesternum(5, 2))
    assert bs5_2 is not None, "Expected basesternum5_2 point in cephalothorax"

    d = _get_opening_support_loop_width(bs5_1, bs5_2, pedicel_size_ratio_x)

    cp_outer_lower, right_inner, left_inner = _identify_pedicel_membrane_points(geo)
    cp_right, cp_left, cp_outer_right, cp_outer_left = _add_side_cepha_pedicel_points(
        geo, baseend0, bs5_1, bs5_2, pedicel_size_ratio_x, d
    )
    cp_upper, cp_lower = _position_vertical_pedicel_points(
        geo, baseend0, headsupport4, sternumrim5, cp_outer_lower, pedicel_size_ratio, d
    )
    _reconnect_lower_sternum_pedicel_loop(
        geo,
        cp_lower,
        cp_outer_lower,
        cp_right,
        cp_outer_right,
        cp_left,
        cp_outer_left,
        left_inner,
        right_inner,
        bs5_1,
        bs5_2,
        sternumrim5,
    )
    p_right, p_left, basesupportend0, basesupportsternum5_1, basesupportsternum5_2 = (
        _reconnect_upper_sternum_pedicel_loop(
            geo,
            baseend0,
            headsupport4,
            cp_upper,
            cp_right,
            cp_outer_right,
            cp_left,
            cp_outer_left,
            bs5_1,
            bs5_2,
            pedicel_size_ratio_x,
        )
    )
    _retopo_head_back_faces(
        geo,
        headsupport3,
        headsupport_minus3,
        headsupport4,
        basesupportend0,
        basesupportsternum5_1,
        basesupportsternum5_2,
        p_right,
        p_left,
    )
    _adjust_opening_points_depth(cp_right, cp_left, cp_upper)


def _get_opening_support_loop_width(
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    pedicel_size_ratio_x: float,
) -> float:
    return bs5_1.position().x() * (1.0 - pedicel_size_ratio_x) * 0.035


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
        if pt_id == sternum.sternumrim(5):
            continue
        if abs(pt.position().x()) < 1e-4:
            p_lower = pt
        elif pt.position().x() > 0:
            right_inner = pt
        else:
            left_inner = pt

    assert p_lower is not None, "Expected lower p point in basepedicelmembrane"
    assert right_inner is not None, "Expected right inner point in basepedicelmembrane"
    assert left_inner is not None, "Expected left inner point in basepedicelmembrane"
    return p_lower, right_inner, left_inner


def _add_side_cepha_pedicel_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    size_ratio_x: float,
    d: float,
) -> tuple[hou.Point, hou.Point, hou.Point, hou.Point]:
    p_end = baseend0.position()
    pos_bs5_1 = bs5_1.position()
    pos_bs5_2 = bs5_2.position()

    dir_right = (pos_bs5_1 - p_end).normalized()
    dir_left = (pos_bs5_2 - p_end).normalized()

    pos_right = pos_bs5_1 * size_ratio_x + p_end * (1 - size_ratio_x)
    pos_outer_right = pos_right + dir_right * d

    pt_right = geo.createPoint()
    pt_right.setPosition(pos_right)
    pt_right.setAttribValue("id", cephapedicelright())

    pt_outer_right = geo.createPoint()
    pt_outer_right.setPosition(pos_outer_right)

    pos_left = pos_bs5_2 * size_ratio_x + p_end * (1 - size_ratio_x)
    pos_outer_left = pos_left + dir_left * d

    pt_left = geo.createPoint()
    pt_left.setPosition(pos_left)
    pt_left.setAttribValue("id", cephapedicelleft())

    pt_outer_left = geo.createPoint()
    pt_outer_left.setPosition(pos_outer_left)

    return pt_right, pt_left, pt_outer_right, pt_outer_left


def _position_vertical_pedicel_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    headsupport4: hou.Point,
    sternumrim5: hou.Point,
    cp_outer_lower: hou.Point,
    pedicel_size_ratio: tuple[float, float],
    d: float,
) -> tuple[hou.Point, hou.Point]:
    ratio_x, ratio_y = pedicel_size_ratio

    p_end = baseend0.position()
    p_head = headsupport4.position()
    p_sternum = sternumrim5.position()

    dir_upper = (p_head - p_end).normalized()

    pos_cp_lower = p_sternum * ratio_y + p_end * (1 - ratio_y)
    pos_cp_outer_lower = p_sternum * 1/3 + pos_cp_lower * 2/3
    cp_outer_lower.setPosition(pos_cp_outer_lower)

    cp_lower = geo.createPoint()
    cp_lower.setPosition(pos_cp_lower)
    cp_lower.setAttribValue("id", cephapedicellower())

    target_height = p_end.y() - pos_cp_lower.y()
    dy = p_head.y() - p_end.y()
    assert abs(dy) > 1e-6, "Expected non-zero y delta between baseend0 and headback0"
    t = target_height / dy
    offset = t * (p_head - p_end)
    new_end = p_end + offset

    p_upper = new_end * (1 - ratio_x) + p_end * ratio_x
    pos_baseend0 = p_upper + dir_upper * d
    baseend0_offset = pos_baseend0 - p_end

    cp_upper = geo.createPoint()
    cp_upper.setPosition(p_upper)
    cp_upper.setAttribValue("id", cephapedicelupper())

    buffer_points = _find_head_support_end_points(geo, baseend0, headsupport4)
    baseend0.setPosition(pos_baseend0)
    for pt in buffer_points:
        pt.setPosition(pt.position() + baseend0_offset)

    return cp_upper, cp_lower


def _find_head_support_end_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    headsupport4: hou.Point,
) -> list[hou.Point]:
    buffer_points = []
    for prim in geo.prims():
        if prim.stringAttribValue("region") == "headback":
            for pt in prim.points():
                if abs(pt.position().x()) < 1e-4 and pt not in (baseend0, headsupport4) and pt not in buffer_points:
                    buffer_points.append(pt)
    return buffer_points


def _reconnect_lower_sternum_pedicel_loop(
    geo: hou.Geometry,
    cp_lower: hou.Point,
    cp_outer_lower: hou.Point,
    cp_right: hou.Point,
    cp_outer_right: hou.Point,
    cp_left: hou.Point,
    cp_outer_left: hou.Point,
    left_inner: hou.Point,
    right_inner: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    s5: hou.Point,
) -> None:
    p_prims = list(cp_outer_lower.prims())
    geo.deletePrims(p_prims, keep_points=True)

    fill_pentagon(geo, [cp_outer_right, bs5_1, right_inner, s5, cp_outer_lower], (cp_outer_lower, s5), reverse=False)
    fill_pentagon(geo, [cp_outer_left, bs5_2, left_inner, s5, cp_outer_lower], (cp_outer_lower, s5), reverse=True)

    fill_face(geo, [cp_lower, cp_right, cp_outer_right, cp_outer_lower], reverse=False)
    fill_face(geo, [cp_lower, cp_left, cp_outer_left, cp_outer_lower], reverse=True)


def _reconnect_upper_sternum_pedicel_loop(
    geo: hou.Geometry,
    baseend0: hou.Point,
    headsupport4: hou.Point,
    cp_upper: hou.Point,
    cp_right: hou.Point,
    cp_outer_right: hou.Point,
    cp_left: hou.Point,
    cp_outer_left: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    size_ratio_x: float,
) -> tuple[hou.Point, hou.Point, hou.Point, hou.Point, hou.Point]:
    f_buf_ur = fill_face(geo, [cp_upper, cp_right, cp_outer_right, baseend0], reverse=True)
    f_buf_ul = fill_face(geo, [cp_upper, cp_left, cp_outer_left, baseend0], reverse=False)
    f_buf_ur.setAttribValue("region", base_sops.Region.BASEBUFFERMEMBRANE)
    f_buf_ul.setAttribValue("region", base_sops.Region.BASEBUFFERMEMBRANE)

    b_end, b_bs1, b_bs2 = baseend0, bs5_1, bs5_2
    p_r, p_l = cp_outer_right, cp_outer_left

    while True:
        quad_r, quad_l, next_end, next_bs1, next_bs2 = _find_next_headback_rung(b_end, b_bs1, b_bs2)
        if next_end == headsupport4:
            break

        next_p_r = _interpolate_support_p(geo, cp_outer_right, baseend0, bs5_1, next_end, next_bs1, size_ratio_x)
        next_p_l = _interpolate_support_p(geo, cp_outer_left, baseend0, bs5_2, next_end, next_bs2, size_ratio_x)

        geo.deletePrims([quad_r, quad_l], keep_points=True)

        f_r1 = fill_face(geo, [next_end, b_end, p_r, next_p_r], reverse=True)
        f_r2 = fill_face(geo, [next_p_r, p_r, b_bs1, next_bs1], reverse=True)
        f_l1 = fill_face(geo, [next_end, b_end, p_l, next_p_l], reverse=False)
        f_l2 = fill_face(geo, [next_p_l, p_l, b_bs2, next_bs2], reverse=False)

        for f in (f_r1, f_r2, f_l1, f_l2):
            f.setAttribValue("region", "headback")

        b_end, b_bs1, b_bs2 = next_end, next_bs1, next_bs2
        p_r, p_l = next_p_r, next_p_l

    return p_r, p_l, b_end, b_bs1, b_bs2

def _find_next_headback_rung(
    b_end: hou.Point,
    b_bs1: hou.Point,
    b_bs2: hou.Point,
) -> tuple[hou.Prim, hou.Prim, hou.Point, hou.Point, hou.Point]:
    pr_r = [pr for pr in b_end.prims() if pr.stringAttribValue("region") == "headback" and b_bs1 in pr.points()]
    pr_l = [pr for pr in b_end.prims() if pr.stringAttribValue("region") == "headback" and b_bs2 in pr.points()]
    assert len(pr_r) == 1 and len(pr_l) == 1, "Expected 1 headback prim on each side of headback rung"

    quad_r, quad_l = pr_r[0], pr_l[0]
    pts_r = list(quad_r.points())
    pts_l = list(quad_l.points())

    next_b_end = [p for p in pts_r if abs(p.position().x()) < 1e-4 and p != b_end][0]
    next_b_bs1 = [p for p in pts_r if p not in (b_end, b_bs1, next_b_end)][0]
    next_b_bs2 = [p for p in pts_l if p not in (b_end, b_bs2, next_b_end)][0]

    return quad_r, quad_l, next_b_end, next_b_bs1, next_b_bs2

def _interpolate_support_p(
    geo: hou.Geometry,
    cp_outer: hou.Point,
    base_end: hou.Point,
    base_bs: hou.Point,
    next_end: hou.Point,
    next_bs: hou.Point,
    ratio_x: float,
) -> hou.Point:
    v_end = next_end.position() - base_end.position()
    v_bs = next_bs.position() - base_bs.position()
    pos = cp_outer.position() + v_bs * ratio_x + v_end * (1.0 - ratio_x)
    pt = geo.createPoint()
    pt.setPosition(pos)
    return pt

def _retopo_head_back_faces(
    geo: hou.Geometry,
    headsupport3: hou.Point,
    headsupport_minus3: hou.Point,
    headsupport4: hou.Point,
    basesupportend0: hou.Point,
    basesupportsternum5_1: hou.Point,
    basesupportsternum5_2: hou.Point,
    p_right: hou.Point,
    p_left: hou.Point,
) -> None:
    prims_to_delete = [
        pr for pr in headsupport4.prims()
        if pr.stringAttribValue("region") == "headback" and basesupportend0 in pr.points()
    ]
    assert len(prims_to_delete) == 2, f"Expected 2 upper headback prims on headsupport4, got {len(prims_to_delete)}"
    geo.deletePrims(prims_to_delete, keep_points=True)

    fill_pentagon(
        geo,
        [headsupport3, headsupport4, basesupportend0, p_right, basesupportsternum5_1],
        (headsupport4, basesupportend0),
        reverse=False,
    )
    fill_pentagon(
        geo,
        [headsupport_minus3, headsupport4, basesupportend0, p_left, basesupportsternum5_2],
        (headsupport4, basesupportend0),
        reverse=True,
    )

    for prim in geo.prims():
        if not prim.stringAttribValue("region"):
            prim.setAttribValue("region", "headback")


def _adjust_opening_points_depth(
    cp_right: hou.Point,
    cp_left: hou.Point,
    cp_upper: hou.Point,
) -> None:
    offset_z = (cp_right.position().x() - cp_left.position().x()) / 4.0
    for pt in (cp_right, cp_left, cp_upper):
        pos = pt.position()
        pt.setPosition(hou.Vector3(pos.x(), pos.y(), pos.z() - offset_z))
