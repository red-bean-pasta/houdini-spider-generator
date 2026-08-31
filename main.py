import hou

import abdomen
import base_sops
import head
import sternum_sops
from abdomen import build as build_abdomen
from cephalothorax import build as build_cephalothorax
from leg import build as build_legs
from pedicel import build as build_pedicel
from utilities.helper import points_by_id
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_outside_recalculation,
    add_reload_button,
    sopify,
)


def cephapedicelupper() -> str:
    return "cephapedicelupper"
def cephapedicellower() -> str:
    return sternum_sops.sternumrim(5)
def cephapedicelright() -> str:
    return "cephapedicelright"
def cephapedicelleft() -> str:
    return "cephapedicelleft"


def build() -> hou.SopNode:
    spider = _add_spider()

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

    membrane_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == "basepedicelmembrane"
    ]
    assert len(membrane_prims) == 1, f"Expected 1 basepedicelmembrane prim, got {len(membrane_prims)}"
    mem_prim = membrane_prims[0]

    p_point = None
    for pt in mem_prim.points():
        pt_id = pt.stringAttribValue("id")
        if pt_id == sternum_sops.sternumrim(5):
            continue
        if abs(pt.position().x()) < 1e-4:
            p_point = pt
            pt.setAttribValue("id", cephapedicelupper())
        elif pt.position().x() > 0:
            pt.setAttribValue("id", cephapedicelright())
        else:
            pt.setAttribValue("id", cephapedicelleft())

    assert p_point is not None, "Expected upper p point in basepedicelmembrane"

    p_end = baseend0.position()
    p_head = headback0.position()
    p_p = p_point.position()

    d = (p_end - p_p).length()
    line_vec = p_head - p_end
    line_dir = line_vec.normalized()

    target_height = p_end.y() - sternumrim5.position().y()
    dy = p_head.y() - p_end.y()
    assert abs(dy) > 1e-6, "Expected non-zero y delta between baseend0 and headback0"
    t = target_height / dy
    new_end = p_end + t * line_vec

    p_point.setPosition(new_end)
    baseend0.setPosition(new_end + line_dir * d)

    geo.deletePrims(membrane_prims, keep_points=True)


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
