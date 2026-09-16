import hou

from houkit.noder import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from houkit.parameterizer import add_float_parm
from ..helper import sopify_chain
from . import topology


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    sternum = add_reloadable_subnet(cephalothorax, "sternum")
    add_parameters(sternum)
    add_controls(sternum)

    midpoints = sopify_chain(sternum, None, (topology.left_half, topology.add_midpoints))

    mirror = add_mirror(sternum, "right_mirror", midpoints, (1, 0, 0), True, False)
    point_ids = sopify(sternum, mirror, topology.add_point_ids)

    spine = sopify(sternum, point_ids, topology.add_center_spine)

    merge = add_merge(sternum, "merge_boundary_and_spine", point_ids, spine)
    fuse = add_fuse(sternum, "fuse_center_points", merge)

    buffered = sopify_chain(
        sternum,
        fuse,
        (
            topology.build_sternum_faces,
            topology.inset_spine_loop,
            topology.elevate_spine_loop,
            topology.descend_sternum_spine,
            topology.add_prim_regions,
            topology.outset_sternum_loop,
        ),
    )

    _ = add_output(sternum, "OUT_STERNUM", buffered)
    sternum.layoutChildren()
    return sternum


def add_parameters(sternum: hou.SopNode) -> None:
    add_float_parm(
        sternum,
        "front_back_length_ratios",
        2,
        (1.85, 1.6),
        (0.0, None),
        label="Front / Back Length",
        help="X is anterior length; Y is posterior length. Both are relative to sternum half-width.",
    )
    add_float_parm(
        sternum,
        "front_width_ratio",
        1,
        0.455,
        (0.0, 1.0),
        label="Front Width",
        help="Anterior width relative to the sternum’s widest span.",
    )
    add_float_parm(
        sternum,
        "spine_depth_ratio",
        1,
        0.25,
        (0.0, None),
        label="Spine Depth",
        help="Maximum center-spine depression relative to sternum half-width.",
    )
    add_float_parm(
        sternum,
        "spine_descent_power",
        1,
        0.75,
        (0.0, None),
        label="Spine Descent",
        help="1 is linear; lower values deepen sooner and higher values deepen later.",
    )
    add_float_parm(
        sternum,
        "spine_loop_position_ratio",
        2,
        (0.8, 0.35),
        (0.0, 1.0),
        label="Spine Loop Position",
        help=(
            "X is position from center spine toward rim (at 1, intermediate loop is omitted). "
            "spine_loop_position_ratioy is for elevation relative to spine depth."
        ),
    )
    add_float_parm(
        sternum,
        "membrane_ratio",
        1,
        0.02,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )


def add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_parm(
        control,
        "half_width",
        1,
        100.0,
        label="Half Width",
        help="Scene-unit half-width that establishes the sternum scale.",
    )
    add_float_parm(
        control,
        "posterior_outline_angle",
        1,
        150.0,
        (0.0, 180.0),
        label="Posterior Outline Angle",
        help="Interior angle that shapes the rear sternum outline.",
    )
    return control
