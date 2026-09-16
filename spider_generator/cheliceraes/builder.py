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
from ..helper import sopify_chain
from . import topology


def build(cephalothorax: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    chelicerae = add_reloadable_subnet(cephalothorax, "chelicerae")
    chelicerae.setInput(0, source)
    add_parameters(chelicerae)

    right_membrane = sopify_chain(
        chelicerae,
        chelicerae.indirectInputs()[0],
        (topology.build_geometry, topology.inset_flaps, topology.classify_after_inset, topology.prepare_extrusion, topology.remove_left_membrane),
    )
    adjusted_start_section = sopify_chain(
        chelicerae,
        right_membrane,
        (topology.add_start_membrane, topology.inset_start_membrane, topology.adjust_start_section_left),
    )
    lower_middle_section = sopify_chain(
        chelicerae,
        adjusted_start_section,
        (topology.add_end_section, topology.add_middle_section, topology.add_upper_middle_section, topology.add_lower_middle_section),
    )
    cut_tube = sopify_chain(
        chelicerae,
        lower_middle_section,
        (topology.connect_sections, topology.remove_middle_face, topology.middle_loop_cut),
    )
    adjusted_right = sopify_chain(
        chelicerae,
        cut_tube,
        (topology.merge_membrane_curves, topology.adjust_start_membrane_curve, topology.adjust_right_membrane_width),
    )
    clamped_start = sopify_chain(
        chelicerae,
        adjusted_right,
        (
            topology.adjust_head_chelicerae_depth,
            topology.inset_chelicerae_support_loop,
            topology.add_start_membrane_support_loops,
            topology.add_start_section_support_loops,
        ),
    )

    mirrored = add_mirror(chelicerae, "mirror_left_chelicerae", clamped_start, (1, 0, 0), True, True)
    renamed = sopify(chelicerae, mirrored, topology.rename_left_ids)

    fuse_mirrors = add_fuse(chelicerae, "fuse_mirrors", renamed)
    all_merge = add_merge(chelicerae, "merge_head_and_chelicerae", chelicerae.indirectInputs()[0], fuse_mirrors)
    all_fuse = add_fuse(chelicerae, "fuse_head_and_chelicerae", all_merge)
    deduplicated = sopify(chelicerae, all_fuse, topology.deduplicate_base_faces)

    add_output(chelicerae, "OUT_CHELICERAE", deduplicated)
    chelicerae.layoutChildren()
    return chelicerae


def add_parameters(chelicerae: hou.SopNode) -> None:
    add_float_parm(
        chelicerae,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )
    add_heading(
        chelicerae,
        "End Section",
    )
    add_float_parm(
        chelicerae,
        "end_section_ratio",
        2,
        (0.25, 0.25),
        (0.0, None),
        label="End Section Size",
        help="X scales width and Y scales height relative to the start section.",
    )
    add_float_parm(
        chelicerae,
        "end_section_offset",
        3,
        (0.2, 3.15, 1.25),
        label="End Section Offset",
        help="Offsets the end section in its local width, height, and length directions.",
    )
    add_float_parm(
        chelicerae,
        "end_section_rotation",
        2,
        (-90.0, 0.0),
        label="End Section Rotation",
        help="X and Y set the two local rotation directions.",
    )
    add_heading(
        chelicerae,
        "Middle Section",
    )
    add_float_parm(
        chelicerae,
        "middle_section_ratio",
        2,
        (1.0, 1.2),
        (0.0, None),
        label="Middle Section Size",
        help="X scales width and Y scales height relative to the start section.",
    )
    add_float_parm(
        chelicerae,
        "middle_section_offset",
        2,
        (0.1, 2.25),
        label="Middle Section Offset",
        help="Moves the middle section through its local width and length plane.",
    )
    add_float_parm(
        chelicerae,
        "middle_section_height_ratio",
        1,
        0.4,
        (0.0, 1.0),
        label="Middle Section Height",
        help="Vertical placement between the start and end sections.",
    )
