import hou

from ..bases import attributes as base_attributes
from ..helper import points_from_geo
from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm
from .attributes import headfront


def get_head_base_loop_width(node: hou.SopNode) -> float:
    geo = node.geometry()
    ratio = get_membrane_ratio(node)
    headfront0, baseend0 = points_from_geo(geo, headfront(0), base_attributes.baseend(0))
    height = headfront0.position().y() - baseend0.position().y()
    return ratio * height


def get_membrane_ratio(node: hou.SopNode) -> float:
    parent = get_parent(node)
    return get_float_parm(parent, "membrane_ratio")
