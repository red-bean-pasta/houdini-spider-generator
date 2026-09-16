import hou

from houkit.noder import add_fuse, add_output, add_reloadable_subnet
from houkit.parameterizer import add_float_parm, add_heading
from bases.attributes import basemaxillamembrane
from helper import points_from_geo, sopify_chain
from legs import topology

def add_parameters(subnet: hou.OpNode) -> None:
    add_heading(
        subnet,
        "Pedipalp",
    )
    add_float_parm(
        subnet,
        "pedipalp_coxa_length",
        default=0.8,
        min_max=(0.0, None),
        label="Coxa Length",
        help="Coxa length evaluated against front leg coxa length.",
    )
    add_float_parm(
        subnet,
        "pedipalp_segment_length_ratios",
        5,
        (0.17, 0.8, 0.4, 0.45, 0.4),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        label="Other Segment Lengths",
        help="One length ratio per post-coxa pedipalp segment, measured against pedipalp coxa length.",
    )
    add_float_parm(
        subnet,
        "endite_length_ratio",
        default=0.95,
        min_max=(0.0, None),
        label="Endite Length",
        help="Extension from the endite membrane attachment toward the coxa.",
    )


def prepare(
    geo: hou.Geometry
) -> set[hou.Point]:
    retained = points_from_geo(
        geo,
        basemaxillamembrane(1),
        basemaxillamembrane(2),
        basemaxillamembrane(3),
        basemaxillamembrane(4),
    )
    return set(retained)


def build(
    parent: hou.SopNode,
    input_node: hou.SopNode,
) -> hou.SopNode:
    pedipalp = add_reloadable_subnet(parent, "pedipalp")
    pedipalp.setInput(0, input_node)
    _add_controls(pedipalp)

    cleaned_up = sopify_chain(
        pedipalp,
        pedipalp.indirectInputs()[0],
        (
            topology.remove_noise_points,
            topology.build_basic,
            topology.trim_bottom_side_length,
            topology.position_basic,
            topology.delete_start_coxa_supports,
            topology.prepare_coxa_base_trapezoid,
            topology.fill_bottom_right_face,
            topology.fill_back_face,
            topology.fill_top_face,
            topology.add_front_upper_face,
            topology.add_front_loop_faces,
            topology.add_maxilla_quads,
            topology.fill_maxilla_faces,
            topology.remove_pedipalp_tmp_attributes,
        ),
    )
    fused = add_fuse(pedipalp, "fuse_sockets", cleaned_up)
    add_output(pedipalp, "OUT_PEDIPALP", fused)
    pedipalp.layoutChildren()
    return pedipalp


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    add_float_parm(
        control,
        "endite_buffer_ratios",
        size=2,
        default=(0.4, 0.1),
        min_max=(0.0, 1.0),
        label="Endite Buffer",
        help="X positions the buffer across the coxa end; Y sets its lengthwise reach.",
    )
    add_float_parm(
        control,
        "endite_surface_size_ratio",
        default=0.06,
        min_max=(0.0, 1.0),
        label="Endite Surface Size",
        help="Size of the added endite surface faces.",
    )
    return control
