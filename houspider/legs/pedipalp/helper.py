import hou

from houkit.noder import get_parent


def get_leg(node: hou.Node) -> hou.OpNode:
    subnet = node if node.isSubNetwork() else get_parent(node)
    return get_parent(subnet)
