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
from ..helper import rename_left_ids_node, sopify_chain
from . import topology


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    head = add_reloadable_subnet(cephalothorax, "head")
    head.setInput(0, base)
    add_parameters(head)

    source = head.indirectInputs()[0]
    base_rim = sopify(head, source, topology.extract_base_rim)
    base_points = sopify(head, source, topology.extract_work_base)
    regions = sopify_chain(
        head,
        base_points,
        (
            topology.add_corners_half,
            topology.add_head_dent,
            topology.curve_lip,
            topology.fill_back_loop_faces,
            topology.fill_support_loop_faces,
            topology.fill_side_faces,
            topology.add_side_regions,
        ),
    )
    mirrored = add_mirror(head, "left_mirror", regions, (1, 0, 0), True, False)
    faces = sopify(head, mirrored, rename_left_ids_node)

    merged = add_merge(head, "merge_base_rim", base_rim, faces)
    fused = add_fuse(head, "fuse_base_rim", merged)
    cleaned = sopify_chain(
        head,
        fused,
        (topology.inset_base_support_loop, topology.extrude_lip, topology.cleanup),
    )
    add_output(head, "OUT_HEAD", cleaned)
    head.layoutChildren()
    return head


def add_parameters(head: hou.SopNode) -> None:
    add_float_parm(
        head,
        "height_ratio",
        1,
        0.375,
        (0.0, None),
        label="Top Height",
        help="Top-face height relative to the base-to-chelicerae reference span.",
    )
    add_float_parm(
        head,
        "top_width_length_ratios",
        2,
        (1.0, 0.4),
        (0.0, None),
        naming_scheme=hou.parmNamingScheme.XYZW,
        label="Top Width / Length",
        help="X sets top width. Y sets the top face’s front-to-back length and flatness.",
    )
    add_float_parm(
        head,
        "top_face_offset_ratio",
        1,
        0.0,
        label="Top Face Offset",
        help="Lengthwise skew of the top face relative to base length.",
    )
    add_float_parm(
        head,
        "top_support_loop_ratios",
        2,
        (0.2, 0.5),
        naming_scheme=hou.parmNamingScheme.Base1,
        label="Top Support Loop",
        help="X adjusts the forward portion; Y adjusts the rear portion between the top face and base-side loop.",
    )
    add_float_parm(
        head,
        "chelicerae_height_ratio",
        1,
        0.35,
        (0.0, None),
        label="Chelicerae Height",
        help="Vertical placement of the upper chelicerae line relative to the base.",
    )
    add_float_parm(
        head,
        "lip_extrusion_ratio",
        2,
        (5.0, 1.0),
        (-10.0, 10.0),
        naming_scheme=hou.parmNamingScheme.XYZW,
        label="Lip Extrusion",
        help="X is lengthwise extrusion; Y is vertical extrusion.",
    )
    add_float_parm(
        head,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )
