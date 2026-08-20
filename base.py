import hou

import base_sops
from hom_helper import sopify
from sop_helper import add_fuse, add_merge, add_output, propagate_parameters
from sternum import build as build_sternum


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    base = cephalothorax.createNode("subnet", "base")
    _add_parameters(base)

    sternum = build_sternum(base)
    propagate_parameters(base, sternum, prefix="sternum_")

    rim = sopify(base, sternum, base_sops.extract_sternum_rim)
    flaps = sopify(base, rim, base_sops.build_coxa_flaps)
    fuse_flaps = add_fuse(base, "fuse_coxa_flaps", flaps)
    connected = sopify(base, fuse_flaps, base_sops.connect_side_flaps)
    fuse_connected = add_fuse(base, "fuse_connected_side_flaps", connected)
    cleaned_connected = sopify(base, fuse_connected, base_sops.cleanup_connected_side_flap_ids)

    rotated = sopify(base, cleaned_connected, base_sops.rotate_coxa_flaps)
    adjusted = sopify(base, rotated, base_sops.adjust_frontest_line)

    maxilla = sopify(base, adjusted, base_sops.fill_maxilla)
    pedicel = sopify(base, maxilla, base_sops.fill_pedicel_membrane)

    fused_pedicel = add_fuse(base, "fuse_pedicel_membrane", pedicel)
    membrane = _inset_membrane(base, fused_pedicel)

    merge = add_merge(base, "merge_sternum_and_coxa", membrane, sternum)
    fuse = add_fuse(base, "fuse_sternum_and_coxa", merge)
    add_output(base, "OUT_BASE", fuse)

    base.layoutChildren()
    return base


def _add_parameters(base: hou.SopNode) -> hou.SopNode:
    templates = base.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "coxa_width_ratio",
            "Coxa Width Ratio",
            2,
            default_value=(1.0, 1.2),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "coxa_depth_ratio",
            "Coxa Depth Ratio",
            1,
            default_value=(0.35,),
            min=0.0,
            min_is_strict=True,
        )
    )
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
    base.setParmTemplateGroup(templates)
    return base


def _inset_membrane(parent: hou.SopNode, coxa: hou.SopNode) -> hou.SopNode:
    attr_prepared = sopify(parent, coxa, base_sops.prepare_membrane_attributes)
    front_prepared = sopify(parent, attr_prepared, base_sops.prepare_front_membrane)
    maxilla_prepared = sopify(parent, front_prepared, base_sops.prepare_maxilla_membrane)
    side_prepared = sopify(parent, maxilla_prepared, base_sops.prepare_side_membrane)
    side_split = sopify(parent, side_prepared, base_sops.identify_side_inset_split)

    side = parent.createNode("polyextrude", "inset_side_membrane")
    side.setInput(0, side_split)
    side.parm("group").set("@tmp_inset_region=side_flap")
    side.parm("splittype").set(1)
    side.parm("usesplitgroup").set(1)
    side.parm("splitgroup").set("tmp_side_split")
    side.parm("inset").setExpression('ch("../membrane_ratio")')
    side.parm("uselocalinsetscaleattrib").set(1)
    side.parm("localinsetscaleattrib").set("tmp_insetscale")

    front = parent.createNode("polyextrude", "inset_front_membrane")
    front.setInput(0, side)
    front.parm("group").set("@tmp_inset_region=front_flap")
    front.parm("splittype").set(1)
    front.parm("inset").setExpression('ch("../membrane_ratio")')
    front.parm("uselocalinsetscaleattrib").set(1)
    front.parm("localinsetscaleattrib").set("tmp_insetscale")

    maxilla = parent.createNode("polyextrude", "inset_maxilla")
    maxilla.setInput(0, front)
    maxilla.parm("group").set("@tmp_inset_region=maxilla")
    maxilla.parm("splittype").set(0)
    maxilla.parm("inset").setExpression('ch("../membrane_ratio")')
    maxilla.parm("uselocalinsetscaleattrib").set(1)
    maxilla.parm("localinsetscaleattrib").set("tmp_insetscale")

    cleanup = sopify(parent, maxilla, base_sops.cleanup_temp_attributes)