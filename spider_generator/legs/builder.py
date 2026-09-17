import hou

from houkit.noder import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from houkit.parameterizer import add_float_parm, add_heading
from . import topology
from .pedipalp import builder


def build(
    spider: hou.SopNode,
    base: hou.SopNode,
) -> hou.SopNode:
    legs = add_reloadable_subnet(spider, "legs")
    legs.setInput(0, base)
    _add_parameters(legs)
    _add_controls(legs)

    prepared = sopify(legs, legs.indirectInputs()[0], topology.prepare_attributed_data)
    extracted = sopify(legs, prepared, topology.extract_right_coxa)
    extruded = sopify(legs, extracted, topology.extrude_legs)

    pedipalp_built = builder.build(legs, extracted)
    merged_legs = add_merge(legs, "merge_legs_and_pedipalp", extruded, pedipalp_built)

    cleaned = sopify(legs, merged_legs, topology.remove_tmp_attributes)
    fused = add_fuse(legs, "fuse_sockets", cleaned)
    mirrored = add_mirror(legs, "mirror_left_legs", fused, (1, 0, 0), True, False)
    add_output(legs, "OUT_LEGS", mirrored)

    legs.layoutChildren()
    return legs


def _add_parameters(legs: hou.OpNode) -> None:
    add_heading(legs, "Basic")
    add_float_parm(
        legs,
        "min_flex_angles",
        6,
        (180, 200, 30, 95, 150, 170),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Minimum Flex Angles",
        help="One minimum flex angle per post-coxa segment joint.",
    )
    add_float_parm(
        legs,
        "max_yaw_angles",
        6,
        (25, 0, 0, 0, 0, 20),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Maximum Yaw Angles",
        help="One maximum yaw angle per post-coxa segment joint.",
    )
    add_heading(legs, "Front Leg")
    add_float_parm(
        legs,
        "front_coxa_width_length_ratios",
        2,
        (0.75, 1.2),
        (0.0, None),
        label="Front Coxa Width / Length",
        help="X scales coxa width and Y scales coxa length from the front socket width.",
    )
    add_float_parm(
        legs,
        "front_segment_length_ratios",
        6,
        (0.33, 1.5, 0.9, 1.2, 1, 0.7),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Front Leg Lengths",
        help="One length ratio per post-coxa segment, measured against front coxa length.",
    )
    add_heading(legs, "Other Main Legs")
    add_float_parm(
        legs,
        "other_leg_width_ratios",
        3,
        (0.8, 0.7, 0.8),
        (0.0, None),
        label="Other Leg Widths",
        help="Coxa-width scale for legs 2–4 relative to the front coxa.",
    )
    add_float_parm(
        legs,
        "other_leg_length_ratios",
        3,
        (0.88, 0.9, 1.1),
        (0.0, None),
        label="Other Leg Lengths",
        help="Coxa-length scale for legs 2–4 relative to the front coxa.",
    )
    builder.add_parameters(legs)


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_parm(
        control,
        "joint_support_loop_ratio",
        1,
        0.015,
        (0.0, 1.0),
        label="Joint Support Loop",
        help="Inset width at coxa sockets and segment joints, relative to coxa width.",
    )
    add_float_parm(
        control,
        "coxa_trochanter_height_ratio",
        1,
        0.63,
        (0.0, None),
        label="Coxa-Trochanter Height",
        help="Height-to-width proportion of the trochanter segment.",
    )
    add_float_parm(
        control,
        "other_segment_height_ratio",
        1,
        1.15,
        (0.0, None),
        label="Other Segment Height",
        help="Height-to-width proportion of post-trochanter segments.",
    )
    add_float_parm(
        control,
        "segment_bulge_bias_ratio",
        1,
        0.5,
        (0.0, None),
        label="Segment Bulge Bias",
        help="Moves the segment’s fullest area between its upper and lower sides.",
    )
    add_float_parm(
        control,
        "segment_taper_ratios",
        2,
        (0.98, 0.875),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Segment Taper",
        help="X sets taper along a segment; Y sets the size change at each joint.",
    )
    add_float_parm(
        control,
        "joint_clearance_limits",
        2,
        (1.0, 5.0),
        (0.0, 45.0),
        hou.parmNamingScheme.Base1,
        label="Joint Clearance Limits",
        help="X is minimum membrane separation in scene units. Y is minimum flex angle; keep it strictly between 0° and 45°.",
    )
    add_float_parm(
        control,
        "tarsus_wedge_angle",
        1,
        45.0,
        (-60.0, 60.0),
        label="Tarsus Wedge",
        help="Terminal tarsus wedge angle.",
    )
    add_float_parm(
        control,
        "coxa_start_wedge_angle",
        1,
        45.0,
        (0.0, 90.0),
        label="Coxa Start Wedge",
        help="Wedge angle used to place the coxa socket's lower support.",
    )
    return control
