from typing import Any

import hou

from ..sternums import attributes as sternum_attributes
from ..bases import attributes as base_attributes
from ..helper import points_by_id, points_from_geo, positions_from_geo, replace_points
from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm, get_parms
from .attributes import headback, headchelicerae, headfront, headtopmiddle, headsupport

def extract_base_rim(node: hou.SopNode) -> None:
    geo = node.geometry()
    excluded_ids = {
        base_attributes.basesternum(0),
        base_attributes.basesternum(1, 1),
        base_attributes.basesternum(-1, 1),
    }
    point_data = [
        (point.stringAttribValue("id"), point.position())
        for point in geo.points()
        if point.stringAttribValue("id") not in excluded_ids
        and point.stringAttribValue("id").startswith("base")
    ]
    replace_points(geo, point_data)


def extract_work_base(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    upper0_pos, upper1_pos, upper2_pos = _get_chelicerae_upper_positions(geo, parent)

    excluded_ids = {
        base_attributes.basesternum(1, 1),
    }
    point_data = [
        (point.stringAttribValue("id"), point.position())
        for point in geo.points()
        if point.position()[0] >= -1e-4
        and point.stringAttribValue("id") not in excluded_ids
        and (
                   point.stringAttribValue("id").startswith("base")
                   or point.stringAttribValue("id") == sternum_attributes.sternumrim(0)
        )
    ]
    point_data.append((headchelicerae(0), upper0_pos))
    point_data.append((headchelicerae(1), upper1_pos))
    point_data.append((headchelicerae(2), upper2_pos))
    replace_points(geo, point_data)


def _get_chelicerae_upper_positions(geo: hou.Geometry, parent: hou.OpNode) -> tuple[hou.Vector3, hou.Vector3, hou.Vector3]:
    chelicerae_height_ratio = get_float_parm(parent, "chelicerae_height_ratio")
    basesternum0, basemaxilla1 = points_from_geo(geo, base_attributes.basesternum(0), base_attributes.basemaxilla(1))
    height = basemaxilla1.position().distanceTo(basesternum0.position()) * chelicerae_height_ratio
    height_offset = hou.Vector3(0.0, height, 0.0)

    upper0_pos = basesternum0.position() + height_offset
    upper2_pos = basemaxilla1.position() + height_offset
    upper1_pos = (upper0_pos + upper2_pos) / 2.0
    return upper0_pos, upper1_pos, upper2_pos


def add_corners_half(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)
    points = points_by_id(geo)
    ref = _get_corner_reference_positions(geo)
    params = get_parms(parent)

    top_corners = _compute_top_corners(ref, params)
    support_points = _compute_support_points(ref, top_corners, params)

    point_data = [
        (point_id, point.position())
        for point_id, point in points.items()
        if point_id not in (sternum_attributes.sternumrim(0), base_attributes.basesternum(0))
    ]
    new_points = list(top_corners.items()) + list(support_points.items())
    replace_points(geo, point_data + new_points)

def _get_corner_reference_positions(geo: hou.Geometry) -> dict[str, hou.Vector3]:
    points = points_by_id(geo)
    expected_ids = (
        sternum_attributes.sternumrim(0),
        headchelicerae(0),
        base_attributes.basesternum(0),
        base_attributes.basesternum(1, 2),
        base_attributes.basesternum(3),
        base_attributes.basesternum(5, 1),
        base_attributes.baseend(0),
    )
    assert all(point_id in points for point_id in expected_ids), "Expected head reference points"
    positions = positions_from_geo(geo, *expected_ids)
    return dict(zip(expected_ids, positions))

def _compute_top_corners(
    ref: dict[str, hou.Vector3],
    params: Any,
) -> dict[str, hou.Vector3]:
    height = ref[base_attributes.baseend(0)][2] - ref[headchelicerae(0)][2]
    flat_ratiox, flat_ratioy = params.top_width_length_ratios
    y_offset = hou.Vector3(0.0, height * params.height_ratio, 0.0)
    z_offset = hou.Vector3(0.0, 0.0, height * flat_ratioy)

    base_length = abs(ref[sternum_attributes.sternumrim(0)].z() - ref[base_attributes.baseend(0)].z())
    flat_offset_z = hou.Vector3(0.0, 0.0, base_length * params.top_face_offset_ratio)
    sternumrim0_y = ref[sternum_attributes.sternumrim(0)][1]

    def align_front(position: hou.Vector3) -> hou.Vector3:
        return position + y_offset - hou.Vector3(0.0, position[1] - sternumrim0_y, 0.0)

    hf0 = align_front(ref[headchelicerae(0)]) + flat_offset_z
    hf1 = align_front(ref[base_attributes.basesternum(1, 2)])
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

    hs0 = top_corners[headfront(0)] * (1.0 - r1) + ref[base_attributes.basesternum(0)] * r1
    hs2 = top_corners[headfront(1)] * (1.0 - r1) + ref[base_attributes.basesternum(1, 2)] * r1
    hs1 = (hs0 + hs2) / 2.0
    hs3 = top_corners[headtopmiddle(1)] * (1.0 - r_mid) + ref[base_attributes.basesternum(3)] * r_mid
    hs4 = top_corners[headback(1)] * (1.0 - r2) + ref[base_attributes.basesternum(5, 1)] * r2
    hs5 = top_corners[headback(0)] * (1.0 - r2) + ref[base_attributes.baseend(0)] * r2
    return {
        headsupport(0): hs0,
        headsupport(1): hs1,
        headsupport(2): hs2,
        headsupport(3): hs3,
        headsupport(4): hs4,
        headsupport(5): hs5,
    }
