import hou

import sternum_sops
from utilities.common import add_float_param
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
    _add_parameters(sternum)
    _add_controls(sternum)

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
    buffered = sternum_sops.extrude_sternum_loop(sternum, regions)

    _ = add_output(sternum, "OUT_STERNUM", buffered)
    sternum.layoutChildren()
    return sternum


def _add_parameters(sternum: hou.SopNode) -> None:
    add_float_param(
        sternum,
        "width_length_ratio",
        2,
        (2.0, 1.825),
        (0.0, None),
        help="Front (anterior) length ratio and back (posterior) length ratio relative to half-width",
    )
    add_float_param(
        sternum,
        "top_width_ratio",
        1,
        0.5,
        (0.0, 1.0),
    )
    add_float_param(
        sternum,
        "width_depth_ratio",
        1,
        0.5,
        (0.0, None),
    )
    add_float_param(
        sternum,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_param(
        control,
        "half_width",
        1,
        100.0,
    )
    add_float_param(
        control,
        "leg_angle",
        1,
        165.0,
        (0.0, 180.0),
    )
    return control
