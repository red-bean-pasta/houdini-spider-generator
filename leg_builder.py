import math
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Self

import hou

from utilities.common import (
    MessagedResult,
    add_prim_attr,
    fill_face,
    points_to_positions,
)
from utilities.topology import loop_cut


class Region(StrEnum):
    LEGSEGMENT = auto()
    LEGMEMBRANE = auto()


@dataclass
class LegParam:
    coxa_size: tuple[float, float, float]
    length_ratios: tuple[float, ...] | list[float]
    yaw_flex_specs: tuple[tuple[float, float], ...]

    tarsus_wedge_angle: float = 45.0

    height_ratio: float = 1.15
    spine_ratio: float = 0.5
    shrink_ratios: tuple[float, float] = (0.95, 0.875)
    support_loop_ratio: float = 0.015

    minimum_membrane: tuple[float, float] = (1.0, 5.0)

    def __post_init__(self) -> None:
        assert len(self.length_ratios) == len(self.yaw_flex_specs), (
            f"Length mismatch: length_ratios ({len(self.length_ratios)}) != yaw_flex_specs ({len(self.yaw_flex_specs)})"
        )

    @classmethod
    def from_specs(
        cls,
        coxa_size: tuple[float, float, float],
        length_ratios: tuple[float, ...] | list[float],
        max_segment_yaws: tuple[float, ...] | list[float],
        min_segment_flexes: tuple[float, ...] | list[float],
        **kwargs,
    ) -> Self:
        assert len(max_segment_yaws) == len(min_segment_flexes), (
            f"Spec mismatch: max_segment_yaws ({len(max_segment_yaws)}) != min_segment_flexes ({len(min_segment_flexes)})"
        )
        assert len(length_ratios) == len(max_segment_yaws), (
            f"Length mismatch: length_ratios ({len(length_ratios)}) != max_segment_yaws ({len(max_segment_yaws)})"
        )
        segment_specs = tuple(zip(max_segment_yaws, min_segment_flexes))
        return cls(
            coxa_size=coxa_size,
            length_ratios=length_ratios,
            yaw_flex_specs=segment_specs,
            **kwargs,
        )


def build_leg(
    geo: hou.Geometry,
    param: LegParam,
) -> MessagedResult[tuple[list[hou.Point], list[hou.Point], list[hou.Point]]]:
    add_prim_attr(geo, "region", "")

    seg_pts, warnings = _build_segment_tubes(geo, param)
    thickness_pts = _add_segment_thickness(geo, seg_pts, param.support_loop_ratio)
    all_seg_pts = _add_segment_loop_cuts(geo, seg_pts, param.support_loop_ratio)
    mem_pts = _fill_membranes(geo, thickness_pts)
    all_mem_pts = _add_membrane_loop_cuts(geo, seg_pts, thickness_pts, mem_pts, param.support_loop_ratio)
    _close_tarsus(geo, all_seg_pts, param.tarsus_wedge_angle)
    return MessagedResult((all_seg_pts, thickness_pts, all_mem_pts), warnings)


build = build_leg


def _build_segment_tubes(
    geo: hou.Geometry,
    param: LegParam,
) -> MessagedResult[list[hou.Point]]:
    segments, messages = _get_leg_points(param)

    seg_pts: list[hou.Point] = []
    for seg in segments:
        cur_seg_pts = [geo.createPoint() for _ in range(8)]
        for pt, pos in zip(cur_seg_pts, seg):
            pt.setPosition(pos)
        seg_pts.extend(cur_seg_pts)

        start_loop = [cur_seg_pts[0], cur_seg_pts[1], cur_seg_pts[3], cur_seg_pts[2]]
        end_loop = [cur_seg_pts[4], cur_seg_pts[5], cur_seg_pts[7], cur_seg_pts[6]]
        for j in range(4):
            next_j = (j + 1) % 4
            prim = fill_face(geo, [
                start_loop[j],
                start_loop[next_j],
                end_loop[next_j],
                end_loop[j],
            ])
            prim.setAttribValue("region", Region.LEGSEGMENT)

    return MessagedResult(seg_pts, messages)

def _get_leg_points(
    param: LegParam,
) -> MessagedResult[list[list[hou.Vector3]]]:
    assert len(param.yaw_flex_specs) == len(param.length_ratios)

    coxa_width, coxa_height, coxa_length = param.coxa_size
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
        cur_height_ratio = 1.0 if i == 0 else param.height_ratio
        (former_wedged, latter), seg_messages = _append_segment(
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
    return MessagedResult(segments, messages)

def _append_segment(
    former_positions: list[hou.Vector3],
    height_ratio: float,
    section_shrink_ratios: tuple[float, float],
    length_ratio: float,
    spine_ratio: float,
    max_yaw: float,
    min_flex: float,
    minimum_membrane: tuple[float, float],
) -> MessagedResult[tuple[list[hou.Vector3], list[hou.Vector3]]]:
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

    (offset, wedge_angle), messages = _calc_segment_offset_and_wedge(
        max_yaw,
        min_flex,
        spine_ratio,
        (former_size, latter_start_size),
        minimum_membrane,
    )

    latter_start_top_y = end_top1.y() + offset.y()
    latter_start_btm_y = latter_start_top_y - latter_start_height
    latter_start_z = end_top1.z() - offset.x()
    latter_end_z = latter_start_z - latter_length
    latter_start_hw = latter_start_width / 2.0
    latter_end_hw = latter_end_width / 2.0

    delta_z_latter = latter_start_height * math.tan(math.radians(wedge_angle))
    latter_start_btm_z = latter_start_z - delta_z_latter

    offset_y_in = -(latter_start_height - latter_end_height) * spine_ratio
    latter_end_top_y = latter_start_top_y + offset_y_in
    latter_end_btm_y = latter_end_top_y - latter_end_height

    latter_segment = [
        hou.Vector3(latter_start_hw, latter_start_top_y, latter_start_z),
        hou.Vector3(-latter_start_hw, latter_start_top_y, latter_start_z),
        hou.Vector3(latter_start_hw, latter_start_btm_y, latter_start_btm_z),
        hou.Vector3(-latter_start_hw, latter_start_btm_y, latter_start_btm_z),
        hou.Vector3(latter_end_hw, latter_end_top_y, latter_end_z),
        hou.Vector3(-latter_end_hw, latter_end_top_y, latter_end_z),
        hou.Vector3(latter_end_hw, latter_end_btm_y, latter_end_z),
        hou.Vector3(-latter_end_hw, latter_end_btm_y, latter_end_z),
    ]

    delta_z_former = former_height * math.tan(math.radians(wedge_angle))
    new_end_btm1_z = min(end_btm1.z() + delta_z_former, start_btm1.z())
    new_end_btmn1_z = min(end_btmn1.z() + delta_z_former, start_btmn1.z())

    former_positions_list = list(former_positions)
    former_positions_list[6] = hou.Vector3(end_btm1.x(), end_btm1.y(), new_end_btm1_z)
    former_positions_list[7] = hou.Vector3(end_btmn1.x(), end_btmn1.y(), new_end_btmn1_z)

    return MessagedResult((former_positions_list, latter_segment), messages)

def _calc_segment_offset_and_wedge(
    max_yaw: float,
    min_flex: float,
    spine_ratio: float,
    segment_size: tuple[tuple[float, float], tuple[float, float]],
    minimum_membrane: tuple[float, float],
) -> MessagedResult[tuple[hou.Vector2, float]]:
    (former_width, former_height), (latter_width, latter_height) = segment_size

    (offset_x, wedge_angle), messages = _calc_membrane_spec(max_yaw, min_flex, segment_size, minimum_membrane)

    offset_y = (former_height - latter_height) * spine_ratio
    if offset_y > 0:
        offset_y *= -1

    wedged_x = abs(offset_y) * math.tan(math.radians(wedge_angle))
    offset_x -= wedged_x
    offset_x = max(offset_x, minimum_membrane[0])

    return MessagedResult((hou.Vector2(offset_x, offset_y), wedge_angle), messages)

def _calc_membrane_spec(
    max_yaw_deg: float,
    min_flex_deg: float,
    segment_sections: tuple[tuple[float, float], tuple[float, float]],
    min_return: tuple[float, float],
    max_wedge_deg: float = 45,
    max_distance_ratio: float = 1.0,
) -> MessagedResult[tuple[float, float]]:
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
        return MessagedResult((distance, angle), messages)

    min_height = min(former_height, latter_height)
    angle, wedge_messages = _solve_membrane_wedge_deg(
        min_flex_deg,
        distance,
        min_height,
    )
    messages.extend(wedge_messages)
    angle = max(angle, min_return[1])
    if angle > max_wedge_deg:
        angle = max_wedge_deg
        distance = _solve_membrane_thickness_deg(
            180 - 2 * max_wedge_deg - min_flex_deg,
            min_height,
            max_wedge_deg,
        )
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

    return MessagedResult((distance, angle), messages)

def _solve_membrane_wedge_deg(
    min_flex: float,
    membrane_thickness: float,
    min_height: float,
    tolerance: float = 1e-5,
    iterations: int = 50,
) -> MessagedResult[float]:
    wedge_rad, messages = _solve_membrane_wedge_rad(
        math.radians(min_flex),
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return MessagedResult(math.degrees(wedge_rad), messages)

def _solve_membrane_wedge_rad(
    min_flex: float,
    membrane_thickness: float,
    min_height: float,
    tolerance: float = 1e-5,
    iterations: int = 50,
) -> MessagedResult[float]:
    remain_rad, messages = _solve_membrane_wedge_remain_rad(
        min_flex,
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return MessagedResult(math.pi / 2 - remain_rad, messages)

def _solve_membrane_wedge_remain_rad(
    min_flex: float,
    membrane_thickness: float,
    min_height: float,
    tolerance: float = 1e-5,
    iterations: int = 50,
) -> MessagedResult[float]:
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
            return MessagedResult(u)
        df = 2.0 / (cos_w * cos_w) - k * math.cos(u)
        assert abs(df) >= tolerance, "Derivative too small"
        u -= f / df

    msg = (
        f"Membrane wedge solver exhausted {iterations} iterations without converging to tolerance {tolerance:.2e} "
        f"(final residual: {abs(f):.4e}, min_flex: {math.degrees(min_flex):.2f}°, "
        f"membrane_thickness: {membrane_thickness:.4f}, min_height: {min_height:.4f})."
    )
    return MessagedResult(u, [msg])

def _solve_membrane_thickness_deg(
    needed_angle: float,
    min_height: float,
    wedge_angle: float,
) -> float:
    return _solve_membrane_thickness_rad(
        math.radians(needed_angle),
        min_height,
        math.radians(wedge_angle),
    )

def _solve_membrane_thickness_rad(
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


def _add_segment_thickness(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    support_loop_ratio: float,
) -> list[hou.Point]:
    assert len(seg_pts) % 8 == 0, f"Expected seg_pts length to be a multiple of 8, got {len(seg_pts)}"
    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_segs = len(seg_pts) // 8
    thickness_pts: list[hou.Point] = []

    for i in range(num_segs - 1):
        former_end = seg_pts[i * 8 + 4:(i + 1) * 8]
        latter_start = seg_pts[(i + 1) * 8:(i + 1) * 8 + 4]

        former_inset = _inset_loop(geo, former_end, cut_length)
        latter_inset = _inset_loop(geo, latter_start, cut_length)

        e_loop = [former_end[0], former_end[1], former_end[3], former_end[2]]
        ie_loop = [former_inset[0], former_inset[1], former_inset[3], former_inset[2]]
        for j in range(4):
            next_j = (j + 1) % 4
            prim = fill_face(
                geo,
                [
                    e_loop[next_j],
                    e_loop[j],
                    ie_loop[j],
                    ie_loop[next_j],
                ],
                True,
            )
            prim.setAttribValue("region", Region.LEGSEGMENT)

        s_loop = [latter_start[0], latter_start[1], latter_start[3], latter_start[2]]
        is_loop = [latter_inset[0], latter_inset[1], latter_inset[3], latter_inset[2]]
        for j in range(4):
            next_j = (j + 1) % 4
            prim = fill_face(
                geo,
                [
                    s_loop[j],
                    s_loop[next_j],
                    is_loop[next_j],
                    is_loop[j],
                ],
                True,
            )
            prim.setAttribValue("region", Region.LEGSEGMENT)

        thickness_pts.extend([*former_inset, *latter_inset])

    return thickness_pts

def _inset_loop(
    geo: hou.Geometry,
    pts: list[hou.Point],
    cut_length: float,
) -> list[hou.Point]:
    assert len(pts) == 4
    pos0, pos1, pos2, pos3 = points_to_positions(pts)
    v_down = pos2 - pos0
    dir_down = v_down.normalized()

    pos_in0 = pos0 + hou.Vector3(-cut_length, 0, 0) + dir_down * cut_length
    pos_in1 = pos1 + hou.Vector3(cut_length, 0, 0) + dir_down * cut_length
    pos_in2 = pos2 + hou.Vector3(-cut_length, 0, 0) - dir_down * cut_length
    pos_in3 = pos3 + hou.Vector3(cut_length, 0, 0) - dir_down * cut_length

    p_in = [geo.createPoint() for _ in range(4)]
    for p, pos in zip(p_in, (pos_in0, pos_in1, pos_in2, pos_in3)):
        p.setPosition(pos)
    return p_in


def _add_segment_loop_cuts(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    support_loop_ratio: float,
) -> list[hou.Point]:
    assert len(seg_pts) % 8 == 0, f"Expected seg_pts length to be a multiple of 8, got {len(seg_pts)}"
    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_segs = len(seg_pts) // 8
    all_seg_pts: list[hou.Point] = []

    for i in range(num_segs):
        cur_pts = seg_pts[i * 8:(i + 1) * 8]
        start_pts = cur_pts[:4]
        end_pts = cur_pts[4:]

        start_cut = _add_tube_loop_cut(geo, start_pts, end_pts, cut_length)
        end_cut = _add_tube_loop_cut(geo, end_pts, start_cut, cut_length)

        all_seg_pts.extend([
            *start_pts,
            *start_cut,
            *end_cut,
            *end_pts,
        ])

    return all_seg_pts


def _fill_membranes(
    geo: hou.Geometry,
    thickness_pts: list[hou.Point],
) -> list[hou.Point]:
    if not thickness_pts:
        return []

    add_prim_attr(geo, "region", "")
    assert len(thickness_pts) % 8 == 0, f"Expected thickness_pts length to be a multiple of 8, got {len(thickness_pts)}"

    membrane_points: list[hou.Point] = []
    num_joints = len(thickness_pts) // 8
    for i in range(num_joints):
        former_end = thickness_pts[i * 8:i * 8 + 4]
        latter_start = thickness_pts[i * 8 + 4:(i + 1) * 8]
        # fu: former upper, fb: former bottom, lu: latter upper, lb: latter bottom
        fu1, fu2, fb1, fb2 = former_end
        lu1, lu2, lb1, lb2 = latter_start

        (
            pos_fu1,
            pos_fu2,
            pos_fb1,
            pos_fb2,
            pos_lu1,
            pos_lu2,
            pos_lb1,
            pos_lb2,
        ) = points_to_positions(former_end + latter_start)

        lf = pos_fu1.distanceTo(pos_fb1)
        ll = pos_lu1.distanceTo(pos_lb1)
        membrane_length = (lf + ll) * 0.5

        # mu: midpoint upper, mb: midpoint bottom
        pos_mu1 = (pos_fu1 + pos_lu1) * 0.5
        pos_mu2 = (pos_fu2 + pos_lu2) * 0.5
        pos_mb1 = (pos_fb1 + pos_lb1) * 0.5
        pos_mb2 = (pos_fb2 + pos_lb2) * 0.5
        pos_mb1[1] = (pos_mb1.y() + (pos_mu1.y() - membrane_length)) * 0.5
        pos_mb2[1] = (pos_mb2.y() + (pos_mu2.y() - membrane_length)) * 0.5

        mu1 = geo.createPoint()
        mu2 = geo.createPoint()
        mb1 = geo.createPoint()
        mb2 = geo.createPoint()

        mu1.setPosition(pos_mu1)
        mu2.setPosition(pos_mu2)
        mb1.setPosition(pos_mb1)
        mb2.setPosition(pos_mb2)

        membrane_points.extend([mu1, mu2, mb1, mb2])

        former_loop = [fu1, fu2, fb2, fb1]
        mid_loop = [mu1, mu2, mb2, mb1]
        latter_loop = [lu1, lu2, lb2, lb1]

        for j in range(4):
            next_j = (j + 1) % 4
            prim1 = fill_face(geo, [
                former_loop[j],
                former_loop[next_j],
                mid_loop[next_j],
                mid_loop[j],
            ])
            prim1.setAttribValue("region", Region.LEGMEMBRANE)
            prim2 = fill_face(geo, [
                mid_loop[j],
                mid_loop[next_j],
                latter_loop[next_j],
                latter_loop[j],
            ])
            prim2.setAttribValue("region", Region.LEGMEMBRANE)

    return membrane_points


def _add_membrane_loop_cuts(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    thickness_pts: list[hou.Point],
    mem_pts: list[hou.Point],
    support_loop_ratio: float,
) -> list[hou.Point]:
    assert len(thickness_pts) % 8 == 0, f"Expected thickness_pts length to be a multiple of 8, got {len(thickness_pts)}"
    coxa_width = seg_pts[0].position().distanceTo(seg_pts[1].position())
    cut_length = coxa_width * support_loop_ratio

    num_joints = len(thickness_pts) // 8
    all_mem_pts: list[hou.Point] = []

    for i in range(num_joints):
        former_end = thickness_pts[i * 8:i * 8 + 4]
        latter_start = thickness_pts[i * 8 + 4:(i + 1) * 8]
        mid_pts = mem_pts[i * 4:(i + 1) * 4]

        # fu: former upper, lu: latter upper
        fu1 = former_end[0]
        lu1 = latter_start[0]
        half_width = fu1.position().distanceTo(lu1.position()) * 0.5
        if cut_length >= half_width:
            all_mem_pts.extend(mid_pts)
            continue

        former_cut = _add_tube_loop_cut(geo, former_end, mid_pts, cut_length)
        latter_cut = _add_tube_loop_cut(geo, latter_start, mid_pts, cut_length)
        all_mem_pts.extend([
            *former_cut,
            *mid_pts,
            *latter_cut,
        ])

    return all_mem_pts


def _close_tarsus(
    geo: hou.Geometry,
    seg_pts: list[hou.Point],
    tarsus_wedge_angle: float,
) -> None:
    assert len(seg_pts) >= 4, f"Expected at least 4 seg_pts, got {len(seg_pts)}"
    p4, p5, p6, p7 = seg_pts[-4:]
    prim = fill_face(geo, [p4, p6, p7, p5])
    prim.setAttribValue("region", Region.LEGSEGMENT)

    pos4, pos5, pos6, pos7 = points_to_positions([p4, p5, p6, p7])
    offset_y = pos4.y() - pos6.y()
    offset_z = offset_y * math.tan(math.radians(tarsus_wedge_angle))

    p6.setPosition(hou.Vector3(pos6.x(), pos6.y(), pos6.z() - offset_z))
    p7.setPosition(hou.Vector3(pos7.x(), pos7.y(), pos7.z() - offset_z))


def _add_tube_loop_cut(
    geo: hou.Geometry,
    start_pts: list[hou.Point],
    end_pts: list[hou.Point],
    cut_length: float,
) -> list[hou.Point]:
    s0, s1, s2, s3 = start_pts
    e0, e1, e2, e3 = end_pts

    edge = geo.findEdge(s0, e0)
    assert edge is not None, f"Expected edge between {s0} and {e0}"
    prim = [p for p in edge.prims() if s1 in p.points()][0]
    cut_pts, _ = loop_cut(
        prim,
        s0,
        e0,
        cut_length,
        use_ratio=False,
    )
    m0, m1, m3, m2 = cut_pts
    return [m0, m1, m2, m3]
