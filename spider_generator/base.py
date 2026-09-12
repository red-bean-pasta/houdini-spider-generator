import hou

from . import base_sops
from .helper import sopify_chain
from .sternum import build as build_sternum
from utilities.common import add_float_param
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_output,
    add_reloadable_subnet,
    propagate_parameters,
    sopify,
)


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    base = add_reloadable_subnet(cephalothorax, "base")
    _add_parameters(base)

    sternum = build_sternum(base)
    propagate_parameters(base, sternum, skip_params="membrane_ratio")
    sternum.parm("membrane_ratio").set(base.parm("membrane_ratio"))

    flap_regions = sopify_chain(
        base,
        sternum,
        (base_sops.extract_sternum_rim, base_sops.build_coxa_flaps, base_sops.add_flap_regions),
    )
    fuse_flaps = add_fuse(base, "fuse_coxa_flaps", flap_regions)
    connected = sopify(base, fuse_flaps, base_sops.connect_side_flaps)
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
    membrane = sopify(base, fused_pedicel, base_sops.inset_membrane)

    merge = add_merge(base, "merge_sternum_and_coxa", membrane, sternum)
    fuse = add_fuse(base, "fuse_sternum_and_coxa", merge)
    buffered = sopify(base, fuse, base_sops.extrude_base_buffer)
    add_output(base, "OUT_BASE", buffered)

    base.layoutChildren()
    return base


def _add_parameters(base: hou.SopNode) -> None:
    add_float_param(
        base,
        "coxa_height_ratio",
        1,
        1.2,
        (0.0, None),
    )
    add_float_param(
        base,
        "coxa_rotation_angle",
        1,
        36,
        (0.0, 90.0),
    )
    add_float_param(
        base,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )
