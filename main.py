import hou
from cephalothorax import build as build_cephalothorax


def build() -> hou.ObjNode:
    spider = _add_spider()
    cephalothorax = build_cephalothorax(spider)
    spider.layoutChildren()
    return spider


def _add_spider() -> hou.ObjNode:
    obj = _get_root()

    spider = obj.node("spider")
    if spider:
        return spider

    spider = obj.createNode("geo", "spider")
    for child in spider.children():
        child.destroy()

    return spider


def _get_root() -> hou.Node:
    obj = hou.node("/obj")
    assert obj is not None
    return obj


if __name__ == "__main__":
    build()
