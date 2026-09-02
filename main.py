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
from utilities.common import fill_face
from utilities.helper import points_by_id
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_outside_recalculation,
    add_reload_button,
    propagate_parameters,
    sopify,
)


def cephapedicelupper() -> str:
    return base_sops.baseend(0)
def cephapedicellower() -> str:
    return "cephapedicellower"
def cephapedicelright() -> str:
    return base_sops.basesternum(5, 1)
def cephapedicelleft() -> str:
    return base_sops.basesternum(5, 2)


def build() -> hou.SopNode:
    spider = _add_spider()

    cephalothorax = build_cephalothorax(spider)
    opened_cepha = sopify(spider, cephalothorax, _open_cepha_pedicel)

    abdomen_node = build_abdomen(spider, opened_cepha)

    opened_abdomen = sopify(spider, abdomen_node, _open_abdomen_pedicel)
    merged_c_a = add_merge(spider, "merge_cephalothorax_and_abdomen", opened_cepha, opened_abdomen)

    pedicel = build_pedicel(spider, merged_c_a)
    propagate_parameters(spider, pedicel)
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


def _add_spider() -> hou.SopNode:
    obj = _get_root()

    spider = obj.node("spider")
    if spider:
        return spider

    spider = obj.createNode("geo", "spider")
    for child in spider.children():
        child.destroy()

    add_reload_button(spider)
    return spider


def _open_cepha_pedicel(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
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
    _position_pedicel_opening_points(baseend0, headback0, sternumrim5, p_lower)
    _adjust_side_cepha_pedicel_points(bs5_1, bs5_2, right_inner, left_inner)
    _reconnect_sternum_pedicel_loop(geo, p_lower, left_inner, right_inner, sternumrim5, bs5_1, bs5_2)

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

def _position_pedicel_opening_points(
    baseend0: hou.Point,
    headback0: hou.Point,
    sternumrim5: hou.Point,
    p_lower: hou.Point,
) -> None:
    p_end = baseend0.position()
    p_head = headback0.position()
    p_p = p_lower.position()
    p_sternum = sternumrim5.position()

    d = (p_end - p_p).length()

    target_height = p_end.y() - p_sternum.y()
    dy = p_head.y() - p_end.y()
    assert abs(dy) > 1e-6, "Expected non-zero y delta between baseend0 and headback0"
    t = target_height / dy
    new_end = p_end + t * (p_head - p_end)

    baseend0.setPosition(new_end)

    dir_sternum_to_orig_end = (p_end - p_sternum).normalized()
    p_lower.setPosition(p_sternum + dir_sternum_to_orig_end * d)

def _adjust_side_cepha_pedicel_points(
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

def _reconnect_sternum_pedicel_loop(
    geo: hou.Geometry,
    p_lower: hou.Point,
    left_inner: hou.Point,
    right_inner: hou.Point,
    sternumrim5: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
) -> None:
    p_prims = list(p_lower.prims())
    geo.deletePrims(p_prims, keep_points=True)

    f_left = fill_face(geo, [bs5_2, p_lower, sternumrim5, left_inner])
    f_left.setAttribValue("region", base_sops.Region.BASEBUFFERMEMBRANE)

    f_right = fill_face(geo, [bs5_1, p_lower, sternumrim5, right_inner], True)
    f_right.setAttribValue("region", base_sops.Region.BASEBUFFERMEMBRANE)


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


def _get_root() -> hou.SopNode:
    obj = hou.node("/obj")
    assert obj is not None
    return obj
