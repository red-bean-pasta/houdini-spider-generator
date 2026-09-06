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
    propagate_parameters(cephalothorax, base, skip_params="membrane_ratio")
    base.parm("membrane_ratio").set(cephalothorax.parm("membrane_ratio"))

    chelicerae = build_chelicerae(cephalothorax, base)
    propagate_parameters(cephalothorax, chelicerae, skip_params="membrane_ratio")
    chelicerae.parm("membrane_ratio").set(cephalothorax.parm("membrane_ratio"))

    b_c_merge = add_merge(cephalothorax, "merge_base_and_chelicerae", base, chelicerae)
    b_c_fuse = add_fuse(cephalothorax, "fuse_base_and_chelicerae", b_c_merge)

    head = build_head(cephalothorax, b_c_fuse)
    propagate_parameters(cephalothorax, head, skip_params="membrane_ratio")
    head.parm("membrane_ratio").set(cephalothorax.parm("membrane_ratio"))

    b_h_merge = add_merge(cephalothorax, "merge_base_and_head", b_c_fuse, head)
    b_h_fuse = add_fuse(cephalothorax, "fuse_base_and_head", b_h_merge)

    recalculate = add_outside_recalculation(cephalothorax, "recalculate_normals", b_h_fuse)
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


def _position_cephalothorax(parent: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    position = parent.createNode("xform", "position_cephalothorax")
    position.setInput(0, source)
    pattern = f'pointpattern(0, "@id={base_sops.baseend(0)}")'
    position.parm("tx").setExpression(f'0 - point(0, {pattern}, "P", 0)')
    position.parm("ty").setExpression(f'0 - point(0, {pattern}, "P", 1)')
    position.parm("tz").setExpression(f'0 - point(0, {pattern}, "P", 2)')
    return position
