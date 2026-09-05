import hou

from chelicerae import cheliceraemembraneupper
from head import headcheliceraeupper
from helper import points_by_id
from utilities.common import add_float_param
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import loop_cut


def build(cephalothorax: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    lip = add_reloadable_subnet(cephalothorax, "lip")
    lip.setInput(0, source)
    _add_parameters(lip)

    source_node = lip.indirectInputs()[0]
    loops = sopify(lip, source_node, _add_loops)

    add_output(lip, "OUT_LIP", loops)
    lip.layoutChildren()
    return lip


def _add_parameters(lip: hou.SopNode) -> None:
    add_float_param(
        lip,
        "extrusion_ratio",
        2,
        (5.0, 1.0),
        (-10.0, 10.0),
        naming_scheme=hou.parmNamingScheme.XYZW,
        help="Lip refers to the touching line between chelicerae and head, and the ratio is relative to the base support loop (membrane) height",
    )


def _add_loops(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)

    c0 = points[cheliceraemembraneupper(0)]
    h0 = points[headcheliceraeupper(0)]
    c1 = points[cheliceraemembraneupper(1)]
    h1 = points[headcheliceraeupper(1)]
    c_neg1 = points[cheliceraemembraneupper(-1)]
    h_neg1 = points[headcheliceraeupper(-1)]

    prim_right = next(
        p for p in c0.prims()
        if h0 in p.points() and c1 in p.points() and h1 in p.points()
    )
    prim_left = next(
        p for p in c0.prims()
        if h0 in p.points() and c_neg1 in p.points() and h_neg1 in p.points()
    )

    ratios = (1/6, 2/6, 3/6, 5/6)
    delta_ratios = [
        ratios[i]
        if i < 1 else
        (ratios[i] - ratios[i - 1]) / (1 - (ratios[i - 1]))
        for i in range(len(ratios))
    ]

    current_start = h0
    scope = [prim_right, prim_left]
    for delta in delta_ratios:
        prim_to_cut = scope[0]
        added_pts, _ = loop_cut(
            prim_to_cut,
            current_start,
            c0,
            delta,
            use_ratio=True,
            scope=scope,
        )
        current_start = next(pt for pt in added_pts if abs(pt.position().x()) < 1e-4)
        scope = [p for p in current_start.prims() if c0 in p.points()]
