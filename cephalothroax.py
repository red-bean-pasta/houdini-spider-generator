import hou

from base import build as build_base
from chelicerae import build as build_chelicerae
from head import build as build_head
from helper import add_fuse, add_merge, add_output, propagate_parameters


def build(spider: hou.OpNode) -> hou.SopNode:
    cephalothroax = spider.createNode("subnet", "cephalothroax")
    parameters = _add_parameters(cephalothroax)

    base = build_base(cephalothroax)
    propagate_parameters(cephalothroax, base, skip_params=("membrane_ratio",))
    base.parm("membrane_ratio").set(cephalothroax.parm("membrane_ratio"))

    chelicerae = build_chelicerae(cephalothroax, base)
    propagate_parameters(cephalothroax, chelicerae, prefix="chelicerae_", skip_params=("membrane_ratio",))
    chelicerae.parm("membrane_ratio").set(cephalothroax.parm("membrane_ratio"))

    b_c_merge = add_merge(cephalothroax, "merge_base_and_chelicerae", base, chelicerae)
    b_c_fuse = add_fuse(cephalothroax, "fuse_base_and_chelicerae", b_c_merge)

    head = build_head(cephalothroax, b_c_fuse)
    propagate_parameters(cephalothroax, head, prefix="head_", skip_params=("membrane_ratio",))
    head.parm("membrane_ratio").set(cephalothroax.parm("membrane_ratio"))

    b_h_merge = add_merge(cephalothroax, "merge_base_and_head", b_c_fuse, head)
    b_h_fuse = add_fuse(cephalothroax, "fuse_base_and_head", b_h_merge)

    output = add_output(cephalothroax, "OUT_CEPHALOTHROAX", b_h_fuse)

    cephalothroax.layoutChildren()
    return cephalothroax


def _add_parameters(cephalothroax: hou.SopNode) -> hou.SopNode:
    templates = cephalothroax.parmTemplateGroup()
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
    cephalothroax.setParmTemplateGroup(templates)
    return cephalothroax