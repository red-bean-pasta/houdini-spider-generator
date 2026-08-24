from enum import StrEnum, auto
from typing import Callable

import hou

import base_sops
import sternum_sops
from chelicerae import cheliceraeupper
from utility.helper import (
    add_point_attr,
    affix_id,
    fill_face,
    fill_face_by_id,
    get_float_parm,
    get_parent,
    points_by_attribute,
    set_point_id,
    sopify, add_new_prim_attr,
)
from sop_helper import add_fuse, add_merge, add_mirror, add_output


class ID(StrEnum):
    HEADFRONT = auto()
    HEADBACK = auto()
    HEADTOPMIDDLE = auto()
    HEADSIDEFRONT = auto()
    HEADSIDEMIDDLE = auto()
    HEADSIDEBACK = auto()

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


def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    head = cephalothorax.createNode("subnet", "head")
    head.setInput(0, base)
    _add_parameters(head)

    source = head.indirectInputs()[0]
    base_rim = sopify(head, source, _extract_base_rim)
    base_points = sopify(head, source, _extract_work_base)
    corners = sopify(head, base_points, _add_corners_half)
    back_faces = sopify(head, corners, _fill_back_loop_faces)
    right_half = sopify(head, back_faces, _fill_side_faces)
    regions = sopify(head, right_half, _add_side_regions)
    mirrored = add_mirror(head, "left_mirror", regions, (1, 0, 0), True, False)
    faces = sopify(head, mirrored, _rename_left_ids)

    merged = add_merge(head, "merge_base_rim", base_rim, faces)
    fused = add_fuse(head, "fuse_base_rim", merged)
    add_output(head, "OUT_HEAD", fused)
    head.layoutChildren()
    return head


def _add_parameters(head: hou.SopNode) -> None:
    templates = head.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "height_ratio",
            "Height Ratio",
            1,
            default_value=(0.375,),
            min=0.0,
            min_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "flat_ratio",
            "Flat Ratio",
            1,
            default_value=(0.4,),
            min=0.0,
            min_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "membrane_ratio",
            "Membrane Ratio",
            1,
            default_value=(0.035,),
            min=0.0,
            min_is_strict=True,
        )
    )
    head.setParmTemplateGroup(templates)


def _add_points(
    geo: hou.Geometry,
    point_data: list[tuple[str, hou.Vector3]],
) -> None:
    geo.clear()
    add_point_attr(geo)
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
        base_sops.basesternum(0),
        base_sops.basesternum(1, 1),
    }
    _extract_points(
        node,
        lambda point_id, position: (
            position[0] >= 0.0
            and point_id not in excluded_ids
            and (
                point_id.startswith("base")
                or point_id.startswith("chelicerae")
                or point_id == sternum_sops.sternumrim(0)
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
            and (point_id.startswith("base") or point_id.startswith("chelicerae"))
        ),
    )


def _add_corners_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    points = points_by_attribute(geo)

    sternumrim0 = sternum_sops.sternumrim(0)
    cheliceraeupper0 = cheliceraeupper(0)
    basesternum1_2 = base_sops.basesternum(1, 2)
    baseend0 = base_sops.baseend(0)
    expected_ids = (sternumrim0, cheliceraeupper0, basesternum1_2, baseend0)
    assert all(point_id in points for point_id in expected_ids), "Expected head reference points"

    sternumrim0_position = points[sternumrim0].position()
    cheliceraeupper0_position = points[cheliceraeupper0].position()
    baseend0_position = points[baseend0].position()
    basesternum1_2_position = points[basesternum1_2].position()

    height = baseend0_position[2] - cheliceraeupper0_position[2]
    height_ratio = get_float_parm(parent, "height_ratio")
    flat_ratio = get_float_parm(parent, "flat_ratio")
    y_offset = hou.Vector3(0.0, height * height_ratio, 0.0)
    z_offset = hou.Vector3(0.0, 0.0, height * flat_ratio)

    def align_front(position: hou.Vector3) -> hou.Vector3:
        return position + y_offset - hou.Vector3(
            0.0,
            position[1] - sternumrim0_position[1],
            0.0,
        )

    headfront0_position = align_front(cheliceraeupper0_position)
    headfront1_position = align_front(basesternum1_2_position)
    headback0_position = headfront0_position + z_offset
    headback1_position = headfront1_position + z_offset
    headtopmiddle1_position = (headfront1_position + headback1_position) / 2.0
    headtopmiddle0_position = (headfront0_position + headback0_position) / 2.0

    point_data = [
        (point_id, point.position())
        for point_id, point in points.items()
        if point_id != sternumrim0
    ]
    new_points = [
        (headfront(0), headfront0_position),
        (headfront(1), headfront1_position),
        (headback(0), headback0_position),
        (headback(1), headback1_position),
        (headtopmiddle(1), headtopmiddle1_position),
        (headtopmiddle(0), headtopmiddle0_position),
    ]
    _add_points(geo, point_data + new_points)


def _fill_back_loop_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    faces = (
        (
            cheliceraeupper(0),
            headfront(0),
            headfront(1),
            cheliceraeupper(2),
            cheliceraeupper(1),
        ),
        (
            cheliceraeupper(2),
            headfront(1),
            base_sops.basesternum(1, 2),
            base_sops.basemaxilla(1),
        ),
        (
            headfront(0),
            headfront(1),
            headtopmiddle(1),
            headtopmiddle(0),
        ),
        (
            headtopmiddle(0),
            headtopmiddle(1),
            headback(1),
            headback(0),
        ),
        (
            headback(0),
            headback(1),
            base_sops.basesternum(5, 1),
            base_sops.baseend(0),
        ),
    )
    regions = ("headfrontmain", "headfrontcheek", "headtop", "headtop", "headback")

    add_new_prim_attr(geo, "region", "")
    for i, face in enumerate(faces):
        prim = fill_face_by_id(geo, list(face))
        prim.setAttribValue("region", regions[i])


def _sorted_right_side_points(geo: hou.Geometry) -> list[hou.Point]:
    candidates = [
        point
        for point in geo.points()
        if point.stringAttribValue("id").startswith(base_sops.ID.BASESTERNUM)
        and point.position()[0] > 0.0
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
    points = points_by_attribute(geo)
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

    headfront_point = points.get(headfront(1))
    headmiddle_point = points.get(headtopmiddle(1))
    headback_point = points.get(headback(1))
    assert (
        headfront_point is not None
        and headmiddle_point is not None
        and headback_point is not None
    ), "Expected head side reference points"
    headfront_position = headfront_point.position()
    headback_position = headback_point.position()

    side_points = []
    for layer, (front_ratio, back_ratio) in enumerate(
        zip(front_ratios, back_ratios),
        start=1,
    ):
        front_position = center_position + (headfront_position - center_position) * front_ratio
        back_position = center_position + (headback_position - center_position) * back_ratio
        middle_position = (front_position + back_position) / 2.0
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
    geo = node.geometry()
    for point in geo.points():
        if point.position()[0] >= 0.0:
            continue
        point_id = point.stringAttribValue("id")
        first_digit = next(
            (index for index, character in enumerate(point_id) if character.isdigit()),
            None,
        )
        assert first_digit is not None, f"Expected a numeric suffix in point id {point_id}"
        point.setAttribValue(
            "id",
            f"{point_id[:first_digit]}-{point_id[first_digit:]}",
        )
