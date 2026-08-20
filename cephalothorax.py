import hou

from base import build as build_base
from chelicerae import build as build_chelicerae
from head import build as build_head
from helper import add_fuse, add_merge, add_output, propagate_parameters


def build(spider: hou.OpNode) -> hou.SopNode:
    cephalothorax = spider.createNode("subnet", "cephalothorax")
    parameters = _add_parameters(cephalothorax)

    base = build_base(cephalothorax)
    propagate_parameters(cephalothorax, base, skip_params=("membrane_ratio",))
    base.parm("membrane_ratio").set(cephalothorax.parm("membrane_ratio"))

    chelicerae = build_chelicerae(cephalothorax, base)
    propagate_parameters(cephalothorax, chelicerae, prefix="chelicerae_", skip_params=("membrane_ratio",))
    chelicerae.parm("membrane_ratio").set(cephalothorax.parm("membrane_ratio"))

    b_c_merge = add_merge(cephalothorax, "merge_base_and_chelicerae", base, chelicerae)
    b_c_fuse = add_fuse(cephalothorax, "fuse_base_and_chelicerae", b_c_merge)

    head = build_head(cephalothorax, b_c_fuse)
    propagate_parameters(cephalothorax, head, prefix="head_", skip_params=("membrane_ratio",))
    head.parm("membrane_ratio").set(cephalothorax.parm("membrane_ratio"))

    b_h_merge = add_merge(cephalothorax, "merge_base_and_head", b_c_fuse, head)
    b_h_fuse = add_fuse(cephalothorax, "fuse_base_and_head", b_h_merge)

    output = add_output(cephalothorax, "OUT_CEPHALOTHORAX", b_h_fuse)

    cephalothorax.layoutChildren()
    return cephalothorax


def _add_parameters(cephalothorax: hou.SopNode) -> hou.SopNode:
    templates = cephalothorax.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "membrane_ratio",
            "Membrane Ratio",
            1,
            default_value=(0.035,),
            min=0.0,
            min_is_strict=True,
        )
    )
    cephalothorax.setParmTemplateGroup(templates)
    return cephalothorax