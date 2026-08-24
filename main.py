import hou

import abdomen
import base_sops
import head
from abdomen import build as build_abdomen
from cephalothorax import build as build_cephalothorax
from utility.helper import points_by_attribute, sopify
from pedicel import build as build_pedicel
from sop_helper import add_merge, add_fuse


def build() -> hou.SopNode:
    spider = _add_spider()

    cephalothorax = build_cephalothorax(spider)
    moved_cepha = sopify(spider, cephalothorax, _position_cephalothorax)

    abdomen_node = build_abdomen(spider, cephalothorax)

    opened_cepha = sopify(spider, moved_cepha, _open_cepha_pedicel)
    opened_cepha.setInput(1, abdomen_node)

    merged_c_a = add_merge(spider, "merge_cephalothorax_and_abdomen", opened_cepha, abdomen_node)
    pedicel = build_pedicel(spider, merged_c_a)

    merged_ca_p = add_merge(spider, "merge_main_and_pedicel", merged_c_a, pedicel)
    fused = add_fuse(spider, "fuse_main_and_pedicel", merged_ca_p)
    fused.setDisplayFlag(True)
    fused.setRenderFlag(True)
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

    return spider


def _position_cephalothorax(cephalothorax: hou.SopNode) -> None:
    geo: hou.Geometry = cephalothorax.geometry()
    points = points_by_attribute(geo)
    end = points[base_sops.baseend(0)].position()
    offset = hou.Vector3() - end
    for point in geo.points():
        point.setPosition(point.position() + offset)


def _open_cepha_pedicel(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    abdomen_input = node.inputs()[1]; assert abdomen_input is not None, "Expected abdomen connected as input 1"
    ab_points = points_by_attribute(abdomen_input.geometry())
    v1 = ab_points.get(abdomen.abdomenverticalrim(1)); assert v1 is not None, "Expected abdomenverticalrim1 point in abdomen"
    new_y = v1.position().y()

    cepha_points = points_by_attribute(geo)
    baseend0 = cepha_points.get(base_sops.baseend(0)); assert baseend0 is not None, "Expected baseend0 point in cephalothorax"
    headback0 = cepha_points.get(head.headback(0)); assert headback0 is not None, "Expected headback0 point in cephalothorax"

    p_end = baseend0.position()
    p_head = headback0.position()
    dy = p_head.y() - p_end.y(); assert abs(dy) > 1e-6, "Expected non-zero y delta between baseend0 and headback0"
    t = (new_y - p_end.y()) / dy
    new_end = p_end + t * (p_head - p_end)

    membrane_prims = [
        prim for prim in geo.prims()
        if prim.stringAttribValue("region") == "basepedicelmembrane"
    ]
    geo.deletePrims(membrane_prims, keep_points=True)

    baseend0.setPosition(new_end)


def _get_root() -> hou.SopNode:
    obj = hou.node("/obj")
    assert obj is not None
    return obj


if __name__ == "__main__":
    build()
