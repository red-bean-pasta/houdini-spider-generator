import hou

from .sternums.builder import build as build_sternum


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    return build_sternum(cephalothorax)
