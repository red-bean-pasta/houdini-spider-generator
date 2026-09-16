import hou

from . import base_sops
from .helper import sopify_chain
from .sternum import build as build_sternum
from houkit.noder import (
    add_fuse,
    add_merge,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from houkit.parameterizer import add_float_parm, promote_subnets


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    base = add_reloadable_subnet(cephalothorax, "base")
    _add_parameters(base)

    sternum = build_sternum(base)

    flap_regions = sopify_chain(
        base,
        sternum,
        (base_sops.extract_sternum_rim, base_sops.build_coxa_flaps, base_sops.add_flap_regions),
    )
    fuse_flaps = add_fuse(base, "fuse_coxa_flaps", flap_regions)
    connected = sopify_chain(
        base,
        fuse_flaps,
        (base_sops.connect_side_flaps, base_sops.adjust_front_and_end_flaps),
    )
    fuse_connected = add_fuse(base, "fuse_connected_side_flaps", connected)
    pedicel = sopify_chain(
        base,
        fuse_connected,
        (
            base_sops.cleanup_connected_side_flap_ids,
            base_sops.rotate_coxa_flaps,
            base_sops.adjust_frontest_line,
            base_sops.fill_maxilla,
            base_sops.fill_pedicel_membrane,
        ),
    )

    fused_pedicel = add_fuse(base, "fuse_pedicel_membrane", pedicel)
    membrane = sopify_chain(
        base,
        fused_pedicel,
        (base_sops.adjust_mouth, base_sops.inset_membrane),
    )

    merge = add_merge(base, "merge_sternum_and_coxa", membrane, sternum)
    fuse = add_fuse(base, "fuse_sternum_and_coxa", merge)
    buffered = sopify(base, fuse, base_sops.extrude_base_buffer)
    add_output(base, "OUT_BASE", buffered)

    _propagate_subnets(base)
    base.layoutChildren()
    return base


def _add_parameters(base: hou.SopNode) -> None:
    add_float_parm(
        base,
        "coxa_flap_extension_ratio",
        1,
        1.63,
        (0.0, None),
        label="Coxa Flap Extension",
        help="Outward reach from the sternum rim, relative to rim-edge length.",
    )
    add_float_parm(
        base,
        "coxa_flap_rise_angle",
        1,
        12,
        (0.0, 90.0),
        label="Coxa Flap Rise",
        help="0° lies in the sternum plane; 90° raises the flap edge vertically.",
    )
    add_float_parm(
        base,
        "membrane_ratio",
        1,
        0.02,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )


def _propagate_subnets(base: hou.SopNode) -> None:
    promote_subnets(base)
