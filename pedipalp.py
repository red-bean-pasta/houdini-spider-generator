import hou

from utilities.nodes import add_reloadable_subnet


def build(
    leg: hou.SopNode,
) -> hou.SopNode:
    pedipalp = add_reloadable_subnet(leg, "pedipalp")
    pedipalp.setInput(0, leg)
    _add_parameters(pedipalp)
    _add_controls(pedipalp)

    pedipalp.layoutChildren()
    return pedipalp


def _add_parameters(self: hou.OpNode) -> None:
    pass


def _add_controls(self: hou.SopNode) -> hou.SopNode:
    control = self.createNode("null", "CONTROL")
    pass