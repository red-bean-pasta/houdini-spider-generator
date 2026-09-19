import hou

from .legs.builder import build as build_legs


def build(
    spider: hou.SopNode,
    base: hou.SopNode,
) -> hou.SopNode:
    return build_legs(spider, base)
