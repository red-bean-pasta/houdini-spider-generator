import hou

from .cheliceraes.builder import build as build_chelicerae


def build(cephalothorax: hou.SopNode, source: hou.SopNode) -> hou.SopNode:
    return build_chelicerae(cephalothorax, source)
