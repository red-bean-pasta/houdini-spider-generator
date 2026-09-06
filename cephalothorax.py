import hou

import base_sops
from base import build as build_base
from chelicerae import build as build_chelicerae
from head import build as build_head
from utilities.common import add_float_param
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_output,
    add_outside_recalculation,
    add_reloadable_subnet,
    propagate_parameters,
)


def build(spider: hou.OpNode) -> hou.SopNode:
    cephalothorax = add_reloadable_subnet(spider, "cephalothorax")
    _add_parameters(cephalothorax)

    base = build_base(cephalothorax)
    _link_membrane_ratio(cephalothorax, base)

    head = build_head(cephalothorax, base)
    _link_membrane_ratio(cephalothorax, head)

    b_h_merge = add_merge(cephalothorax, "merge_base_and_head", base, head)
    b_h_fuse = add_fuse(cephalothorax, "fuse_base_and_head", b_h_merge)

    chelicerae = build_chelicerae(cephalothorax, b_h_fuse)
    _link_membrane_ratio(cephalothorax, chelicerae)

    all_merge = add_merge(cephalothorax, "merge_head_and_chelicerae", b_h_fuse, chelicerae)
    all_fuse = add_fuse(cephalothorax, "fuse_head_and_chelicerae", all_merge)

    recalculate = add_outside_recalculation(cephalothorax, "recalculate_normals", all_fuse)
    positioned = _position_cephalothorax(cephalothorax, recalculate)

    _ = add_output(cephalothorax, "OUT_CEPHALOTHORAX", positioned)

    cephalothorax.layoutChildren()
    return cephalothorax


def _add_parameters(cephalothorax: hou.SopNode) -> None:
    add_float_param(
        cephalothorax,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )


def _link_membrane_ratio(parent: hou.SopNode, child: hou.SopNode) -> None:
    propagate_parameters(parent, child, skip_params="membrane_ratio")
    child.parm("membrane_ratio").set(parent.parm("membrane_ratio"))


def _position_cephalothorax(parent: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    position = parent.createNode("xform", "position_cephalothorax")
    position.setInput(0, source)
    pattern = f'pointpattern(0, "@id={base_sops.baseend(0)}")'
    for axis_index, axis_name in enumerate(("tx", "ty", "tz")):
        position.parm(axis_name).setExpression(f'0 - point(0, {pattern}, "P", {axis_index})')
    return position
