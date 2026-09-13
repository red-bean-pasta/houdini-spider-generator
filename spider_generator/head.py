from enum import StrEnum, auto
from typing import Any

import hou

from . import base_sops, sternum
from .helper import (
    add_id_point,
    affix_id,
    deduplicate_id_attr,
    fill_face_by_id_with_attr,
    point_from_geo,
    position_from_geo,
    points_by_id,
    rename_left_ids_node,
    set_prim_attr_where_blank,
    sopify_chain,
    replace_points,
    set_point_id,
)
from utilities.common import (
    add_float_param,
    add_prim_attr,
    fill_face,
    get_float_parm,
    get_params,
    get_parent,
    points_by_attr,
)
from utilities.nodes import (
    add_fuse,
    add_merge,
    add_mirror,
    add_output,
    add_reloadable_subnet,
    sopify,
)
from utilities.topology import fill_pentagon, inset, offset_point


class ID(StrEnum):
    HEADCHELICERAE = auto()
    HEADFRONT = auto()
    HEADBACK = auto()
    HEADTOPMIDDLE = auto()
    HEADSIDEFRONT = auto()
    HEADSIDEMIDDLE = auto()
    HEADSIDEBACK = auto()
    HEADSUPPORT = auto()
    HEADBASESUPPORT = auto()
    HEADFRONTFLOAT = auto()
    HEADFRONTMID = auto()


class Region(StrEnum):
    HEADFRONTMAIN = auto()
    HEADFRONTCHEEK = auto()
    HEADTOP = auto()
    HEADBACK = auto()
    HEADSIDE = auto()


def headchelicerae(*i: int | str) -> str:
    return affix_id(ID.HEADCHELICERAE, *i)
def headfront(*i: int | str) -> str:
    return affix_id(ID.HEADFRONT, *i)
def headback(*i: int | str) -> str:
    return affix_id(ID.HEADBACK, *i)
def headtopmiddle(*i: int | str) -> str:
    return affix_id(ID.HEADTOPMIDDLE, *i)
def headsidefront(*i: int | str) -> str:
    return affix_id(ID.HEADSIDEFRONT, *i)
def headsidemiddle(*i: int | str) -> str:
    return affix_id(ID.HEADSIDEMIDDLE, *i)
def headsideback(*i: int | str) -> str:
    return affix_id(ID.HEADSIDEBACK, *i)
def headsupport(*i: int | str) -> str:
    return affix_id(ID.HEADSUPPORT, *i)
def headbasesupport(*i: int | str) -> str:
    return affix_id(f"{ID.HEADBASESUPPORT}_", *i)
def headfrontfloat(*i: int | str) -> str:
    return affix_id(ID.HEADFRONTFLOAT, *i)
def headfrontmid(*i: int | str) -> str:
    return affix_id(ID.HEADFRONTMID, *i)


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    head = add_reloadable_subnet(cephalothorax, "head")
    head.setInput(0, base)
    _add_parameters(head)

    source = head.indirectInputs()[0]
    base_rim = sopify(head, source, _extract_base_rim)
    base_points = sopify(head, source, _extract_work_base)
    regions = sopify_chain(
        head,
        base_points,
        (
            _add_corners_half,
            _add_head_dent,
            _curve_lip,
            _fill_back_loop_faces,
            _fill_support_loop_faces,
            _fill_side_faces,
            _add_side_regions,
        ),
    )
    mirrored = add_mirror(head, "left_mirror", regions, (1, 0, 0), True, False)
    faces = sopify(head, mirrored, rename_left_ids_node)

    merged = add_merge(head, "merge_base_rim", base_rim, faces)
    fused = add_fuse(head, "fuse_base_rim", merged)
    cleaned = sopify_chain(head, fused, (_inset_base_support_loop, _extrude_lip, _cleanup))
    add_output(head, "OUT_HEAD", cleaned)
    head.layoutChildren()
    return head


def _add_parameters(head: hou.SopNode) -> None:
    add_float_param(
        head,
        "height_ratio",
        1,
        0.375,
        (0.0, None),
        label="Top Height",
        help="Top-face height relative to the base-to-chelicerae reference span.",
    )
    add_float_param(
        head,
        "top_width_length_ratios",
        2,
        (1.0, 0.4),
        (0.0, None),
        naming_scheme=hou.parmNamingScheme.XYZW,
        label="Top Width / Length",
        help="X sets top width. Y sets the top face’s front-to-back length and flatness.",
    )
    add_float_param(
        head,
        "top_face_offset_ratio",
        1,
        0.0,
        label="Top Face Offset",
        help="Lengthwise skew of the top face relative to base length.",
    )
    add_float_param(
        head,
        "top_support_loop_ratios",
        2,
        (0.2, 0.5),
        naming_scheme=hou.parmNamingScheme.Base1,
        label="Top Support Loop",
        help="X adjusts the forward portion; Y adjusts the rear portion between the top face and base-side loop.",
    )
    add_float_param(
        head,
        "chelicerae_height_ratio",
        1,
        0.35,
        (0.0, None),
        label="Chelicerae Height",
        help="Vertical placement of the upper chelicerae line relative to the base.",
    )
    add_float_param(
        head,
        "lip_extrusion_ratio",
        2,
        (5.0, 1.0),
        (-10.0, 10.0),
        naming_scheme=hou.parmNamingScheme.XYZW,
        label="Lip Extrusion",
        help="X is lengthwise extrusion; Y is vertical extrusion.",
    )
    add_float_param(
        head,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
        label="Membrane Width",
        help="Shared cephalothorax setting. Each region applies it against its own local membrane scale.",
    )


def _extract_base_rim(node: hou.SopNode) -> None:
    geo = node.geometry()
    excluded_ids = {
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
        base_sops.basesternum(-1, 1),
    }
    point_data = [
        (point.stringAttribValue("id"), point.position())
        for point in geo.points()
        if point.stringAttribValue("id") not in excluded_ids
        and point.stringAttribValue("id").startswith("base")
    ]
    replace_points(geo, point_data)


def _extract_work_base(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    upper0_pos, upper1_pos, upper2_pos = _get_chelicerae_upper_positions(geo, parent)

    excluded_ids = {
        base_sops.basesternum(1, 1),
    }
    point_data = [
        (point.stringAttribValue("id"), point.position())
        for point in geo.points()
        if point.position()[0] >= -1e-4
        and point.stringAttribValue("id") not in excluded_ids
        and (
                   point.stringAttribValue("id").startswith("base")
                   or point.stringAttribValue("id") == sternum.sternumrim(0)
        )
    ]
    point_data.append((headchelicerae(0), upper0_pos))
    point_data.append((headchelicerae(1), upper1_pos))
    point_data.append((headchelicerae(2), upper2_pos))
    replace_points(geo, point_data)


def _get_chelicerae_upper_positions(geo: hou.Geometry, parent: hou.OpNode) -> tuple[hou.Vector3, hou.Vector3, hou.Vector3]:
    chelicerae_height_ratio = get_float_parm(parent, "chelicerae_height_ratio")
    basesternum0, basemaxilla1 = point_from_geo(geo, base_sops.basesternum(0), base_sops.basemaxilla(1))
    height = basemaxilla1.position().distanceTo(basesternum0.position()) * chelicerae_height_ratio
    height_offset = hou.Vector3(0.0, height, 0.0)

    upper0_pos = basesternum0.position() + height_offset
    upper2_pos = basemaxilla1.position() + height_offset
    upper1_pos = (upper0_pos + upper2_pos) / 2.0
    return upper0_pos, upper1_pos, upper2_pos


def _add_corners_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    points = points_by_id(geo)
    ref = _get_corner_reference_positions(geo)
    params = get_params(parent)

    top_corners = _compute_top_corners(ref, params)
    support_points = _compute_support_points(ref, top_corners, params)

    point_data = [
        (point_id, point.position())
        for point_id, point in points.items()
        if point_id not in (sternum.sternumrim(0), base_sops.basesternum(0))
    ]
    new_points = list(top_corners.items()) + list(support_points.items())
    replace_points(geo, point_data + new_points)

def _get_corner_reference_positions(geo: hou.Geometry) -> dict[str, hou.Vector3]:
    points = points_by_id(geo)
    expected_ids = (
        sternum.sternumrim(0),
        headchelicerae(0),
        base_sops.basesternum(0),
        base_sops.basesternum(1, 2),
        base_sops.basesternum(3),
        base_sops.basesternum(5, 1),
        base_sops.baseend(0),
    )
    assert all(point_id in points for point_id in expected_ids), "Expected head reference points"
    positions = position_from_geo(geo, *expected_ids)
    return dict(zip(expected_ids, positions))

def _compute_top_corners(
    ref: dict[str, hou.Vector3],
    params: Any,
) -> dict[str, hou.Vector3]:
    height = ref[base_sops.baseend(0)][2] - ref[headchelicerae(0)][2]
    flat_ratiox, flat_ratioy = params.top_width_length_ratios
    y_offset = hou.Vector3(0.0, height * params.height_ratio, 0.0)
    z_offset = hou.Vector3(0.0, 0.0, height * flat_ratioy)

    base_length = abs(ref[sternum.sternumrim(0)].z() - ref[base_sops.baseend(0)].z())
    flat_offset_z = hou.Vector3(0.0, 0.0, base_length * params.top_face_offset_ratio)
    sternumrim0_y = ref[sternum.sternumrim(0)][1]

    def align_front(position: hou.Vector3) -> hou.Vector3:
        return position + y_offset - hou.Vector3(0.0, position[1] - sternumrim0_y, 0.0)

    hf0 = align_front(ref[headchelicerae(0)]) + flat_offset_z
    hf1 = align_front(ref[base_sops.basesternum(1, 2)])
    hf1 = hou.Vector3(hf1[0] * flat_ratiox, hf1[1], hf1[2]) + flat_offset_z
    hb0 = hf0 + z_offset
    hb1 = hf1 + z_offset
    htm1 = (hf1 + hb1) / 2.0
    htm0 = (hf0 + hb0) / 2.0
    return {
        headfront(0): hf0,
        headfront(1): hf1,
        headback(0): hb0,
        headback(1): hb1,
        headtopmiddle(1): htm1,
        headtopmiddle(0): htm0,
    }

def _compute_support_points(
    ref: dict[str, hou.Vector3],
    top_corners: dict[str, hou.Vector3],
    params: Any,
) -> dict[str, hou.Vector3]:
    r1, r2 = params.top_support_loop_ratios
    r_mid = (r1 + r2) / 2.0

    hs0 = top_corners[headfront(0)] * (1.0 - r1) + ref[base_sops.basesternum(0)] * r1
    hs2 = top_corners[headfront(1)] * (1.0 - r1) + ref[base_sops.basesternum(1, 2)] * r1
    hs1 = (hs0 + hs2) / 2.0
    hs3 = top_corners[headtopmiddle(1)] * (1.0 - r_mid) + ref[base_sops.basesternum(3)] * r_mid
    hs4 = top_corners[headback(1)] * (1.0 - r2) + ref[base_sops.basesternum(5, 1)] * r2
    hs5 = top_corners[headback(0)] * (1.0 - r2) + ref[base_sops.baseend(0)] * r2
    return {
        headsupport(0): hs0,
        headsupport(1): hs1,
        headsupport(2): hs2,
        headsupport(3): hs3,
        headsupport(4): hs4,
        headsupport(5): hs5,
    }


def _add_head_dent(node: hou.SopNode) -> None:
    geo = node.geometry()
    headfront0, headsupport0 = point_from_geo(
        geo,
        headfront(0),
        headsupport(0),
    )
    dist = headfront0.position().distanceTo(headsupport0.position())
    direction = (headsupport0.position() - headfront0.position()).normalized()
    offset = direction * (dist * 1/3)
    offset_point(headfront0, offset)
    offset_point(headsupport0, offset)


def _curve_lip(node: hou.SopNode) -> None:
    geo = node.geometry()
    dist = get_head_base_loop_width(node)
    headchelicerae1, headsupport1 = point_from_geo(geo, headchelicerae(1), headsupport(1))
    offset = hou.Vector3(0.0, dist * 2, 0.0)
    for point in (headchelicerae1, headsupport1):
        offset_point(point, offset)


def _fill_back_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    add_prim_attr(geo, "region", "")

    _fill_head_front_faces(geo)
    _add_head_front_pentagon(geo)
    _fill_head_top_and_back_faces(geo)
    set_prim_attr_where_blank(geo, "region", Region.HEADTOP)


def _fill_head_front_faces(geo: hou.Geometry) -> None:
    fill_face_by_id_with_attr(
        geo,
        (
            headchelicerae(0),
            headsupport(0),
            headsupport(1),
            headchelicerae(1),
        ),
        "region",
        Region.HEADFRONTMAIN,
        True,
    )

    fill_face_by_id_with_attr(
        geo,
        (
            headchelicerae(1),
            headsupport(1),
            headsupport(2),
            headchelicerae(2),
        ),
        "region",
        Region.HEADFRONTMAIN,
        True,
    )

    fill_face_by_id_with_attr(
        geo,
        (
            headchelicerae(2),
            headsupport(2),
            base_sops.basesternum(1, 2),
            base_sops.basemaxilla(1),
        ),
        "region",
        Region.HEADFRONTCHEEK,
        True,
    )


def _add_head_front_pentagon(geo: hou.Geometry) -> None:
    hf0, hf1, hs2, hs1, hs0 = point_from_geo(
        geo,
        headfront(0),
        headfront(1),
        headsupport(2),
        headsupport(1),
        headsupport(0),
    )
    midpoint, floatpoint = fill_pentagon(
        geo,
        [hf0, hf1, hs2, hs1, hs0],
        (hf0, hs0),
    )
    set_point_id(midpoint, headfrontmid(0))
    set_point_id(floatpoint, headfrontfloat(1))


def _fill_head_top_and_back_faces(geo: hou.Geometry) -> None:
    faces = {
        (
            headfront(0),
            headfront(1),
            headtopmiddle(1),
            headtopmiddle(0),
        ): (False, Region.HEADTOP),
        (
            headtopmiddle(0),
            headtopmiddle(1),
            headback(1),
            headback(0),
        ): (False, Region.HEADTOP),
        (
            headback(1),
            headback(0),
            headsupport(5),
            headsupport(4),
        ): (True, Region.HEADTOP),
        (
            headsupport(4),
            headsupport(5),
            base_sops.baseend(0),
            base_sops.basesternum(5, 1),
        ): (True, Region.HEADBACK),
    }

    for face, (reverse, region) in faces.items():
        fill_face_by_id_with_attr(geo, face, "region", region, reverse)


def _fill_support_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    faces = {
        (
            headfront(1),
            headtopmiddle(1),
            headsupport(3),
            headsupport(2),
        ): True,
        (
            headtopmiddle(1),
            headback(1),
            headsupport(4),
            headsupport(3),
        ): True,
    }
    regions = (Region.HEADTOP, Region.HEADTOP)

    for i, (face, reverse) in enumerate(faces.items()):
        fill_face_by_id_with_attr(geo, face, "region", regions[i], reverse)


def _fill_side_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    right_side = _sorted_right_side_points(geo)
    assert len(right_side) >= 3 and len(right_side) % 2 == 1, "Expected an odd, symmetric right-side sternum loop"

    center_index = (len(right_side) - 1) // 2
    center = right_side[center_index]
    center_position = center.position()
    front_points = list(reversed(right_side[center_index + 1:]))
    back_points = right_side[:center_index]
    assert len(front_points) == len(back_points), "Expected matching front and back sternum loops"

    front_ratios, back_ratios = _get_head_side_layer_ratios(
        center_position,
        front_points,
        back_points,
    )
    head_side_points = _get_head_side_reference_points(points)
    side_points = _add_head_side_layer_points(
        geo,
        center_position,
        head_side_points,
        front_ratios,
        back_ratios,
    )
    current_points = _fill_head_side_layer_faces(
        geo,
        front_points,
        back_points,
        head_side_points,
        side_points,
    )
    _fill_head_side_end_faces(geo, front_points, back_points, center, current_points)


def _get_head_side_layer_ratios(
    center_position: hou.Vector3,
    front_points: list[hou.Point],
    back_points: list[hou.Point],
) -> tuple[list[float], list[float]]:
    front_offsets = [center_position - point.position() for point in front_points]
    back_offsets = [center_position - point.position() for point in back_points]
    front_outer_length = front_offsets[0].length()
    back_outer_length = back_offsets[0].length()
    assert front_outer_length > 1e-6 and back_outer_length > 1e-6, "Expected nonzero sternum side offsets"

    front_ratios = [offset.length() / front_outer_length for offset in front_offsets[1:]]
    back_ratios = [offset.length() / back_outer_length for offset in back_offsets[1:]]
    return front_ratios, back_ratios


def _get_head_side_reference_points(
    points: dict[str, hou.Point],
) -> tuple[hou.Point, hou.Point, hou.Point]:
    headfront_point = points.get(headsupport(2))
    headmiddle_point = points.get(headsupport(3))
    headback_point = points.get(headsupport(4))
    assert (
        headfront_point is not None
        and headmiddle_point is not None
        and headback_point is not None
    ), "Expected head side reference points"
    return headfront_point, headmiddle_point, headback_point


def _add_head_side_layer_points(
    geo: hou.Geometry,
    center_position: hou.Vector3,
    head_side_points: tuple[hou.Point, hou.Point, hou.Point],
    front_ratios: list[float],
    back_ratios: list[float],
) -> list[tuple[hou.Point, hou.Point, hou.Point]]:
    headfront_point, headmiddle_point, headback_point = head_side_points
    headfront_position = headfront_point.position()
    headmiddle_position = headmiddle_point.position()
    headback_position = headback_point.position()

    side_points = []
    for layer, (front_ratio, back_ratio) in enumerate(
        zip(front_ratios, back_ratios),
        start=1,
    ):
        front_position = center_position + (headfront_position - center_position) * front_ratio
        back_position = center_position + (headback_position - center_position) * back_ratio
        middle_ratio = (front_ratio + back_ratio) / 2.0
        middle_position = center_position + (headmiddle_position - center_position) * middle_ratio
        side_points.append(
            (
                _add_named_point(geo, front_position, headsidefront(layer)),
                _add_named_point(geo, middle_position, headsidemiddle(layer)),
                _add_named_point(geo, back_position, headsideback(layer)),
            )
        )
    return side_points


def _fill_head_side_layer_faces(
    geo: hou.Geometry,
    front_points: list[hou.Point],
    back_points: list[hou.Point],
    head_side_points: tuple[hou.Point, hou.Point, hou.Point],
    side_points: list[tuple[hou.Point, hou.Point, hou.Point]],
) -> tuple[hou.Point, hou.Point, hou.Point]:
    current_front, current_middle, current_back = head_side_points
    for layer, (next_front, next_middle, next_back) in enumerate(side_points):
        fill_face(
            geo,
            [current_front, front_points[layer], front_points[layer + 1], next_front],
        )
        fill_face(
            geo,
            [current_front, next_front, next_middle, current_middle],
        )
        fill_face(
            geo,
            [current_middle, next_middle, next_back, current_back],
        )
        fill_face(
            geo,
            [current_back, next_back, back_points[layer + 1], back_points[layer]],
        )
        current_front = next_front
        current_middle = next_middle
        current_back = next_back
    return current_front, current_middle, current_back


def _fill_head_side_end_faces(
    geo: hou.Geometry,
    front_points: list[hou.Point],
    back_points: list[hou.Point],
    center: hou.Point,
    current_points: tuple[hou.Point, hou.Point, hou.Point],
) -> None:
    current_front, current_middle, current_back = current_points
    fill_face(geo, [current_front, front_points[-1], center, current_middle])
    fill_face(geo, [current_middle, center, back_points[-1], current_back])

def _sorted_right_side_points(geo: hou.Geometry) -> list[hou.Point]:
    candidates = [
        point
        for point in geo.points()
        if point.stringAttribValue("id").startswith(base_sops.ID.BASESTERNUM)
        and point.position()[0] > 1e-4
    ]
    candidates.sort(key=lambda point: -point.position()[2])

    right_side = []
    for candidate in candidates:
        if right_side:
            previous = right_side[-1]
            candidate_position = candidate.position()
            previous_position = previous.position()
            if abs(candidate_position[2] - previous_position[2]) <= 1e-6:
                if candidate_position[0] > previous_position[0]:
                    right_side[-1] = candidate
                continue
        right_side.append(candidate)
    return right_side

def _add_named_point(
    geo: hou.Geometry,
    position: hou.Vector3,
    point_id: str,
) -> hou.Point:
    return add_id_point(geo, position, point_id)


def _add_side_regions(node: hou.SopNode) -> None:
    geo = node.geometry()
    set_prim_attr_where_blank(geo, "region", Region.HEADSIDE)


def _inset_base_support_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    dist = get_head_base_loop_width(node)
    inset(list(geo.prims()), dist, use_ratio=False)
    _attribute_inset_points(geo)
    deduplicate_id_attr(geo, None, keep_first=True)


def get_head_base_loop_width(node: hou.SopNode) -> float:
    geo = node.geometry()
    ratio = _get_membrane_ratio(node)
    headfront0, baseend0 = point_from_geo(geo, headfront(0), base_sops.baseend(0))
    height = headfront0.position().y() - baseend0.position().y()
    return ratio * height


def _get_membrane_ratio(node: hou.SopNode) -> float:
    parent = get_parent(node)
    return get_float_parm(parent, "membrane_ratio")


def _attribute_inset_points(geo: hou.Geometry) -> None:
    points = points_by_attr(geo, "id", True)
    for point_id, matching in points.items():
        if not point_id or len(matching) != 2:
            continue
        inset_pt = max(matching, key=lambda pt: pt.number())
        set_point_id(inset_pt, headbasesupport(point_id))


def _extrude_lip(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    ratio_x, ratio_y = get_params(parent).lip_extrusion_ratio

    # h0: headbasesupport(0), c0: headchelicerae(0)
    h0, c0 = point_from_geo(
        geo,
        headbasesupport(headchelicerae(0)),
        headchelicerae(0),
    )
    baseline = h0.position().y() - c0.position().y()

    z_offset = -baseline * ratio_x
    y_offset = -baseline * ratio_y
    offset = hou.Vector3(0.0, y_offset, z_offset)

    for side in (0, 1, 2, -1, -2):
        # hc: headchelicerae, hb: headbasesupport, hs: headsupport
        hc, hb, hs = point_from_geo(
            geo,
            headchelicerae(side),
            headbasesupport(headchelicerae(side)),
            headsupport(side),
        )
        for pt in (hc, hb, hs):
            offset_point(pt, offset)

    for side in (0, 1, -1):
        (hf,) = point_from_geo(geo, headfront(side))
        offset_point(hf, offset)

    for side in (1, -1):
        (hff,) = point_from_geo(geo, headfrontfloat(side))
        offset_point(hff, offset)

    (hfm,) = point_from_geo(geo, headfrontmid(0))
    offset_point(hfm, offset)


def _cleanup(node: hou.SopNode) -> None:
    geo = node.geometry()
    unused = [p for p in geo.points() if not p.prims()]
    if unused:
        geo.deletePoints(unused)
