from enum import StrEnum, auto
from typing import Callable

import hou

import base_sops
import sternum
from chelicerae import cheliceraemembraneupper
from helper import (
    add_id_attr,
    affix_id,
    deduplicate_id_attr,
    fill_face_by_id,
    points_by_id,
    rename_left_ids,
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
from utilities.topology import inset


class ID(StrEnum):
    HEADFRONT = auto()
    HEADBACK = auto()
    HEADTOPMIDDLE = auto()
    HEADSIDEFRONT = auto()
    HEADSIDEMIDDLE = auto()
    HEADSIDEBACK = auto()
    HEADSUPPORT = auto()
    HEADCHELICERAEUPPER = auto()

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
def headcheliceraeupper(*i: int | str) -> str:
    return affix_id(ID.HEADCHELICERAEUPPER, *i)


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    head = add_reloadable_subnet(cephalothorax, "head")
    head.setInput(0, base)
    _add_parameters(head)

    source = head.indirectInputs()[0]
    base_rim = sopify(head, source, _extract_base_rim)
    base_points = sopify(head, source, _extract_work_base)
    corners = sopify(head, base_points, _add_corners_half)
    back_faces = sopify(head, corners, _fill_back_loop_faces)
    support_faces = sopify(head, back_faces, _fill_support_loop_faces)
    right_half = sopify(head, support_faces, _fill_side_faces)
    regions = sopify(head, right_half, _add_side_regions)
    mirrored = add_mirror(head, "left_mirror", regions, (1, 0, 0), True, False)
    faces = sopify(head, mirrored, _rename_left_ids)

    merged = add_merge(head, "merge_base_rim", base_rim, faces)
    fused = add_fuse(head, "fuse_base_rim", merged)
    inset_support = sopify(head, fused, _inset_base_support_loop)
    cleaned = sopify(head, inset_support, _cleanup)
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
    )
    add_float_param(
        head,
        "flat_ratio",
        1,
        0.4,
        (0.0, None),
    )
    add_float_param(
        head,
        "top_support_loop_ratio",
        2,
        (0.2, 0.5),
        naming_scheme=hou.parmNamingScheme.Base1,
        help="Affects how sharp or boxy the head looks; the first is for front ratio and the second for behind",
    )
    add_float_param(
        head,
        "membrane_ratio",
        1,
        0.035,
        (0.0, None),
    )


def _add_points(
    geo: hou.Geometry,
    point_data: list[tuple[str, hou.Vector3]],
) -> None:
    geo.clear()
    add_id_attr(geo)
    for point_id, position in point_data:
        point = geo.createPoint()
        point.setPosition(position)
        point.setAttribValue("id", point_id)

def _extract_points(
    node: hou.SopNode,
    keep_point: Callable[[str, hou.Vector3], bool],
) -> None:
    geo = node.geometry()
    point_data = [
        (point.stringAttribValue("id"), point.position())
        for point in geo.points()
        if keep_point(point.stringAttribValue("id"), point.position())
    ]
    _add_points(geo, point_data)

def _add_named_point(
    geo: hou.Geometry,
    position: hou.Vector3,
    point_id: str,
) -> hou.Point:
    point = geo.createPoint()
    point.setPosition(position)
    set_point_id(point, point_id)
    return point


def _extract_work_base(node: hou.SopNode) -> None:
    excluded_ids = {
        base_sops.basesternum(1, 1),
    }
    _extract_points(
        node,
        lambda point_id, position: (
            position[0] >= -1e-4
            and point_id not in excluded_ids
            and (
                point_id.startswith("base")
                or point_id in (cheliceraemembraneupper(0), cheliceraemembraneupper(1))
                or point_id == sternum.sternumrim(0)
            )
        ),
    )


def _extract_base_rim(node: hou.SopNode) -> None:
    excluded_ids = {
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
        base_sops.basesternum(-1, 1),
    }
    _extract_points(
        node,
        lambda point_id, position: (
            point_id not in excluded_ids
            and (
                point_id.startswith("base")
                or point_id in (
                    cheliceraemembraneupper(0),
                    cheliceraemembraneupper(1),
                    cheliceraemembraneupper(-1),
                )
            )
        ),
    )


def _add_corners_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    points = points_by_id(geo)

    sternumrim0 = sternum.sternumrim(0)
    cheliceraeupper0 = cheliceraemembraneupper(0)
    basesternum0 = base_sops.basesternum(0)
    basesternum1_2 = base_sops.basesternum(1, 2)
    basesternum3 = base_sops.basesternum(3)
    basesternum5_1 = base_sops.basesternum(5, 1)
    baseend0 = base_sops.baseend(0)
    expected_ids = (
        sternumrim0,
        cheliceraeupper0,
        basesternum0,
        basesternum1_2,
        basesternum3,
        basesternum5_1,
        baseend0,
    )
    assert all(point_id in points for point_id in expected_ids), "Expected head reference points"

    sternumrim0_pos = points[sternumrim0].position()
    cheliceraeupper0_pos = points[cheliceraeupper0].position()
    basesternum0_pos = points[basesternum0].position()
    basesternum1_2_pos = points[basesternum1_2].position()
    basesternum3_pos = points[basesternum3].position()
    basesternum5_1_pos = points[basesternum5_1].position()
    baseend0_pos = points[baseend0].position()

    height = baseend0_pos[2] - cheliceraeupper0_pos[2]
    params = get_params(parent)
    height_ratio = params.height_ratio
    flat_ratio = params.flat_ratio
    top_support_loop_ratio1, top_support_loop_ratio2 = params.top_support_loop_ratio
    top_support_loop_ratio_mid = (top_support_loop_ratio1 + top_support_loop_ratio2) / 2.0
    y_offset = hou.Vector3(0.0, height * height_ratio, 0.0)
    z_offset = hou.Vector3(0.0, 0.0, height * flat_ratio)

    def align_front(position: hou.Vector3) -> hou.Vector3:
        return position + y_offset - hou.Vector3(
            0.0,
            position[1] - sternumrim0_pos[1],
            0.0,
        )

    headfront0_pos = align_front(cheliceraeupper0_pos)
    headfront1_pos = align_front(basesternum1_2_pos)
    headback0_pos = headfront0_pos + z_offset
    headback1_pos = headfront1_pos + z_offset
    headtopmiddle1_pos = (headfront1_pos + headback1_pos) / 2.0
    headtopmiddle0_pos = (headfront0_pos + headback0_pos) / 2.0

    r1 = top_support_loop_ratio1
    r2 = top_support_loop_ratio2
    r_mid = top_support_loop_ratio_mid

    headsupport0_pos = headfront0_pos * (1.0 - r1) + basesternum0_pos * r1
    headsupport1_pos = headfront1_pos * (1.0 - r1) + basesternum1_2_pos * r1
    headsupport2_pos = headtopmiddle1_pos * (1.0 - r_mid) + basesternum3_pos * r_mid
    headsupport3_pos = headback1_pos * (1.0 - r2) + basesternum5_1_pos * r2
    headsupport4_pos = headback0_pos * (1.0 - r2) + baseend0_pos * r2

    point_data = [
        (point_id, point.position())
        for point_id, point in points.items()
        if point_id not in (sternumrim0, basesternum0)
    ]
    new_points = [
        (headfront(0), headfront0_pos),
        (headfront(1), headfront1_pos),
        (headback(0), headback0_pos),
        (headback(1), headback1_pos),
        (headtopmiddle(1), headtopmiddle1_pos),
        (headtopmiddle(0), headtopmiddle0_pos),
        (headsupport(0), headsupport0_pos),
        (headsupport(1), headsupport1_pos),
        (headsupport(2), headsupport2_pos),
        (headsupport(3), headsupport3_pos),
        (headsupport(4), headsupport4_pos),
    ]
    _add_points(geo, point_data + new_points)


def _fill_back_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    faces = {
        (
            cheliceraemembraneupper(0),
            headsupport(0),
            headsupport(1),
            cheliceraemembraneupper(1),
        ): True,
        (
            cheliceraemembraneupper(1),
            headsupport(1),
            base_sops.basesternum(1, 2),
            base_sops.basemaxilla(1),
        ): True,
        (
            headfront(0),
            headfront(1),
            headsupport(1),
            headsupport(0),
        ): True,
        (
            headfront(0),
            headfront(1),
            headtopmiddle(1),
            headtopmiddle(0),
        ): False,
        (
            headtopmiddle(0),
            headtopmiddle(1),
            headback(1),
            headback(0),
        ): False,
        (
            headback(1),
            headback(0),
            headsupport(4),
            headsupport(3),
        ): True,
        (
            headsupport(3),
            headsupport(4),
            base_sops.baseend(0),
            base_sops.basesternum(5, 1),
        ): True,
    }
    regions = (
        "headfrontmain",
        "headfrontcheek",
        "headtop",
        "headtop",
        "headtop",
        "headtop",
        "headback",
    )

    add_prim_attr(geo, "region", "")
    for i, (face, reverse) in enumerate(faces.items()):
        prim = fill_face_by_id(geo, face, reverse)
        prim.setAttribValue("region", regions[i])

def _fill_support_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    faces = {
        (
            headfront(1),
            headtopmiddle(1),
            headsupport(2),
            headsupport(1),
        ): True,
        (
            headtopmiddle(1),
            headback(1),
            headsupport(3),
            headsupport(2),
        ): True,
    }
    regions = ("headtop", "headtop")

    for i, (face, reverse) in enumerate(faces.items()):
        prim = fill_face_by_id(geo, face, reverse)
        prim.setAttribValue("region", regions[i])


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

    front_offsets = [center_position - point.position() for point in front_points]
    back_offsets = [center_position - point.position() for point in back_points]
    front_outer_length = front_offsets[0].length()
    back_outer_length = back_offsets[0].length()
    assert front_outer_length > 1e-6 and back_outer_length > 1e-6, "Expected nonzero sternum side offsets"

    front_ratios = [
        offset.length() / front_outer_length
        for offset in front_offsets[1:]
    ]
    back_ratios = [
        offset.length() / back_outer_length
        for offset in back_offsets[1:]
    ]

    headfront_point = points.get(headsupport(1))
    headmiddle_point = points.get(headsupport(2))
    headback_point = points.get(headsupport(3))
    assert (
        headfront_point is not None
        and headmiddle_point is not None
        and headback_point is not None
    ), "Expected head side reference points"
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

    current_front = headfront_point
    current_middle = headmiddle_point
    current_back = headback_point
    for layer, (next_front, next_middle, next_back) in enumerate(side_points):
        fill_face(
            geo,
            [current_front, front_points[layer], front_points[layer + 1], next_front],
        )
        fill_face(
            geo,
            [current_front, next_front, next_middle, current_middle])
        fill_face(
            geo,
            [current_middle, next_middle, next_back, current_back])
        fill_face(
            geo,
            [current_back, next_back, back_points[layer + 1], back_points[layer]],
        )
        current_front = next_front
        current_middle = next_middle
        current_back = next_back

    fill_face(
        geo,
      [current_front, front_points[-1], center, current_middle]
    )
    fill_face(
        geo,
        [current_middle, center, back_points[-1], current_back]
    )


def _add_side_regions(node: hou.SopNode) -> None:
    geo = node.geometry()
    for prim in geo.prims():
        if not prim.stringAttribValue("region"):
            prim.setAttribValue("region", "headside")


def _rename_left_ids(node: hou.SopNode) -> None:
    rename_left_ids(node.geometry())


def _inset_base_support_loop(node: hou.SopNode) -> None:
    geo = node.geometry()
    _inset_base(geo, _get_membrane_ratio(node))
    _attribute_points_between_head_chelicerae(geo, headcheliceraeupper)
    deduplicate_id_attr(geo, None, keep_first=True)


def _cleanup(node: hou.SopNode) -> None:
    geo = node.geometry()
    unused = [p for p in geo.points() if not p.prims()]
    if unused:
        geo.deletePoints(unused)


def _get_membrane_ratio(node: hou.SopNode) -> float:
    parent = get_parent(node)
    return get_float_parm(parent, "membrane_ratio")

def _inset_base(geo: hou.Geometry, ratio: float) -> None:
    points = points_by_id(geo)
    headfront0 = points.get(headfront(0))
    baseend0 = points.get(base_sops.baseend(0))
    if headfront0 is None or baseend0 is None:
        return
    height = headfront0.position().y() - baseend0.position().y()
    dist = ratio * height

    inset(list(geo.prims()), dist, use_ratio=False)

def _attribute_points_between_head_chelicerae(
        geo: hou.Geometry,
        attributer: Callable
) -> None:
    points = points_by_attr(geo, "id", True)
    for i in (-1, 0, 1):
        membrane_id = cheliceraemembraneupper(i)
        matching = points[membrane_id]
        assert len(matching) == 2, f"Expected 2 points with id {membrane_id!r}"
        inset_pt = max(matching, key=lambda pt: pt.number())
        set_point_id(inset_pt, attributer(i))
