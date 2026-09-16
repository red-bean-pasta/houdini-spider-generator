import math

import hou

from helper import bridge_loops
from houkit.models import Moject
from legs.attributes import LegParam, Region

def build_segment_tubes(
    geo: hou.Geometry,
    param: LegParam,
) -> Moject[list[hou.Point]]:
    segments, messages = get_leg_points(param)

    seg_pts: list[hou.Point] = []
    for seg in segments:
        cur_seg_pts = [geo.createPoint() for _ in range(8)]
        for pt, pos in zip(cur_seg_pts, seg):
            pt.setPosition(pos)
        seg_pts.extend(cur_seg_pts)

        start_loop = [cur_seg_pts[0], cur_seg_pts[1], cur_seg_pts[3], cur_seg_pts[2]]
        end_loop = [cur_seg_pts[4], cur_seg_pts[5], cur_seg_pts[7], cur_seg_pts[6]]
        bridge_loops(geo, start_loop, end_loop, primitive_attr=("region", Region.LEGSEGMENT))

    return Moject(seg_pts, messages)

def get_leg_points(
    param: LegParam,
) -> Moject[list[list[hou.Vector3]]]:
    assert len(param.yaw_flex_specs) == len(param.length_ratios)

    coxa_width, coxa_length = param.coxa_width_length
    coxa_height = coxa_width * param.coxa_trochanter_height_ratio
    half_w = coxa_width / 2.0
    top_y = 0.0
    btm_y = -coxa_height
    start_z = 0.0
    end_z = -coxa_length
    coxa = [
        hou.Vector3(half_w, top_y, start_z),
        hou.Vector3(-half_w, top_y, start_z),
        hou.Vector3(half_w, btm_y, start_z),
        hou.Vector3(-half_w, btm_y, start_z),
        hou.Vector3(half_w, top_y, end_z),
        hou.Vector3(-half_w, top_y, end_z),
        hou.Vector3(half_w, btm_y, end_z),
        hou.Vector3(-half_w, btm_y, end_z),
    ]

    messages: list[str] = []
    segments: list[list[hou.Vector3]] = [coxa]
    for i, (max_yaw, min_flex) in enumerate(param.yaw_flex_specs):
        length_ratio_to_former = (
            param.length_ratios[i] / param.length_ratios[i - 1]
            if i > 0 else
            param.length_ratios[0] / 1.0
        )
        cur_height_ratio = (
            param.coxa_trochanter_height_ratio
            if i == 0 else
            param.other_segment_height_ratio
        )
        (former_wedged, latter), seg_messages = append_segment(
            segments[-1],
            cur_height_ratio,
            param.shrink_ratios,
            length_ratio_to_former,
            param.spine_ratio,
            max_yaw,
            min_flex,
            param.minimum_membrane,
        )
        messages.extend(seg_messages)
        segments[-1] = former_wedged
        segments.append(latter)

    assert len(segments) == len(param.yaw_flex_specs) + 1
    return Moject(segments, messages)

def append_segment(
    former_positions: list[hou.Vector3],
    height_ratio: float,
    section_shrink_ratios: tuple[float, float],
    length_ratio: float,
    spine_ratio: float,
    max_yaw: float,
    min_flex: float,
    minimum_membrane: tuple[float, float],
) -> Moject[tuple[list[hou.Vector3], list[hou.Vector3]]]:
    assert len(former_positions) == 8, f"Expected 8 positions for former segment, got {len(former_positions)}"

    # former_positions are ordered:
    # 0: start top +X, 1: start top -X, 2: start btm +X, 3: start btm -X
    # 4: end top +X,   5: end top -X,   6: end btm +X,   7: end btm -X
    start_top1 = former_positions[0]
    # start_topn1 = former_positions[1]
    start_btm1 = former_positions[2]
    start_btmn1 = former_positions[3]
    end_top1 = former_positions[4]
    end_topn1 = former_positions[5]
    end_btm1 = former_positions[6]
    end_btmn1 = former_positions[7]

    former_width = end_top1.x() - end_topn1.x()
    former_height = end_top1.y() - end_btm1.y()
    former_length = start_top1.z() - end_top1.z()
    former_size = (former_width, former_height)

    in_shrink, between_shrink = section_shrink_ratios
    latter_start_width = former_width * between_shrink
    latter_start_height = latter_start_width * height_ratio
    latter_start_size = (latter_start_width, latter_start_height)
    latter_length = former_length * length_ratio

    latter_end_width = latter_start_width * in_shrink
    latter_end_height = latter_start_height * in_shrink

    (offset, wedge_angle), messages = calc_segment_offset_and_wedge(
        max_yaw,
        min_flex,
        spine_ratio,
        (former_size, latter_start_size),
        minimum_membrane,
    )

    latter_segment = build_latter_segment_positions(
        end_top1,
        offset,
        (latter_start_width, latter_start_height),
        (latter_end_width, latter_end_height),
        latter_length,
        wedge_angle,
        spine_ratio,
    )
    former_positions_list = apply_former_segment_wedge(
        former_positions,
        start_btm1,
        start_btmn1,
        end_btm1,
        end_btmn1,
        former_height,
        wedge_angle,
    )

    return Moject((former_positions_list, latter_segment), messages)


def build_latter_segment_positions(
    former_end_top: hou.Vector3,
    offset: hou.Vector2,
    start_size: tuple[float, float],
    end_size: tuple[float, float],
    length: float,
    wedge_angle: float,
    spine_ratio: float,
) -> list[hou.Vector3]:
    start_width, start_height = start_size
    end_width, end_height = end_size

    start_top_y = former_end_top.y() + offset.y()
    start_btm_y = start_top_y - start_height
    start_z = former_end_top.z() - offset.x()
    end_z = start_z - length
    start_hw = start_width / 2.0
    end_hw = end_width / 2.0

    start_btm_z = start_z - start_height * math.tan(math.radians(wedge_angle))
    end_top_y = start_top_y - (start_height - end_height) * spine_ratio
    end_btm_y = end_top_y - end_height

    return [
        hou.Vector3(start_hw, start_top_y, start_z),
        hou.Vector3(-start_hw, start_top_y, start_z),
        hou.Vector3(start_hw, start_btm_y, start_btm_z),
        hou.Vector3(-start_hw, start_btm_y, start_btm_z),
        hou.Vector3(end_hw, end_top_y, end_z),
        hou.Vector3(-end_hw, end_top_y, end_z),
        hou.Vector3(end_hw, end_btm_y, end_z),
        hou.Vector3(-end_hw, end_btm_y, end_z),
    ]


def apply_former_segment_wedge(
    former_positions: list[hou.Vector3],
    start_btm1: hou.Vector3,
    start_btmn1: hou.Vector3,
    end_btm1: hou.Vector3,
    end_btmn1: hou.Vector3,
    former_height: float,
    wedge_angle: float,
) -> list[hou.Vector3]:
    delta_z = former_height * math.tan(math.radians(wedge_angle))
    new_end_btm1_z = min(end_btm1.z() + delta_z, start_btm1.z())
    new_end_btmn1_z = min(end_btmn1.z() + delta_z, start_btmn1.z())

    former_positions_list = list(former_positions)
    former_positions_list[6] = hou.Vector3(end_btm1.x(), end_btm1.y(), new_end_btm1_z)
    former_positions_list[7] = hou.Vector3(end_btmn1.x(), end_btmn1.y(), new_end_btmn1_z)
    return former_positions_list


def calc_segment_offset_and_wedge(
    max_yaw: float,
    min_flex: float,
    spine_ratio: float,
    segment_size: tuple[tuple[float, float], tuple[float, float]],
    minimum_membrane: tuple[float, float],
) -> Moject[tuple[hou.Vector2, float]]:
    (former_width, former_height), (latter_width, latter_height) = segment_size

    (offset_x, wedge_angle), messages = calc_membrane_spec(max_yaw, min_flex, segment_size, minimum_membrane)

    # Keep the spine position (the point at spine_ratio from the top) aligned
    # across the joint, moving the latter segment in either vertical direction.
    offset_y = (latter_height - former_height) * spine_ratio

    wedged_x = abs(offset_y) * math.tan(math.radians(wedge_angle))
    offset_x -= wedged_x
    offset_x = max(offset_x, minimum_membrane[0])

    return Moject((hou.Vector2(offset_x, offset_y), wedge_angle), messages)

def calc_membrane_spec(
    max_yaw_deg: float,
    min_flex_deg: float,
    segment_sections: tuple[tuple[float, float], tuple[float, float]],
    min_return: tuple[float, float],
    max_wedge_deg: float = 45,
    max_distance_ratio: float = 1.0,
) -> Moject[tuple[float, float]]:
    max_yaw_deg = abs(max_yaw_deg)
    assert min_flex_deg > 0
    assert max_yaw_deg <= 90

    min_distance, min_angle = min_return
    assert min_distance > 0 and 0 < min_angle < 45

    messages: list[str] = []
    (former_width, former_height), (latter_width, latter_height) = segment_sections
    distance = latter_width / 2 * math.sin(math.radians(max_yaw_deg))
    distance = max(distance, min_distance)

    if min_flex_deg >= 180:
        angle = min_angle
        return Moject((distance, angle), messages)

    min_height = min(former_height, latter_height)
    angle, wedge_messages = solve_membrane_wedge_deg(
        min_flex_deg,
        distance,
        min_height,
    )
    messages.extend(wedge_messages)
    angle = max(angle, min_return[1])
    limited_distance, limited_angle, limit_messages = apply_membrane_spec_limits(
        distance,
        angle,
        min_distance,
        min_flex_deg,
        min_height,
        former_width,
        latter_width,
        max_wedge_deg,
        max_distance_ratio,
    )
    messages.extend(limit_messages)

    return Moject((limited_distance, limited_angle), messages)


def apply_membrane_spec_limits(
    distance: float,
    angle: float,
    min_distance: float,
    min_flex_deg: float,
    min_height: float,
    former_width: float,
    latter_width: float,
    max_wedge_deg: float,
    max_distance_ratio: float,
) -> tuple[float, float, list[str]]:
    if angle <= max_wedge_deg:
        return distance, angle, []

    angle = max_wedge_deg
    distance = solve_membrane_thickness_deg(
        180 - 2 * max_wedge_deg - min_flex_deg,
        min_height,
        max_wedge_deg,
    )
    messages: list[str] = []
    max_distance = max(former_width, latter_width) * max_distance_ratio
    if distance > max_distance:
        max_membrane_angle = math.degrees(
            math.atan(max_distance * math.cos(math.radians(max_wedge_deg)) / min_height)
        )
        min_flex_ceiling = 180 - 2 * max_wedge_deg - max_membrane_angle
        messages.append(
            f"Membrane distance ({distance:.4f}) exceeded max_distance_ratio limit "
            f"({max_distance:.4f}). Max angle ceiling reached with max_wedge_deg={max_wedge_deg}° "
            f"and max_distance_ratio={max_distance_ratio}, limiting min flex angle ceiling to {min_flex_ceiling:.2f}° "
            f"(requested {min_flex_deg:.2f}°)."
        )
        distance = max_distance
    distance = max(distance, min_distance)
    return distance, angle, messages

def solve_membrane_wedge_deg(
    min_flex: float,
    membrane_thickness: float,
    min_height: float,
    tolerance: float = 1e-5,
    iterations: int = 50,
) -> Moject[float]:
    wedge_rad, messages = solve_membrane_wedge_rad(
        math.radians(min_flex),
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return Moject(math.degrees(wedge_rad), messages)

def solve_membrane_wedge_rad(
    min_flex: float,
    membrane_thickness: float,
    min_height: float,
    tolerance: float = 1e-5,
    iterations: int = 50,
) -> Moject[float]:
    remain_rad, messages = solve_membrane_wedge_remain_rad(
        min_flex,
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return Moject(math.pi / 2 - remain_rad, messages)

def solve_membrane_wedge_remain_rad(
    min_flex: float,
    membrane_thickness: float,
    min_height: float,
    tolerance: float = 1e-5,
    iterations: int = 50,
) -> Moject[float]:
    """
    :solve:
        u: pi / 2 - wedge_angle
        w: max rotate angle introduced by membrane thickness
        2u - w = min_flex
        tan(w) = d / (h / sin(u))
    :return: in radians
    """
    assert min_height > 0 and membrane_thickness > 0

    k = membrane_thickness / min_height

    u = min_flex * 0.5
    f = 0.0
    for _ in range(iterations):
        w = 2.0 * u - min_flex
        cos_w = math.cos(w)
        assert abs(cos_w) >= tolerance, "Solver reached tan(w) singularity"

        f = math.tan(w) - k * math.sin(u)
        if abs(f) < tolerance:
            return Moject(u)
        df = 2.0 / (cos_w * cos_w) - k * math.cos(u)
        assert abs(df) >= tolerance, "Derivative too small"
        u -= f / df

    msg = (
        f"Membrane wedge solver exhausted {iterations} iterations without converging to tolerance {tolerance:.2e} "
        f"(final residual: {abs(f):.4e}, min_flex: {math.degrees(min_flex):.2f}°, "
        f"membrane_thickness: {membrane_thickness:.4f}, min_height: {min_height:.4f})."
    )
    return Moject(u, [msg])

def solve_membrane_thickness_deg(
    needed_angle: float,
    min_height: float,
    wedge_angle: float,
) -> float:
    return solve_membrane_thickness_rad(
        math.radians(needed_angle),
        min_height,
        math.radians(wedge_angle),
    )

def solve_membrane_thickness_rad(
    needed_angle: float,
    min_height: float,
    wedge_angle: float,
) -> float:
    """
    :param needed_angle: in radians
    :param min_height:
    :param wedge_angle: in radians
    :return:
    """
    # d / tan(needed_angle) = l = min_height / cos(wedge_angle)
    return min_height / math.cos(wedge_angle) * math.tan(needed_angle)


