import hou

from .mouths.builder import build as build_mouth


def build(parent: hou.OpNode, source: hou.SopNode) -> hou.SopNode:
    return build_mouth(parent, source)
