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
    add_heading,
    remove_attrs,
)
from utilities.nodes import (
    add_fuse,
    add_mirror,
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
    cleaned = sopify(legs, extruded, _remove_tmp_attributes)
    fused = add_fuse(legs, "fuse_sockets", cleaned)
    mirrored = add_mirror(legs, "mirror_left_legs", fused, (1, 0, 0), True, False)
    add_output(legs, "OUT_LEGS", mirrored)

    legs.layoutChildren()
    return legs


def _add_parameters(legs: hou.OpNode) -> None:
    add_heading(
        legs,
        "Basic",
    )
    add_float_param(
        legs,
        "segment_height_ratio",
        1,
        1.15,
        (0.0, None),
    )
    add_float_param(
        legs,
        "segment_lateral_ratio",
        1,
        0.5,
        (0.0, None),
        help="The top to the thickest part : the thickest part to the bottom",
    )
    add_float_param(
        legs,
        "segment_section_shrink_ratio",
        1,
        0.85,
        (0.0, None),
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
        "minimum_membrane_spec",
        2,
        (1.0, 5.0),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Membrane distance in ratio to the latter segment's width; Wedge angle in degrees",
    )
    add_heading(
        legs,
        "Front Leg",
    )
    add_float_param(
        legs,
        "front_coxa_size_ratio",
        2,
        (0.75, 1.1),
        (0.0, None),
        help="Width and length relative to the base sockets' size.",
    )
    add_float_param(
        legs,
        "front_segment_length_ratios",
        6,
        (0.5, 3, 3, 2.5, 2.5, 1),
        (0.0, None),
        hou.parmNamingScheme.Base1,
        help="Ratio relative to coxa length.",
    )
    add_heading(
        legs,
        "Other Legs",
    )
    add_float_param(
        legs,
        "leg_width_ratios",
        3,
        (0.9, 0.9, 0.95),
        (0.0, None),
        hou.parmNamingScheme.Base1,
    )
    add_float_param(
        legs,
        "leg_length_ratios",
        3,
        (0.85, 0.85, 1.1),
        (0.0, None),
        hou.parmNamingScheme.Base1,
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

    socket_points = _get_right_coxa_socket_points(node)
    geo.deletePrims(geo.prims(), keep_points=True)

    flat_pt_nums = [p.number() for group in socket_points for p in group]
    geo.addArrayAttrib(hou.attribType.Global, "tmp_coxa_corners", hou.attribData.Int)
    geo.setGlobalAttribValue("tmp_coxa_corners", flat_pt_nums)

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


def _remove_tmp_attributes(node: hou.SopNode) -> None:
    remove_attrs(node.geometry(), global_attribs="tmp_coxa_corners")


def _extrude_legs(
        node: hou.SopNode,
) -> None:
    geo = node.geometry()
    corners = geo.attribValue("tmp_coxa_corners")

    for i in range(4):
        pt_nums = corners[i * 4:(i + 1) * 4]
        pts = [geo.iterPoints()[p] for p in pt_nums]
        pos_top_sz = pts[0].position()
        pos_top_bz = pts[1].position()
        pos_btm_sz = pts[2].position()
        pos_btm_bz = pts[3].position()

        top_mid = (pos_top_sz + pos_top_bz) / 2.0
        btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
        origin = top_mid
        direction = hou.Vector3(top_mid.x() - btm_mid.x(), 0.0, top_mid.z() - btm_mid.z()).normalized()

        leg_points = _build_leg(node, i)

        q = rotation_to(hou.Vector3(0.0, 0.0, -1.0), direction)
        for pt in leg_points:
            pt.setPosition(q.rotate(pt.position()) + origin)

        leg_points[0].setPosition(pos_top_bz)
        leg_points[1].setPosition(pos_top_sz)
        leg_points[2].setPosition(pos_btm_bz)
        leg_points[3].setPosition(pos_btm_sz)

def _build_leg(
        node: hou.SopNode,
        index: int,
) -> list[hou.Point]:
    assert 0 <= index <= 3
    geo = node.geometry()
    parent = get_parent(node)

    segment_height_ratio = get_float_parm(parent, "segment_height_ratio")
    spine_ratio = get_float_parm(parent, "segment_lateral_ratio")
    shrink_ratio = get_float_parm(parent, "segment_section_shrink_ratio")

    min_segment_flexes = get_parm(parent, "min_segment_flexes", tuple[float, ...])
    max_segment_yaws = get_parm(parent, "max_segment_yaws", tuple[float, ...])
    minimum_membrane = get_parm(parent, "minimum_membrane_spec", tuple[float, float])
    segment_specs = tuple(zip(max_segment_yaws[1:], min_segment_flexes[1:]))

    front_coxa_size_ratio = get_vector2_parm(parent, "front_coxa_size_ratio")
    length_ratios = get_parm(parent, "front_segment_length_ratios", tuple[float, ...])
    leg_width_ratios = get_parm(parent, "leg_width_ratios", tuple[float, float, float])
    leg_length_ratios = get_parm(parent, "leg_length_ratios", tuple[float, float, float])

    front_socket_width, _ = _get_front_coxa_socket_size(node)
    front_coxa_width = front_socket_width * front_coxa_size_ratio.x()
    front_coxa_length = front_socket_width * front_coxa_size_ratio.y()

    if index == 0:
        coxa_width = front_coxa_width
        coxa_length = front_coxa_length
    else:
        coxa_width = front_coxa_width * leg_width_ratios[index - 1]
        coxa_length = front_coxa_length * leg_length_ratios[index - 1]

    coxa_height = coxa_width * segment_height_ratio
    coxa_size = (coxa_width, coxa_height, coxa_length)

    segments = _get_leg_points(
        coxa_size,
        shrink_ratio,
        list(length_ratios),
        spine_ratio,
        segment_specs,
        minimum_membrane,
    )

    all_points: list[hou.Point] = []
    for seg in segments:
        seg_pts = [geo.createPoint() for _ in range(8)]
        for pt, pos in zip(seg_pts, seg):
            pt.setPosition(pos)
        all_points.extend(seg_pts)

        start_loop = [seg_pts[0], seg_pts[1], seg_pts[3], seg_pts[2]]
        end_loop = [seg_pts[4], seg_pts[5], seg_pts[7], seg_pts[6]]
        for j in range(4):
            next_j = (j + 1) % 4
            fill_face(geo, [
                start_loop[j],
                start_loop[next_j],
                end_loop[next_j],
                end_loop[j],
            ])

    return all_points

def _get_front_coxa_socket_size(node: hou.SopNode) -> tuple[float, float]:
    geo = node.geometry()
    corners = geo.attribValue("tmp_coxa_corners")
    pts = [geo.iterPoints()[p] for p in corners[:4]]

    pos_top_sz = pts[0].position()
    pos_top_bz = pts[1].position()
    pos_btm_sz = pts[2].position()
    pos_btm_bz = pts[3].position()

    width = (pos_top_bz - pos_top_sz).length()
    top_mid = (pos_top_sz + pos_top_bz) / 2.0
    btm_mid = (pos_btm_sz + pos_btm_bz) / 2.0
    height = top_mid.y() - btm_mid.y()

    return width, height

def _get_leg_points(
        coxa_size: tuple[float, float, float],
        section_shrink_ratio: float,
        length_ratios: list[float],
        spine_ratio: float,
        segment_specs: tuple[tuple[float, float], ...],
        minimum_membrane: tuple[float, float],
) -> list[list[hou.Vector3]]:
    assert len(segment_specs) == len(length_ratios) == 6  # TROCHANTER, FEMUR, PATELLA, TIBIA, METATARSUS, TARSUS

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
    for i, (max_yaw, min_flex) in enumerate(segment_specs):
        length_ratio_to_former = (
            length_ratios[i] / length_ratios[i - 1]
            if i > 0 else
            length_ratios[0] / 1.0
        )
        former_wedged, latter = _append_segment(
            segments[-1],
            section_shrink_ratio,
            length_ratio_to_former,
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
        section_shrink_ratio: float,
        length_ratio: float,
        spine_ratio: float,
        max_yaw: float,
        min_flex: float,
        minimum_membrane: tuple[float, float],
) -> tuple[
    list[hou.Vector3],
    list[hou.Vector3]
]:
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

    latter_width = former_width * section_shrink_ratio
    latter_height = former_height * section_shrink_ratio
    latter_size = (latter_width, latter_height)
    latter_length = former_length * length_ratio

    offset, wedge_angle = _calc_segment_offset_and_wedge(
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
    new_end_btm1_z = min(end_btm1.z() + delta_z_former, start_btm1.z())
    new_end_btmn1_z = min(end_btmn1.z() + delta_z_former, start_btmn1.z())

    former_positions_list = list(former_positions)
    former_positions_list[6] = hou.Vector3(end_btm1.x(), end_btm1.y(), new_end_btm1_z)
    former_positions_list[7] = hou.Vector3(end_btmn1.x(), end_btmn1.y(), new_end_btmn1_z)

    return former_positions_list, latter_segment

def _calc_segment_offset_and_wedge(
        max_yaw: float,
        min_flex: float,
        spine_ratio: float,
        segment_size: tuple[tuple[float, float], tuple[float, float]],
        minimum_membrane: tuple[float, float],
) -> tuple[hou.Vector2, float]:
    (former_width, former_height), (latter_width, latter_height) = segment_size

    offset_x, wedge_angle = _calc_membrane_spec(max_yaw, min_flex, segment_size, minimum_membrane)

    offset_y = (former_height - latter_height) * spine_ratio
    if offset_y > 0:
        offset_y *= -1

    wedged_x = abs(offset_y) * math.tan(math.radians(wedge_angle))
    offset_x -= wedged_x

    return hou.Vector2(offset_x, offset_y), wedge_angle


def _calc_membrane_spec(
        max_yaw_deg: float,
        min_flex_deg: float,
        segment_sections: tuple[tuple[float, float], tuple[float, float]],
        min_return: tuple[float, float],
        max_wedge_deg: float = 45,
        max_distance_ratio: float = 1.0,
) -> tuple[float, float]:
    """

    :param max_yaw_deg:
    :param min_flex_deg:
    :param segment_sections:
    :param min_return:
    :param max_wedge_deg:
    :param max_distance_ratio:
    :return:
    """
    max_yaw_deg = abs(max_yaw_deg)
    assert min_flex_deg > 0
    assert max_yaw_deg <= 90

    min_distance, min_angle = min_return
    assert min_distance > 0 and 0 < min_angle < 45

    (former_width, former_height), (latter_width, latter_height) = segment_sections
    distance = latter_width / 2 * math.sin(math.radians(max_yaw_deg))
    distance = max(distance, min_distance)

    if min_flex_deg >= 180:
        angle = min_angle
        return distance, angle

    min_height = min(former_height, latter_height)
    angle = _solve_membrane_wedge_deg(
        min_flex_deg,
        distance,
        min_height
    )
    angle = max(angle, min_return[1])
    if angle > max_wedge_deg:
        angle = max_wedge_deg
        distance = _solve_membrane_thickness_deg(
            180 - 2 * max_wedge_deg - min_flex_deg,
            min_height,
            max_wedge_deg,
        )
        distance = min(distance, latter_width * max_distance_ratio)
        distance = max(distance, min_distance)

    return distance, angle


def _solve_membrane_wedge_deg(
        min_flex: float,
        membrane_thickness: float,
        min_height: float,
        tolerance: float = 1e-5,
        iterations: int = 50,
) -> float:
    wedge_rad = _solve_membrane_wedge_rad(
        math.radians(min_flex),
        membrane_thickness,
        min_height,
        tolerance,
        iterations,
    )
    return math.degrees(wedge_rad)

def _solve_membrane_wedge_rad(
        min_flex: float,
        membrane_thickness: float,
        min_height: float,
        tolerance: float = 1e-5,
        iterations: int = 50,
) -> float:
    return math.pi / 2 - _solve_membrane_wedge_remain_rad(
        min_flex,
        membrane_thickness,
        min_height,
        tolerance,
        iterations
    )

def _solve_membrane_wedge_remain_rad(
        min_flex: float,
        membrane_thickness: float,
        min_height: float,
        tolerance: float = 1e-5,
        iterations: int = 50,
) -> float:
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
    for _ in range(iterations):
        w = 2.0 * u - min_flex
        cos_w = math.cos(w)
        assert abs(cos_w) >= tolerance, "Solver reached tan(w) singularity"

        f = math.tan(w) - k * math.sin(u)  # f(u) = tan(2u-a) - k*sin(u)
        if abs(f) < tolerance:
            return u
        # derivative: d/du tan(2u-a) = 2 / cos²(2u-a)
        df = 2.0 / (cos_w * cos_w) - k * math.cos(u)
        assert abs(df) >= tolerance, "Derivative too small"
        u -= f / df

    return u

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