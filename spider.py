from enum import StrEnum, auto

import hou

import abdomen
import base_sops
import head
import sternum
from cephalothorax import build as build_cephalothorax
from helper import (
    add_id_point,
    affix_id,
    fill_face_with_attr,
    point_from_geo,
    points_by_id,
    prims_by_attr,
    set_prim_attr_where_blank,
)
from leg import build as build_legs
from pedicel import build as build_pedicel
from utilities.common import (
    add_float_param,
    add_folder,
    fill_face,
    get_params,
    get_parent,
)
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_outside_recalculation,
    add_reload_button,
    sopify,
)
from utilities.topology import fill_pentagon, offset_point


class ID(StrEnum):
    CEPHAPEDICELUPPER = auto()
    CEPHAPEDICELLOWER = auto()
    CEPHAPEDICELRIGHT = auto()
    CEPHAPEDICELLEFT = auto()


def cephapedicelupper(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELUPPER, *i)
def cephapedicellower(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELLOWER, *i)
def cephapedicelright(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELRIGHT, *i)
def cephapedicelleft(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELLEFT, *i)


def build(parent: hou.OpNode) -> hou.SopNode:
    spider = _add_spider(parent)

    cephalothorax = build_cephalothorax(spider)
    opened_cepha = sopify(spider, cephalothorax, _open_cepha_pedicel)

    abdomen_node = abdomen.build(spider, opened_cepha)

    opened_abdomen = sopify(spider, abdomen_node, _open_abdomen_pedicel)
    merged_c_a = add_merge(spider, "merge_cephalothorax_and_abdomen", opened_cepha, opened_abdomen)

    pedicel = build_pedicel(spider, merged_c_a)
    merged_ca_p = add_merge(spider, "merge_main_and_pedicel", merged_c_a, pedicel)
    fused_ca_p = add_fuse(spider, "fuse_main_and_pedicel", merged_ca_p)
    removed_sockets = sopify(spider, fused_ca_p, _remove_coxa_sockets)

    legs = build_legs(spider, fused_ca_p)
    merged_all = add_merge(spider, "merge_main_and_legs", removed_sockets, legs)
    fused = add_fuse(spider, "fuse_main_and_legs", merged_all)

    recalculated = add_outside_recalculation(spider, "recalculate_normals", fused)
    _add_subdivide(spider, "subdivision", recalculated, depth=3)

    recalculated.setDisplayFlag(True)
    recalculated.setRenderFlag(True)
    spider.layoutChildren()
    return spider


def _add_spider(parent: hou.OpNode) -> hou.SopNode:
    spider = parent.node("spider")
    if not spider:
        spider = parent.createNode("geo", "spider")
        for child in spider.children():
            child.destroy()
        add_reload_button(spider)

    _add_parameters(spider)
    return spider

def _add_parameters(spider: hou.OpNode) -> None:
    add_folder(
        spider,
        "build",
    )
    add_float_param(
        spider,
        "pedicel_size_ratio",
        2,
        (0.5, 0.5),
        (0.0, 1.0),
        folder_label="Build",
        help="Pedicel width and height ratio relative to the base pedicel opening.",
    )


def _add_subdivide(
    parent: hou.OpNode,
    name: str,
    p_input: hou.SopNode,
    depth: int = 1,
) -> hou.SopNode:
    subdivide = parent.createNode("subdivide", name)
    subdivide.setInput(0, p_input)
    subdivide.parm("iterations").set(depth)
    return subdivide


def _open_cepha_pedicel(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)
    params = get_params(parent)
    pedicel_size_ratio = params.pedicel_size_ratio
    pedicel_size_ratio_x, _ = pedicel_size_ratio

    (
        baseend0,
        basesupportend0,
        headsupport4,
        headsupport_minus4,
        headsupport5,
        sternumrim5,
        bs5_1,
        bs5_2,
        basesupportsternum5_1,
        basesupportsternum5_2,
    ) = point_from_geo(
        geo,
        base_sops.baseend(0),
        head.headbasesupport(base_sops.baseend(0)),
        head.headsupport(4),
        head.headsupport(-4),
        head.headsupport(5),
        sternum.sternumrim(5),
        base_sops.basesternum(5, 1),
        base_sops.basesternum(5, 2),
        head.headbasesupport(base_sops.basesternum(5, 1)),
        head.headbasesupport(base_sops.basesternum(5, 2)),
    )

    support_loop_width = _get_opening_support_loop_width(bs5_1, bs5_2, pedicel_size_ratio_x)

    cp_outer_lower, right_inner, left_inner = _identify_pedicel_membrane_points(geo)
    cp_right, cp_left, cp_outer_right, cp_outer_left = _add_side_cepha_pedicel_points(
        geo, baseend0, bs5_1, bs5_2, pedicel_size_ratio_x, support_loop_width
    )
    cp_upper, cp_lower = _position_vertical_pedicel_points(
        geo, baseend0, basesupportend0, headsupport5, sternumrim5, cp_outer_lower, pedicel_size_ratio, support_loop_width
    )
    _reconnect_lower_sternum_pedicel_loop(
        geo,
        cp_lower,
        cp_outer_lower,
        cp_right,
        cp_outer_right,
        cp_left,
        cp_outer_left,
        left_inner,
        right_inner,
        bs5_1,
        bs5_2,
        sternumrim5,
    )
    p_right, p_left = _reconnect_upper_sternum_pedicel_loop(
        geo,
        baseend0,
        basesupportend0,
        basesupportsternum5_1,
        basesupportsternum5_2,
        cp_upper,
        cp_right,
        cp_outer_right,
        cp_left,
        cp_outer_left,
        bs5_1,
        bs5_2,
        pedicel_size_ratio_x,
    )
    _retopo_head_back_faces(
        geo,
        headsupport4,
        headsupport_minus4,
        headsupport5,
        basesupportend0,
        basesupportsternum5_1,
        basesupportsternum5_2,
        p_right,
        p_left,
    )
    _adjust_opening_points_depth(cp_right, cp_left, cp_upper)

def _get_opening_support_loop_width(
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    pedicel_size_ratio_x: float,
) -> float:
    return bs5_1.position().x() * (1.0 - pedicel_size_ratio_x) * 0.035


def _identify_pedicel_membrane_points(geo: hou.Geometry) -> tuple[hou.Point, hou.Point, hou.Point]:
    membrane_prims = prims_by_attr(geo, "region", base_sops.Region.BASEPEDICELMEMBRANE)
    assert len(membrane_prims) == 1, f"Expected 1 basepedicelmembrane prim, got {len(membrane_prims)}"
    mem_prim = membrane_prims[0]

    p_lower = None
    right_inner = None
    left_inner = None
    for pt in mem_prim.points():
        pt_id = pt.stringAttribValue("id")
        if pt_id == sternum.sternumrim(5):
            continue
        if abs(pt.position().x()) < 1e-4:
            p_lower = pt
        elif pt.position().x() > 0:
            right_inner = pt
        else:
            left_inner = pt

    assert p_lower is not None, "Expected lower p point in basepedicelmembrane"
    assert right_inner is not None, "Expected right inner point in basepedicelmembrane"
    assert left_inner is not None, "Expected left inner point in basepedicelmembrane"
    return p_lower, right_inner, left_inner


def _add_side_cepha_pedicel_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    size_ratio_x: float,
    support_width: float,
) -> tuple[hou.Point, hou.Point, hou.Point, hou.Point]:
    p_end = baseend0.position()
    pos_bs5_1 = bs5_1.position()
    pos_bs5_2 = bs5_2.position()

    dir_right = (pos_bs5_1 - p_end).normalized()
    dir_left = (pos_bs5_2 - p_end).normalized()

    pos_right = pos_bs5_1 * size_ratio_x + p_end * (1 - size_ratio_x)
    pos_outer_right = pos_right + dir_right * support_width

    # cp = cephalothorax pedicel
    cp_right = add_id_point(geo, pos_right, cephapedicelright())

    cp_outer_right = geo.createPoint()
    cp_outer_right.setPosition(pos_outer_right)

    pos_left = pos_bs5_2 * size_ratio_x + p_end * (1 - size_ratio_x)
    pos_outer_left = pos_left + dir_left * support_width

    cp_left = add_id_point(geo, pos_left, cephapedicelleft())

    cp_outer_left = geo.createPoint()
    cp_outer_left.setPosition(pos_outer_left)

    return cp_right, cp_left, cp_outer_right, cp_outer_left


def _position_vertical_pedicel_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    basesupportend0: hou.Point,
    headsupport5: hou.Point,
    sternumrim5: hou.Point,
    cp_outer_lower: hou.Point,
    pedicel_size_ratio: tuple[float, float],
    support_width: float,
) -> tuple[hou.Point, hou.Point]:
    ratio_x, ratio_y = pedicel_size_ratio

    p_end = baseend0.position()
    p_head = headsupport5.position()
    p_sternum = sternumrim5.position()

    dir_upper = (p_head - p_end).normalized()

    pos_cp_lower = p_sternum * ratio_y + p_end * (1 - ratio_y)
    pos_cp_outer_lower = p_sternum * (1.0 / 3.0) + pos_cp_lower * (2.0 / 3.0)
    cp_outer_lower.setPosition(pos_cp_outer_lower)

    cp_lower = add_id_point(geo, pos_cp_lower, cephapedicellower())

    target_height = p_end.y() - pos_cp_lower.y()
    dy = p_head.y() - p_end.y()
    assert abs(dy) > 1e-6, "Expected non-zero y delta between baseend0 and headback0"
    t = target_height / dy
    offset = t * (p_head - p_end)
    new_end = p_end + offset

    p_upper = new_end * (1 - ratio_x) + p_end * ratio_x
    pos_baseend0 = p_upper + dir_upper * support_width
    baseend0_offset = pos_baseend0 - p_end

    cp_upper = add_id_point(geo, p_upper, cephapedicelupper())

    baseend0.setPosition(pos_baseend0)
    offset_point(basesupportend0, baseend0_offset)

    return cp_upper, cp_lower


def _reconnect_lower_sternum_pedicel_loop(
    geo: hou.Geometry,
    cp_lower: hou.Point,
    cp_outer_lower: hou.Point,
    cp_right: hou.Point,
    cp_outer_right: hou.Point,
    cp_left: hou.Point,
    cp_outer_left: hou.Point,
    left_inner: hou.Point,
    right_inner: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    s5: hou.Point,
) -> None:
    p_prims = list(cp_outer_lower.prims())
    geo.deletePrims(p_prims, keep_points=True)

    fill_pentagon(geo, [cp_outer_right, bs5_1, right_inner, s5, cp_outer_lower], (cp_outer_lower, s5), reverse=True)
    fill_pentagon(geo, [cp_outer_left, bs5_2, left_inner, s5, cp_outer_lower], (cp_outer_lower, s5), reverse=False)

    fill_face(geo, [cp_lower, cp_right, cp_outer_right, cp_outer_lower], reverse=False)
    fill_face(geo, [cp_lower, cp_left, cp_outer_left, cp_outer_lower], reverse=True)


def _reconnect_upper_sternum_pedicel_loop(
    geo: hou.Geometry,
    baseend0: hou.Point,
    basesupportend0: hou.Point,
    basesupportsternum5_1: hou.Point,
    basesupportsternum5_2: hou.Point,
    cp_upper: hou.Point,
    cp_right: hou.Point,
    cp_outer_right: hou.Point,
    cp_left: hou.Point,
    cp_outer_left: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    size_ratio_x: float,
) -> tuple[hou.Point, hou.Point]:
    _remove_upper_head_back_faces(baseend0, geo)
    p_right, p_left = _create_upper_pedicel_support_points(
        geo,
        baseend0,
        basesupportend0,
        basesupportsternum5_1,
        basesupportsternum5_2,
        cp_outer_right,
        cp_outer_left,
        bs5_1,
        bs5_2,
        size_ratio_x,
    )
    _fill_upper_pedicel_head_back_faces(
        geo,
        basesupportend0,
        baseend0,
        cp_outer_right,
        p_right,
        bs5_1,
        basesupportsternum5_1,
        cp_outer_left,
        p_left,
        bs5_2,
        basesupportsternum5_2,
    )
    _fill_upper_pedicel_buffer_faces(geo, cp_upper, cp_right, cp_left, cp_outer_right, cp_outer_left, baseend0)
    return p_right, p_left


def _remove_upper_head_back_faces(baseend0: hou.Point, geo: hou.Geometry) -> None:
    headback_prims = prims_by_attr(baseend0.prims(), "region", head.Region.HEADBACK)
    assert len(headback_prims) == 2, f"Expected 2 headback prims on baseend0, got {len(headback_prims)}"
    geo.deletePrims(headback_prims, keep_points=True)


def _create_upper_pedicel_support_points(
    geo: hou.Geometry,
    baseend0: hou.Point,
    basesupportend0: hou.Point,
    basesupportsternum5_1: hou.Point,
    basesupportsternum5_2: hou.Point,
    cp_outer_right: hou.Point,
    cp_outer_left: hou.Point,
    bs5_1: hou.Point,
    bs5_2: hou.Point,
    size_ratio_x: float,
) -> tuple[hou.Point, hou.Point]:
    v_end = basesupportend0.position() - baseend0.position()
    v_bs1 = basesupportsternum5_1.position() - bs5_1.position()
    v_bs2 = basesupportsternum5_2.position() - bs5_2.position()

    pos_p_right = cp_outer_right.position() + v_bs1 * size_ratio_x + v_end * (1 - size_ratio_x)
    pos_p_left = cp_outer_left.position() + v_bs2 * size_ratio_x + v_end * (1 - size_ratio_x)

    p_right = geo.createPoint()
    p_right.setPosition(pos_p_right)

    p_left = geo.createPoint()
    p_left.setPosition(pos_p_left)

    return p_right, p_left


def _fill_upper_pedicel_head_back_faces(
    geo: hou.Geometry,
    basesupportend0: hou.Point,
    baseend0: hou.Point,
    cp_outer_right: hou.Point,
    p_right: hou.Point,
    bs5_1: hou.Point,
    basesupportsternum5_1: hou.Point,
    cp_outer_left: hou.Point,
    p_left: hou.Point,
    bs5_2: hou.Point,
    basesupportsternum5_2: hou.Point,
) -> None:
    # Reconnect upper-right and upper-left faces
    fill_face_with_attr(
        geo, [basesupportend0, baseend0, cp_outer_right, p_right], "region", head.Region.HEADBACK, reverse=True
    )
    fill_face_with_attr(
        geo, [p_right, cp_outer_right, bs5_1, basesupportsternum5_1], "region", head.Region.HEADBACK, reverse=True
    )
    fill_face_with_attr(
        geo, [basesupportend0, baseend0, cp_outer_left, p_left], "region", head.Region.HEADBACK, reverse=False
    )
    fill_face_with_attr(
        geo, [p_left, cp_outer_left, bs5_2, basesupportsternum5_2], "region", head.Region.HEADBACK, reverse=False
    )


def _fill_upper_pedicel_buffer_faces(
    geo: hou.Geometry,
    cp_upper: hou.Point,
    cp_right: hou.Point,
    cp_left: hou.Point,
    cp_outer_right: hou.Point,
    cp_outer_left: hou.Point,
    baseend0: hou.Point,
) -> None:
    fill_face_with_attr(
        geo, [cp_upper, cp_right, cp_outer_right, baseend0], "region", base_sops.Region.BASEBUFFERMEMBRANE, reverse=True
    )
    fill_face_with_attr(
        geo, [cp_upper, cp_left, cp_outer_left, baseend0], "region", base_sops.Region.BASEBUFFERMEMBRANE, reverse=False
    )


def _retopo_head_back_faces(
    geo: hou.Geometry,
    headsupport4: hou.Point,
    headsupport_minus4: hou.Point,
    headsupport5: hou.Point,
    basesupportend0: hou.Point,
    basesupportsternum5_1: hou.Point,
    basesupportsternum5_2: hou.Point,
    p_right: hou.Point,
    p_left: hou.Point,
) -> None:
    prims_to_delete = [
        pr for pr in headsupport5.prims()
        if pr.stringAttribValue("region") == head.Region.HEADBACK and basesupportend0 in pr.points()
    ]
    assert len(prims_to_delete) == 2, f"Expected 2 upper headback prims on headsupport5, got {len(prims_to_delete)}"
    geo.deletePrims(prims_to_delete, keep_points=True)

    fill_pentagon(
        geo,
        [headsupport4, headsupport5, basesupportend0, p_right, basesupportsternum5_1],
        (headsupport5, basesupportend0),
        reverse=False,
    )
    fill_pentagon(
        geo,
        [headsupport_minus4, headsupport5, basesupportend0, p_left, basesupportsternum5_2],
        (headsupport5, basesupportend0),
        reverse=True,
    )

    set_prim_attr_where_blank(geo, "region", head.Region.HEADBACK)


def _adjust_opening_points_depth(
    cp_right: hou.Point,
    cp_left: hou.Point,
    cp_upper: hou.Point,
) -> None:
    offset_z = (cp_right.position().x() - cp_left.position().x()) / 4.0
    offset = hou.Vector3(0.0, 0.0, -offset_z)
    for pt in (cp_right, cp_left, cp_upper):
        offset_point(pt, offset)


def _open_abdomen_pedicel(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    points = points_by_id(geo)
    origin_point = points.get(abdomen.abdomenorigin())
    assert origin_point is not None, "Expected abdomenorigin point in abdomen"
    prims = list(origin_point.prims())
    geo.deletePrims(prims, keep_points=True)
    if origin_point in geo.points():
        geo.deletePoints([origin_point])


def _remove_coxa_sockets(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    socket_prims = prims_by_attr(
        geo,
        "region",
        (base_sops.Region.COXASOCKET, base_sops.Region.MAXILLASOCKET),
        startswith=True,
    )
    assert len(socket_prims) == 16 + 2, f"Expected 18 coxa socket prims, got {len(socket_prims)}"
    geo.deletePrims(socket_prims, keep_points=True)
