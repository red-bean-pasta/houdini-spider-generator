import hou

from ..bases import attributes as base_attributes
from ..helper import prims_by_attr

def remove_coxa_sockets(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims = prims_by_attr(
        geo,
        "region",
        (base_attributes.Region.COXASOCKET, base_attributes.Region.MAXILLASOCKET),
        startswith=True,
    )
    assert len(socket_prims) == 16 + 2, f"Expected 18 coxa socket prims, got {len(socket_prims)}"
    geo.deletePrims(socket_prims, keep_points=True)
