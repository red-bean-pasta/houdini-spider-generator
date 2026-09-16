import hou

from houkit.noder import (
    add_fuse,
    add_merge,
    add_recalculate_normal,
    add_reload_button,
    sopify,
)
from houkit.parameterizer import add_float_parm, add_folder, promote_controls, promote_subnets
from .. import abdomen
from ..cephalothorax import build as build_cephalothorax
from ..leg import build as build_legs
from ..pedicel import build as build_pedicel
from . import topology


def build(parent: hou.OpNode) -> hou.SopNode:
    spider = _add_spider(parent)

    cephalothorax = build_cephalothorax(spider)
    opened_cepha = sopify(spider, cephalothorax, topology.open_cepha_pedicel)

    abdomen_node = abdomen.build(spider, opened_cepha)

    opened_abdomen = sopify(spider, abdomen_node, topology.open_abdomen_pedicel)
    merged_c_a = add_merge(spider, "merge_cephalothorax_and_abdomen", opened_cepha, opened_abdomen)

    pedicel = build_pedicel(spider, merged_c_a)
    merged_ca_p = add_merge(spider, "merge_main_and_pedicel", merged_c_a, pedicel)
    fused_ca_p = add_fuse(spider, "fuse_main_and_pedicel", merged_ca_p)
    removed_sockets = sopify(spider, fused_ca_p, topology.remove_coxa_sockets)

    legs = build_legs(spider, fused_ca_p)
    merged_all = add_merge(spider, "merge_main_and_legs", removed_sockets, legs)
    fused = add_fuse(spider, "fuse_main_and_legs", merged_all)

    recalculated = add_recalculate_normal(spider, "recalculate_normals", fused)
    _add_subdivide(spider, "subdivision", recalculated, depth=3)

    _propagate_subnets(spider)
    _propagate_controls(spider)

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
        "build",
    )
    add_float_parm(
        spider,
        "pedicel_opening_ratios",
        2,
        (0.5, 0.5),
        (0.0, 1.0),
        folder_label="Build",
        label="Pedicel Opening",
        help="X sets the side and upper opening proportion. Y places the lower opening between the base end and sternum rim.",
    )


def _propagate_subnets(spider: hou.OpNode) -> None:
    promote_subnets(spider, dest_group="Build")


def _propagate_controls(spider: hou.OpNode) -> None:
    add_folder(spider, "advanced")
    promote_controls(spider, depth=None, dest_group="Advanced",)


def _add_subdivide(
    parent: hou.OpNode,
    name: str,
    p_input: hou.SopNode,
    depth: int = 1,
) -> hou.SopNode:
    subdivide = parent.createNode("subdivide", name)
    subdivide.setInput(0, p_input)
    subdivide.parm("iterations").set(depth)
    return subdivide
