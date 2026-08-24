import hou

import sternum_sops
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    sternum = add_reloadable_subnet(cephalothorax, "sternum")
    parameters = _add_parameters(sternum)
    control = _add_controls(sternum)

    half = sopify(sternum, None, sternum_sops.left_half)
    midpoints = sopify(sternum, half, sternum_sops.add_midpoints)

    mirror = add_mirror(sternum, "right_mirror", midpoints, (1, 0, 0), True, False)
    point_ids = sopify(sternum, mirror, sternum_sops.add_point_ids)

    spine = sopify(sternum, point_ids, sternum_sops.add_center_spine)

    merge = add_merge(sternum, "merge_boundary_and_spine", point_ids, spine)
    fuse = add_fuse(sternum, "fuse_center_points", merge)

    depth = sopify(sternum, fuse, sternum_sops.descend_sternum_spine)
    faces = sopify(sternum, depth, sternum_sops.build_sternum_faces)
    regions = sopify(sternum, faces, sternum_sops.add_prim_regions)

    output = add_output(sternum, "OUT_STERNUM", regions)
    sternum.layoutChildren()
    return sternum


def _add_parameters(sternum: hou.SopNode) -> hou.SopNode:
    templates = sternum.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "width_length_ratio",
            "Width Length Ratio",
            3,
            default_value=(1.0, 2.0, 1.825),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "top_width_ratio",
            "Top Width Ratio",
            1,
            default_value=(0.5,),
            min=0.0,
            max=1.0,
            min_is_strict=True,
            max_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "width_depth_ratio",
            "Width Depth Ratio",
            1,
            default_value=(0.5,),
            min=0.0,
            min_is_strict=True,
        )
    )
    sternum.setParmTemplateGroup(templates)
    return sternum


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    templates = control.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "half_width",
            "Half Width",
            1,
            default_value=(100.0,)
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "leg_angle",
            "Leg Angle",
            1,
            default_value=(165.0,),
            min=0.0,
            max=180.0,
            min_is_strict=True,
            max_is_strict=True,
        )
    )
    control.setParmTemplateGroup(templates)

    return control
