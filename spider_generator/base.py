import hou

from .bases.builder import build as build_base


def build(cephalothorax: hou.SopNode) -> hou.SopNode:
    return build_base(cephalothorax)
