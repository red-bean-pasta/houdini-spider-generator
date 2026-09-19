import hou

from .spiders.builder import build as build_spider


def build(parent: hou.OpNode) -> hou.SopNode:
    return build_spider(parent)
