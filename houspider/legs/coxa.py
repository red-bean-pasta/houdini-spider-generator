import hou

from houkit.attributer import add_global_attrib, remove_attribs
from .pedipalp.attributes import tmp_front_socket_size
from ..bases import attributes as base_attributes
from ..helper import positions_from_geo, prims_by_attr


def prepare_attributed_data(node: hou.SopNode) -> None:
    from .pedipalp.builder import prepare_attributed_data as pedipalp_prepare

    geo = node.geometry()
    add_global_attrib(
        geo,
        tmp_front_socket_size(),
        _get_front_coxa_socket_size(geo)
    )

    pedipalp_prepare(geo)


def extract_right_coxa(node: hou.SopNode) -> None:
    from .pedipalp.builder import extract_required_points as pedipalp_extract

    geo = node.geometry()
    socket_prims = [
        prim for prim in prims_by_attr(geo, "region", base_attributes.Region.COXASOCKET, startswith=True)
        if prim.boundingBox().center().x() > 0
    ]
    assert len(socket_prims) == 8, f"Expected 8 right coxa socket prims, got {len(socket_prims)}"

    used = (
        {pt for prim in socket_prims for pt in prim.points()}
        | pedipalp_extract(geo)
    )
    geo.deletePoints([p for p in geo.points() if p not in used])
    geo.deletePrims(geo.prims(), keep_points=True)


def remove_tmp_attributes(node: hou.SopNode) -> None:
    remove_attribs(node.geometry(), global_attributes=(tmp_front_socket_size(),))


def _get_front_coxa_socket_size(geo: hou.Geometry) -> tuple[float, float]:
    """

    :param geo:
    :return: width, length
    """
    pos_top_sz, pos_top_bz, pos_btm_sz, pos_btm_bz = positions_from_geo(
        geo,
        base_attributes.basecoxamemebrane(1, 4),
        base_attributes.basecoxamemebrane(1, 3),
        base_attributes.basecoxamemebrane(1, 1),
        base_attributes.basecoxamemebrane(1, 2),
    )

    width = (pos_top_bz - pos_top_sz).length()
    top_mid = (pos_top_sz + pos_top_bz) / 2.0
    btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
    height = top_mid.y() - btm_mid.y()

    return width, height
