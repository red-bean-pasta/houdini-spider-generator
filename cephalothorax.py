import math

import hou

import base_sops
from base import build as build_base
from chelicerae import (
    build as build_chelicerae,
    cheliceraemembrane,
    cheliceraestartmembranesupport,
)
from head import build as build_head, headbasesupport, headchelicerae
from helper import point_from_geo
from utilities.common import add_float_param
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_output,
    add_outside_recalculation,
    add_reloadable_subnet,
    propagate_parameters,
    sopify,
)


def build(spider: hou.OpNode) -> hou.SopNode:
    cephalothorax = add_reloadable_subnet(spider, "cephalothorax")
    _add_parameters(cephalothorax)

    base = build_base(cephalothorax)
    _link_membrane_ratio(cephalothorax, base)

    head = build_head(cephalothorax, base)
    _link_membrane_ratio(cephalothorax, head)

    b_h_merge = add_merge(cephalothorax, "merge_base_and_head", base, head)
    b_h_fuse = add_fuse(cephalothorax, "fuse_base_and_head", b_h_merge)

    chelicerae_added = build_chelicerae(cephalothorax, b_h_fuse)
    _link_membrane_ratio(cephalothorax, chelicerae_added)

    adjusted = sopify(cephalothorax, chelicerae_added, _adjust_head_chelicerae_depth)

    recalculate = add_outside_recalculation(cephalothorax, "recalculate_normals", adjusted)
    positioned = _position_cephalothorax(cephalothorax, recalculate)

    _ = add_output(cephalothorax, "OUT_CEPHALOTHORAX", positioned)

    cephalothorax.layoutChildren()
    return cephalothorax


def _add_parameters(cephalothorax: hou.SopNode) -> None:
    add_float_param(
        cephalothorax,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )


def _link_membrane_ratio(parent: hou.SopNode, child: hou.SopNode) -> None:
    propagate_parameters(parent, child, skip_params="membrane_ratio")
    child.parm("membrane_ratio").set(parent.parm("membrane_ratio"))


def _position_cephalothorax(parent: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    position = parent.createNode("xform", "position_cephalothorax")
    position.setInput(0, source)
    pattern = f'pointpattern(0, "@id={base_sops.baseend(0)}")'
    for axis_index, axis_name in enumerate(("tx", "ty", "tz")):
        position.parm(axis_name).setExpression(f'0 - point(0, {pattern}, "P", {axis_index})')
    return position


def _adjust_head_chelicerae_depth(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    # h0: headchelicerae0, hs0: headbasesupport_headchelicerae0
    # c6: cheliceraemembrane6, cs6: cheliceraestartmembranesupport2
    h0, hs0, c6, cs6 = point_from_geo(
        geo,
        headchelicerae(0),
        headbasesupport(headchelicerae(0)),
        cheliceraemembrane(6),
        cheliceraestartmembranesupport(2),
    )
    for pt in (h0, hs0, c6, cs6):
        assert abs(pt.position().x()) < 1e-4

    dh = (h0.position() - hs0.position()).normalized()
    dc = (cs6.position() - c6.position()).normalized()

    v0 = h0.position() - c6.position()
    v_perp = (v0 - dc * v0.dot(dc)).normalized()
    angle = math.radians(10)
    d_target = dc * math.cos(angle) + v_perp * math.sin(angle)

    denom = (d_target.cross(dh)).x()
    assert abs(denom) > 1e-6, "Target direction and head direction are nearly parallel"
    t = (v0.cross(d_target)).x() / denom
    h0.setPosition(h0.position() + dh * t)
