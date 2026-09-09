import hou

from utilities.common import get_parent


def build_pedipalp(
    node: hou.SopNode,
) -> hou.SopNode:
    leg = get_parent(node)


