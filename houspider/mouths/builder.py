import hou

from houkit.noder import add_output, add_reloadable_subnet
from ..helper import sopify_chain
from . import topology


def build(parent: hou.OpNode, source: hou.SopNode) -> hou.SopNode:
    mouth_subnet = add_reloadable_subnet(parent, "mouth")
    mouth_subnet.setInput(0, source)

    source = mouth_subnet.indirectInputs()[0]
    built = sopify_chain(mouth_subnet, source, (topology.add_mouth_geometry, topology.adjust_mouth_points))
    add_output(mouth_subnet, "OUT_MOUTH", built)
    mouth_subnet.layoutChildren()
    return mouth_subnet
