import hou

from utilities.common import add_float_param
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
)


def build(cephalothorax: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    lip = add_reloadable_subnet(cephalothorax, "lip")
    lip.setInput(0, source)
    _add_parameters(lip)

    source_node = lip.indirectInputs()[0]
    add_output(lip, "OUT_LIP", source_node)
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
