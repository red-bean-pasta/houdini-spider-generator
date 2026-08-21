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
    flap_regions = sopify(base, flaps, base_sops.add_flap_regions)
    fuse_flaps = add_fuse(base, "fuse_coxa_flaps", flap_regions)
    connected = sopify(base, fuse_flaps, base_sops.connect_side_flaps)
    fuse_connected = add_fuse(base, "fuse_connected_side_flaps", connected)
    cleaned_connected = sopify(base, fuse_connected, base_sops.cleanup_connected_side_flap_ids)

    rotated = sopify(base, cleaned_connected, base_sops.rotate_coxa_flaps)
    adjusted = sopify(base, rotated, base_sops.adjust_frontest_line)

    maxilla = sopify(base, adjusted, base_sops.fill_maxilla)
    pedicel = sopify(base, maxilla, base_sops.fill_pedicel_membrane)

    fused_pedicel = add_fuse(base, "fuse_pedicel_membrane", pedicel)
    membrane = base_sops.inset_membrane(base, fused_pedicel)

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

