import math

import hou

import base_sops
from utilities.common import (
    add_float_param,
    fill_face,
    get_float_parm,
    get_parm,
    get_parent,
    get_vector2_parm,
    rotation_to,
)
from utilities.nodes import (
    add_output,
    add_reloadable_subnet,
    sopify,
)


def build(
        spider: hou.SopNode,
        base: hou.SopNode,
) -> hou.SopNode:
    legs = add_reloadable_subnet(spider, "legs")
    legs.setInput(0, base)
    _add_parameters(legs)

    extracted = sopify(legs, legs.indirectInputs()[0], _extract_right_coxa)
    extruded = sopify(legs, extracted, _extrude_legs)
    add_output(legs, "OUT_LEGS", extruded)

    legs.layoutChildren()
    return legs


def _add_parameters(legs: hou.OpNode) -> None:
    add_float_param(
        legs,
        "segment_height_ratio",
        1,
        0.5,
        (0.0, None),
    )
    add_float_param(
        legs,
        "segment_lateral_ratio",
        1,
        0.5,
        (0.0, None),
        help="The top to thickest part : thickest part to the bottom"
    )
    add_float_param(
        legs,
        "coxa_width_ratios",
        4,
        (0.8, 0.8, 0.8, 0.8),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Ratio to the base sockets' width, ordered from the front legs to the hind legs.",
    )
    add_float_param(
        legs,
        "min_segment_flexes",
        7,
        (140, 180, 200, 30, 95, 150, 170),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_float_param(
        legs,
        "max_segment_yaws",
        7,
        (15, 25, 0, 0, 0, 0, 20),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_float_param(
        legs,
        "joint_shrink_ratio",
        2,
        (0.8, 0.8),
        (0.0, None),
    )
    add_float_param(
        legs,
        "minimum_membrane_spec",
        2,
        (1, 5.0),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Membrane distance in ratio to the latter segment's width; Wedge angle in degrees",
    )


def _extract_right_coxa(node: hou.SopNode) -> None:
    geo = node.geometry()
    socket_prims = [
        prim for prim in geo.prims()
        if prim.boundingBox().center().x() > 0 and prim.stringAttribValue("region").startswith(base_sops.Region.COXASOCKET)
    ]
    assert len(socket_prims) == 8, f"Expected 8 right coxa socket prims, got {len(socket_prims)}"

    used_points = {v.point() for prim in socket_prims for v in prim.vertices()}
    unused_points = [p for p in geo.points() if p not in used_points]
    geo.deletePoints(unused_points)


def _extrude_legs(
        node: hou.SopNode,
) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    shrink_ratio = get_vector2_parm(parent, "joint_shrink_ratio")
    spine_ratio = get_float_parm(parent, "segment_lateral_ratio")
    segment_height_ratio = get_float_parm(parent, "segment_height_ratio")
    coxa_width_ratios = get_parm(parent, "coxa_width_ratios", tuple[float, float, float, float])
    min_segment_flexes = get_parm(parent, "min_segment_flexes", tuple[float, ...])
    max_segment_yaws = get_parm(parent, "max_segment_yaws", tuple[float, ...])
    minimum_membrane = get_parm(parent, "minimum_membrane_spec", tuple[float, float])

    segment_specs = tuple(zip(max_segment_yaws[1:], min_segment_flexes[1:]))

    sockets = _get_right_coxa_socket_points(node)
    geo.deletePrims(geo.prims(), keep_points=True)

    for leg_idx, socket_pts in enumerate(sockets):
        p_top_sz, p_top_bz, p_btm_sz, p_btm_bz = socket_pts
        pos_top_sz = p_top_sz.position()
        pos_top_bz = p_top_bz.position()
        pos_btm_sz = p_btm_sz.position()
        pos_btm_bz = p_btm_bz.position()

        upper_width = (pos_top_bz - pos_top_sz).length()
        ratio = coxa_width_ratios[leg_idx]
        coxa_width = upper_width * ratio

        top_midpoint = (pos_top_sz + pos_top_bz) / 2.0
        btm_midpoint = (pos_btm_sz + pos_btm_bz) / 2.0
        coxa_height = top_midpoint.y() - btm_midpoint.y()
        coxa_length = coxa_height * segment_height_ratio

        origin = top_midpoint
        direction = hou.Vector3(top_midpoint.x() - btm_midpoint.x(), 0.0, top_midpoint.z() - btm_midpoint.z()).normalized()

        _extrude_leg(
            geo,
            socket_pts,
            origin,
            direction,
            (coxa_width, coxa_height, coxa_length),
            (shrink_ratio.x(), shrink_ratio.y()),
            spine_ratio,
            segment_specs,
            minimum_membrane,
        )

def _extrude_leg(
        geo: hou.Geometry,
        socket_pts: list[hou.Point],
        origin: hou.Vector3,
        direction: hou.Vector3,
        coxa_size: tuple[float, float, float],
        shrink_ratio: tuple[float, float],
        spine_ratio: float,
        segment_specs: tuple[tuple[float, float], ...],
        minimum_membrane: tuple[float, float],
) -> None:
    p_top_sz, p_top_bz, p_btm_sz, p_btm_bz = socket_pts

    segments = _build_leg_points(
        origin,
        direction,
        coxa_size,
        shrink_ratio,
        spine_ratio,
        segment_specs,
        minimum_membrane,
    )

    # Connect coxa
    coxa_start_loop = [p_top_bz, p_top_sz, p_btm_sz, p_btm_bz]
    coxa_end_positions = segments[0][4:]
    coxa_end_loop = [geo.createPoint() for _ in range(4)]
    for i in range(4):
        coxa_end_loop[i].setPosition(coxa_end_positions[i])
    for j in range(4):
        next_j = (j + 1) % 4
        fill_face(geo, [
            coxa_start_loop[j],
            coxa_start_loop[next_j],
            coxa_end_loop[next_j],
            coxa_end_loop[j],
        ])

    # Connect segments 1 to 6
    for seg in segments[1:]:
        start_loop = [geo.createPoint() for _ in range(4)]
        start_loop[0].setPosition(seg[0])
        start_loop[1].setPosition(seg[1])
        start_loop[2].setPosition(seg[3])
        start_loop[3].setPosition(seg[2])

        end_loop = [geo.createPoint() for _ in range(4)]
        end_loop[0].setPosition(seg[4])
        end_loop[1].setPosition(seg[5])
        end_loop[2].setPosition(seg[7])
        end_loop[3].setPosition(seg[6])

        for j in range(4):
            next_j = (j + 1) % 4
            fill_face(geo, [
                start_loop[j],
                start_loop[next_j],
                end_loop[next_j],
                end_loop[j],
            ])

def _get_right_coxa_socket_points(
        node: hou.SopNode,
) -> list[list[hou.Point]]:
    geo = node.geometry()
    prims = sorted(geo.prims(), key=lambda p: p.boundingBox().center().z())
    assert len(prims) == 8, f"Expected 8 socket prims, got {len(prims)}"

    groups = [prims[i:i + 2] for i in range(0, 8, 2)]
    result = []
    for group in groups:
        p_set = set()
        for prim in group:
            for v in prim.vertices():
                p_set.add(v.point())
        assert len(p_set) == 6, f"Expected 6 unique points in socket group, got {len(p_set)}"

        pts_prim0 = {v.point() for v in group[0].vertices()}
        pts_prim1 = {v.point() for v in group[1].vertices()}
        shared_pts = pts_prim0 & pts_prim1
        outer_pts = list(p_set - shared_pts)
        assert len(outer_pts) == 4, f"Expected 4 outer points, got {len(outer_pts)}"

        mid_y = sum(p.position().y() for p in outer_pts) / 4.0
        top_pts = [p for p in outer_pts if p.position().y() >= mid_y]
        btm_pts = [p for p in outer_pts if p.position().y() < mid_y]
        assert len(top_pts) == 2 and len(btm_pts) == 2

        top_pts.sort(key=lambda p: p.position().z())
        btm_pts.sort(key=lambda p: p.position().z())
        result.append([top_pts[0], top_pts[1], btm_pts[0], btm_pts[1]])

    return result


def _build_leg_points(
        origin: hou.Vector3,
        direction: hou.Vector3,
        coxa_size: tuple[float, float, float],
        shrink_ratio: tuple[float, float],
        spine_ratio: float,
        segment_specs: tuple[tuple[float, float], ...],
        minimum_membrane: tuple[float, float],
) -> list[list[hou.Vector3]]:
    segments = _build_leg(coxa_size, shrink_ratio, spine_ratio, segment_specs, minimum_membrane)
    assert len(segments) == 7 and all(len(segment_points) == 8 for segment_points in segments)

    q = rotation_to(hou.Vector3(0.0, 0.0, -1.0), direction.normalized())
    return [
        [q.rotate(p) + origin for p in segment]
        for segment in segments
    ]

def _build_leg(
        coxa_size: tuple[float, float, float],
        shrink_ratio: tuple[float, float],
        spine_ratio: float,
        segment_specs: tuple[tuple[float, float], ...],
        minimum_membrane: tuple[float, float],
) -> list[list[hou.Vector3]]:
    assert len(segment_specs) == 6  # TROCHANTER, FEMUR, PATELLA, TIBIA, METATARSUS, TARSUS

    coxa_width, coxa_height, coxa_length = coxa_size
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

    segments: list[list[hou.Vector3]] = [coxa]
    for max_yaw, min_flex in segment_specs:
        former_wedged, latter = _append_segment(
            segments[-1],
            shrink_ratio,
            spine_ratio,
            max_yaw,
            min_flex,
            minimum_membrane,
        )
        segments[-1] = former_wedged
        segments.append(latter)

    assert len(segments) == 7
    return segments

def _append_segment(
        former_positions: list[hou.Vector3],
        shrink_ratio: tuple[float, float],
        spine_ratio: float,
        max_yaw: float,
        min_flex: float,
        minimum_membrane: tuple[float, float],
) -> tuple[
    list[hou.Vector3],
    list[hou.Vector3]
]:
    assert len(former_positions) == 8, f"Expected 8 positions for former segment, got {len(former_positions)}"

    sorted_by_z = sorted(range(8), key=lambda i: former_positions[i].z())
    end_indices = sorted_by_z[:4]
    start_indices = sorted_by_z[4:]

    end_pts = [former_positions[i] for i in end_indices]
    max_end_y = max(p.y() for p in end_pts)
    min_end_y = min(p.y() for p in end_pts)
    mid_end_y = (max_end_y + min_end_y) / 2.0

    end_top_indices = [i for i in end_indices if former_positions[i].y() >= mid_end_y]
    end_btm_indices = [i for i in end_indices if former_positions[i].y() < mid_end_y]
    assert len(end_top_indices) == 2 and len(end_btm_indices) == 2, "Expected 2 top and 2 bottom end points"

    end_top1_idx = next(i for i in end_top_indices if former_positions[i].x() >= 0)
    end_topn1_idx = next(i for i in end_top_indices if former_positions[i].x() < 0)
    end_btm1_idx = next(i for i in end_btm_indices if former_positions[i].x() >= 0)
    end_btmn1_idx = next(i for i in end_btm_indices if former_positions[i].x() < 0)

    end_top1 = former_positions[end_top1_idx]
    end_topn1 = former_positions[end_topn1_idx]
    end_btm1 = former_positions[end_btm1_idx]
    end_btmn1 = former_positions[end_btmn1_idx]

    assert math.isclose(end_top1.y(), end_topn1.y(), abs_tol=1e-4) and \
           math.isclose(end_top1.x(), -end_topn1.x(), abs_tol=1e-4) and \
           math.isclose(end_top1.z(), end_topn1.z(), abs_tol=1e-4), "Top end points symmetry mismatch"
    assert math.isclose(end_btm1.y(), end_btmn1.y(), abs_tol=1e-4) and \
           math.isclose(end_btm1.x(), -end_btmn1.x(), abs_tol=1e-4) and \
           math.isclose(end_btm1.z(), end_btmn1.z(), abs_tol=1e-4), "Bottom end points symmetry mismatch"

    former_width = end_top1.x() - end_topn1.x()
    former_height = end_top1.y() - end_btm1.y()
    former_size = (former_width, former_height)

    start_top_z = max(former_positions[i].z() for i in start_indices)
    former_length = start_top_z - end_top1.z()

    latter_width = former_width * shrink_ratio[0]
    latter_height = former_height * shrink_ratio[1]
    latter_size = (latter_width, latter_height)
    latter_length = former_length

    offset, wedge_angle = _calc_segment_offset(
        max_yaw,
        min_flex,
        spine_ratio,
        (former_size, latter_size),
        minimum_membrane,
    )

    latter_start_top_y = end_top1.y() + offset.y()
    latter_start_btm_y = latter_start_top_y - latter_height
    latter_start_z = end_top1.z() - offset.x()
    latter_end_z = latter_start_z - latter_length
    latter_hw = latter_width / 2.0

    delta_z_latter = latter_height * math.tan(math.radians(wedge_angle))
    latter_start_btm_z = latter_start_z - delta_z_latter

    latter_segment = [
        hou.Vector3(latter_hw, latter_start_top_y, latter_start_z),
        hou.Vector3(-latter_hw, latter_start_top_y, latter_start_z),
        hou.Vector3(latter_hw, latter_start_btm_y, latter_start_btm_z),
        hou.Vector3(-latter_hw, latter_start_btm_y, latter_start_btm_z),
        hou.Vector3(latter_hw, latter_start_top_y, latter_end_z),
        hou.Vector3(-latter_hw, latter_start_top_y, latter_end_z),
        hou.Vector3(latter_hw, latter_start_btm_y, latter_end_z),
        hou.Vector3(-latter_hw, latter_start_btm_y, latter_end_z),
    ]

    delta_z_former = former_height * math.tan(math.radians(wedge_angle))
    former_positions_list = list(former_positions)
    former_positions_list[end_btm1_idx] = hou.Vector3(end_btm1.x(), end_btm1.y(), end_btm1.z() + delta_z_former)
    former_positions_list[end_btmn1_idx] = hou.Vector3(end_btmn1.x(), end_btmn1.y(), end_btmn1.z() + delta_z_former)

    return former_positions_list, latter_segment

def _calc_segment_offset(
        max_yaw: float,
        min_flex: float,
        spine_ratio: float,
        segment_size: tuple[tuple[float, float], tuple[float, float]],
        minimum_membrane: tuple[float, float],
) -> tuple[hou.Vector2, float]:
    former_size, latter_size = segment_size

    offset_x, wedge_angle = _calc_membrane_spec(max_yaw, min_flex, latter_size, minimum_membrane)

    offset_y = (former_size[1] - latter_size[1]) * spine_ratio
    if offset_y > 0:
        offset_y *= -1

    wedged_x = abs(offset_y) * math.tan(math.radians(wedge_angle))
    offset_x -= wedged_x

    return hou.Vector2(offset_x, offset_y), wedge_angle


def _calc_membrane_spec(
        max_yaw: float,
        min_flex: float,
        latter_segment_size: tuple[float, float],
        minimum_return: tuple[float, float],
) -> tuple[float, float]:
    max_yaw = abs(max_yaw)
    assert min_flex > 0
    assert max_yaw <= 90
    distance = latter_segment_size[0] * math.sin(math.radians(max_yaw))
    distance = max(distance, minimum_return[0])

    if min_flex >= 180:
        angle = minimum_return[1]
    else:
        angle = _solve_membrane_angle(min_flex, distance, latter_segment_size[1])
        angle = max(angle, minimum_return[1])

    return distance, angle

def _solve_membrane_angle(
        total: float,
        distance: float,
        height: float,
) -> float:
    k = distance / height

    # Special case: z = 90°
    if math.isclose(total, 90.0):
        disc = k * k + 4
        t1 = (-k + math.sqrt(disc)) / 2
        t2 = (-k - math.sqrt(disc)) / 2
    else:
        T = math.tan(math.radians(total))
        disc = 4 + (k * k + 4) * T * T
        t1 = (-(2 + k * T) + math.sqrt(disc)) / (2 * T)
        t2 = (-(2 + k * T) - math.sqrt(disc)) / (2 * T)

    x1 = math.degrees(math.atan(t1))
    x2 = math.degrees(math.atan(t2))
    return next(x for x in (x1, x1 + 180, x2, x2 + 180) if 0 < x < total)
