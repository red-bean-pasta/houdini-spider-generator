import hou

from . import spider


def build() -> hou.SopNode:
    root = _get_root()
    spider_node = spider.build(root)
    spider_node.layoutChildren()
    return spider_node

def _get_root() -> hou.OpNode:
    obj = hou.node("/obj")
    assert obj is not None, "Expected /obj node"
    return obj
