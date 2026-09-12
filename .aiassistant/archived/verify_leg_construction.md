## Task 1
verify leg construction logic

#### Background
each leg segment can yaw and flex. unlike vector angle, the flex angle is treated more "biologically". therefore, when the segment is fully "folded", e.g., (0,0,1) and (0,0,-1), it's angle is 0 instead of 180 degrees.
spider leg segment is made possible to yaw and flex by membrane. many methods in `../../spider_generator/leg.py` address how to calculate the mebrane.
yaw is straight forward: when the segment is fully yawed, it's corner should not go through the former segment. therefore, the calculation is `half_width_latter * sin(yaw) <= membrane_width`. This is simply because the yaw angle (the angle between latter_segment_forward and former_segment_forward) is the same as the angle between latter_segment_left and former_segment_left, which can then derive the mambrane width, or `distance` in the code.
as for flex, it's much more complicated. The wedge is always from top to bottom (the bottom is wedged off). In the code, the wedge angle refers to the "hallow" angle, so it's  the angle between segment_down and wedged_line, not the "remaining angle". 
Therefore, the maximum flex doesn't determine the wedge angle needed, but the minimum flex. and if the min flex is above 180, there's no wedge needed. And the min_flex is at least `2 * (90 - wedge_angle)`, if membrane width is not considered. `2 * (90 - wedge_angle)` happens when two wedge surfaces are just onto each other.
we can technically stop at this simplified version, but in reality, the min flex is much much smaller, like 30 degrees. therefore, a simple wedge would be impossible (a very large wedge angle is derived).
in fact, membrane itself allows flex, because of the gap it introduces. the gap allows a fairly small rotation, let's say `r`, and the min_flex is therefore `2 * (90 - wedge_angle) - r`, since the latter segment is rotated further by `r`. 
it's also easy to find that the `r` is at its maximum, when the distance between two wedge surfaces is at its maximum, which is when the membrane itself is perpendicular to the wedge surfaces. 
Thus the following python methods:
```python
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
        distance = _solve_membrane_thickness_deg(
            max_wedge_deg * 2 - min_flex_deg,
            min_height,
            max_wedge_deg,
        )
        distance = min(distance, latter_width * max_distance_ratio)

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
```

Help me debug:
1. if my logic is sound
2. if the code is sound
