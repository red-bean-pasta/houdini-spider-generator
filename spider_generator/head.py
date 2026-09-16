import hou

from .heads.builder import build as build_head


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    return build_head(cephalothorax, base)
