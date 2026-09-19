import hou

from .abdomens.builder import build as build_abdomen


def build(spider_node: hou.OpNode, cephalothorax: hou.SopNode) -> hou.SopNode:
    return build_abdomen(spider_node, cephalothorax)
