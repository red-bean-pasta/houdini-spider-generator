import hou

from houkit.topology import fill_face
from .attributes import Region, headsideback, headsidefront, headsidemiddle, headsupport
from ..bases import attributes as base_attributes
from ..helper import add_id_point, points_by_id, set_prim_attr_where_blank


def fill_side_faces(node: hou.SopNode) -> None:
    geo = node.geometry()
    points = points_by_id(geo)
    right_side = sorted_right_side_points(geo)
    assert len(right_side) >= 3 and len(right_side) % 2 == 1, "Expected an odd, symmetric right-side sternum loop"

    center_index = (len(right_side) - 1) // 2
    center = right_side[center_index]
    center_position = center.position()
    front_points = list(reversed(right_side[center_index + 1:]))
    back_points = right_side[:center_index]
    assert len(front_points) == len(back_points), "Expected matching front and back sternum loops"

    front_ratios, back_ratios = get_head_side_layer_ratios(
        center_position,
        front_points,
        back_points,
    )
    head_side_points = get_head_side_reference_points(points)
    side_points = add_head_side_layer_points(
        geo,
        center_position,
        head_side_points,
        front_ratios,
        back_ratios,
    )
    current_points = fill_head_side_layer_faces(
        geo,
        front_points,
        back_points,
        head_side_points,
        side_points,
    )
    fill_head_side_end_faces(geo, front_points, back_points, center, current_points)


def get_head_side_layer_ratios(
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


def get_head_side_reference_points(
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


def add_head_side_layer_points(
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
                add_named_point(geo, front_position, headsidefront(layer)),
                add_named_point(geo, middle_position, headsidemiddle(layer)),
                add_named_point(geo, back_position, headsideback(layer)),
            )
        )
    return side_points


def fill_head_side_layer_faces(
    geo: hou.Geometry,
    front_points: list[hou.Point],
    back_points: list[hou.Point],
    head_side_points: tuple[hou.Point, hou.Point, hou.Point],
    side_points: list[tuple[hou.Point, hou.Point, hou.Point]],
) -> tuple[hou.Point, hou.Point, hou.Point]:
    current_front, current_middle, current_back = head_side_points
    for layer, (next_front, next_middle, next_back) in enumerate(side_points):
        fill_face(
            [current_front, front_points[layer], front_points[layer + 1], next_front],
        )
        fill_face(
            [current_front, next_front, next_middle, current_middle],
        )
        fill_face(
            [current_middle, next_middle, next_back, current_back],
        )
        fill_face(
            [current_back, next_back, back_points[layer + 1], back_points[layer]],
        )
        current_front = next_front
        current_middle = next_middle
        current_back = next_back
    return current_front, current_middle, current_back


def fill_head_side_end_faces(
    geo: hou.Geometry,
    front_points: list[hou.Point],
    back_points: list[hou.Point],
    center: hou.Point,
    current_points: tuple[hou.Point, hou.Point, hou.Point],
) -> None:
    current_front, current_middle, current_back = current_points
    fill_face([current_front, front_points[-1], center, current_middle])
    fill_face([current_middle, center, back_points[-1], current_back])

def sorted_right_side_points(geo: hou.Geometry) -> list[hou.Point]:
    candidates = [
        point
        for point in geo.points()
        if point.stringAttribValue("id").startswith(base_attributes.ID.BASESTERNUM)
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

def add_named_point(
    geo: hou.Geometry,
    position: hou.Vector3,
    point_id: str,
) -> hou.Point:
    return add_id_point(geo, position, point_id)


def add_side_regions(node: hou.SopNode) -> None:
    geo = node.geometry()
    set_prim_attr_where_blank(geo, "region", Region.HEADSIDE)

