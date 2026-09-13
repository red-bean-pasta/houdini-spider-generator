import hou

from . import base_sops
from .base import build as build_base
from .chelicerae import build as build_chelicerae
from .head import build as build_head
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_output,
    add_outside_recalculation,
    add_reloadable_subnet,
    propagate_subnets,
)


def build(spider: hou.OpNode) -> hou.SopNode:
    cephalothorax = add_reloadable_subnet(spider, "cephalothorax")

    base = build_base(cephalothorax)

    head = build_head(cephalothorax, base)

    b_h_merge = add_merge(cephalothorax, "merge_base_and_head", base, head)
    b_h_fuse = add_fuse(cephalothorax, "fuse_base_and_head", b_h_merge)

    chelicerae = build_chelicerae(cephalothorax, b_h_fuse)

    recalculate = add_outside_recalculation(cephalothorax, "recalculate_normals", chelicerae)
    positioned = _position_cephalothorax(cephalothorax, recalculate)

    _ = add_output(cephalothorax, "OUT_CEPHALOTHORAX", positioned)

    _propagate_subnets(cephalothorax)
    cephalothorax.layoutChildren()
    return cephalothorax


def _propagate_subnets(cephalothorax: hou.SopNode) -> None:
    propagate_subnets(cephalothorax)


def _position_cephalothorax(parent: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    position = parent.createNode("xform", "position_cephalothorax")
    position.setInput(0, source)
    pattern = f'pointpattern(0, "@id={base_sops.baseend(0)}")'
    for axis_index, axis_name in enumerate(("tx", "ty", "tz")):
        position.parm(axis_name).setExpression(f'0 - point(0, {pattern}, "P", {axis_index})')
    return position
