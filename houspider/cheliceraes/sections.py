from dataclasses import dataclass
from typing import Callable

import hou

from houkit.attributer import add_prim_attrib
from houkit.geomath import interpolate_elliptical, rotation_to
from houkit.noder import get_parent
from houkit.parameterizer import get_parms
from houkit.topology import fill_face
from .attributes import (
    Region,
    cheliceraeend,
    cheliceraeintermediate,
    cheliceraemembrane,
    cheliceraemiddle,
    cheliceraestart,
    cheliceraestartmembranesupport,
)
from ..helper import add_id_point, bridge_loops, fill_face_with_attr, points_from_geo


def add_end_section(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)
    params = get_parms(parent, use_tuple=False)
    end_section_ratio = params.end_section_ratio

    start_section, end_pivot, end_rot_matrix, end_surface_normal = _get_end_section_frame(geo, parent)

    c3_positions = _construct_section_loop(
        end_pivot,
        hou.Vector2(start_section.height * end_section_ratio.y(), start_section.width * end_section_ratio.x()),
        start_section.along * end_rot_matrix,
        end_surface_normal,
    )

    for pos in c3_positions:
        assert pos.x() >= 0.0, f"End section loop point crossed symmetry plane (x={pos.x():.4f} < 0.0). Adjust parameters."

    c3_pts = [
        add_id_point(geo, pos, cheliceraeend(j))
        for j, pos in enumerate(c3_positions, start=1)
    ]

    add_prim_attrib(geo, "region", "")
    fill_face_with_attr(geo, c3_pts, "region", Region.FANG, True)


@dataclass
class Section:
    pivot: hou.Vector3
    points: tuple[hou.Point, hou.Point, hou.Point, hou.Point]
    along: hou.Vector3
    normal: hou.Vector3
    width: float
    height: float

    @property
    def offset_baseline(self) -> hou.Vector3:
        return hou.Vector3(self.width, self.height, self.height)


def _get_start_section_frame(geo: hou.Geometry) -> Section:
    c1_1, c1_2, c1_3, c1_4 = points_from_geo(
        geo,
        cheliceraestart(1),
        cheliceraestart(2),
        cheliceraestart(3),
        cheliceraestart(4),
    )

    pivot = (c1_1.position() + c1_2.position() + c1_3.position() + c1_4.position()) / 4.0
    along = (c1_1.position() - c1_2.position()).normalized()
    normal = (c1_2.position() - c1_1.position()).cross(c1_4.position() - c1_1.position()).normalized()
    w = (c1_4.position() - c1_1.position()).length()
    h = (c1_2.position() - c1_1.position()).length()
    return Section(
        pivot,
        (c1_1, c1_2, c1_3, c1_4),
        along,
        normal,
        w,
        h,
    )


def _get_end_section_frame(geo: hou.Geometry, parent: hou.OpNode) -> tuple[Section, hou.Vector3, hou.Matrix3, hou.Vector3]:
    params = get_parms(parent, use_tuple=False)
    end_section_offset = params.end_section_offset
    end_section_rotation = params.end_section_rotation

    start_section = _get_start_section_frame(geo)
    offset_baseline = start_section.offset_baseline

    end_pivot_offset = hou.Vector3(end_section_offset.x(), -end_section_offset.y(), -end_section_offset.z())
    end_pivot = start_section.pivot + hou.Vector3(
        offset_baseline.x() * end_pivot_offset.x(),
        offset_baseline.y() * end_pivot_offset.y(),
        offset_baseline.z() * end_pivot_offset.z(),
    )

    end_rot_matrix = hou.hmath.buildRotate(end_section_rotation.x(), 0.0, end_section_rotation.y())
    end_surface_normal = start_section.normal * end_rot_matrix
    return start_section, end_pivot, end_rot_matrix, end_surface_normal


def _construct_section_loop(
    pivot: hou.Vector3,
    size: hou.Vector2,
    along: hou.Vector3,
    normal: hou.Vector3,
) -> list[hou.Vector3]:
    normal = normal.normalized()
    along = along.normalized()
    along = (along - normal * along.dot(normal)).normalized()
    side = normal.cross(along).normalized()

    half_h, half_w = size.x() / 2.0, size.y() / 2.0
    corners = (
        (half_h, half_w),
        (-half_h, half_w),
        (-half_h, -half_w),
        (half_h, -half_w),
    )
    return [
        pivot + along * ah + side * sw
        for ah, sw in corners
    ]


def add_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.5, cheliceraemiddle)


def add_upper_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.25, lambda *i: cheliceraeintermediate(0.25, *i))


def add_lower_middle_section(node: hou.SopNode) -> None:
    _add_intermediate_section(node, 0.75, lambda *i: cheliceraeintermediate(0.75, *i))


def _add_intermediate_section(
    node: hou.SopNode,
    factor: float,
    id_factory: Callable[[int], str] | None,
) -> None:
    geo: hou.Geometry = node.geometry()
    parent = get_parent(node)

    params = get_parms(parent, use_tuple=False)
    end_section_ratio = params.end_section_ratio
    middle_section_offset = params.middle_section_offset
    middle_section_height_ratio = params.middle_section_height_ratio
    middle_section_ratio = params.middle_section_ratio

    start_section, end_pivot, _, end_surface_normal = _get_end_section_frame(geo, parent)
    offset_baseline = start_section.offset_baseline

    middle_pivot = _get_middle_section_pivot(
        start_section,
        end_pivot,
        offset_baseline,
        middle_section_offset,
        middle_section_height_ratio,
    )
    pivot, direction, normal, weights = _get_intermediate_section_frame(
        start_section.pivot,
        middle_pivot,
        end_pivot,
        start_section.along,
        end_surface_normal,
        start_section.normal,
        factor,
    )

    start_size = hou.Vector2(start_section.height, start_section.width)
    size = _get_intermediate_section_size(
        start_size,
        middle_section_ratio,
        end_section_ratio,
        weights,
    )

    positions = _construct_section_loop(
        pivot,
        size,
        direction,
        normal,
    )

    for pos in positions:
        assert pos.x() >= 0.0, f"Section loop point at factor {factor} crossed symmetry plane (x={pos.x():.4f} < 0.0). Adjust parameters or ratio."

    pts = _add_intermediate_section_points(geo, positions, id_factory)
    fill_face(pts, True)


def _get_middle_section_pivot(
    start_section: Section,
    end_pivot: hou.Vector3,
    offset_baseline: hou.Vector3,
    middle_section_offset: hou.Vector2,
    middle_section_height_ratio: float,
) -> hou.Vector3:
    return hou.Vector3(
        start_section.pivot.x() + offset_baseline.x() * middle_section_offset.x(),
        start_section.pivot.y() + (end_pivot.y() - start_section.pivot.y()) * middle_section_height_ratio,
        start_section.pivot.z() - offset_baseline.z() * middle_section_offset.y(),
    )


def _get_intermediate_section_frame(
    start_pivot: hou.Vector3,
    middle_pivot: hou.Vector3,
    end_pivot: hou.Vector3,
    start_along: hou.Vector3,
    end_surface_normal: hou.Vector3,
    start_normal: hou.Vector3,
    factor: float,
) -> tuple[hou.Vector3, hou.Vector3, hou.Vector3, tuple[float, float, float]]:
    evaluate = interpolate_elliptical(
        start_pivot,
        middle_pivot,
        end_pivot,
        start_along,
        -end_surface_normal,
    )

    along_axis = (end_pivot - start_pivot).normalized()
    chord_length = (end_pivot - start_pivot).length()
    middle_t = (middle_pivot - start_pivot).dot(along_axis) / chord_length

    f_upper = min(factor * 2.0, 1.0)
    f_lower = max(factor * 2.0 - 1.0, 0.0)
    w_start = 1.0 - f_upper
    w_mid = f_upper - f_lower
    w_end = f_lower
    t = middle_t * w_mid + w_end

    pivot, direction = evaluate(t)
    normal = rotation_to(start_along, direction).rotate(start_normal)
    return pivot, direction, normal, (w_start, w_mid, w_end)


def _get_intermediate_section_size(
    start_size: hou.Vector2,
    middle_section_ratio: hou.Vector2,
    end_section_ratio: hou.Vector2,
    weights: tuple[float, float, float],
) -> hou.Vector2:
    w_start, w_mid, w_end = weights
    middle_size = hou.Vector2(
        start_size.x() * middle_section_ratio.y(),
        start_size.y() * middle_section_ratio.x(),
    )
    end_size = hou.Vector2(
        start_size.x() * end_section_ratio.y(),
        start_size.y() * end_section_ratio.x(),
    )
    return start_size * w_start + middle_size * w_mid + end_size * w_end


def _add_intermediate_section_points(
    geo: hou.Geometry,
    positions: list[hou.Vector3],
    id_factory: Callable[[int], str] | None,
) -> list[hou.Point]:
    if id_factory:
        return [
            add_id_point(geo, pos, id_factory(j))
            for j, pos in enumerate(positions, start=1)
        ]

    pts = [geo.createPoint() for _ in positions]
    for pt, pos in zip(pts, positions):
        pt.setPosition(pos)
    return pts


def connect_sections(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()

    _remove_section_cap_faces(geo)
    _connect_membrane_to_start_support(geo)
    _bridge_chelicerae_section_loops(geo)


def _remove_section_cap_faces(geo: hou.Geometry) -> None:
    def is_cap_face(prim: hou.Prim) -> bool:
        if prim.stringAttribValue("region") == Region.FANG:
            return False
        pt_ids = [pt.stringAttribValue("id") for pt in prim.points()]
        if not all(pid.startswith((cheliceraestart(), cheliceraemiddle(), cheliceraeintermediate())) for pid in pt_ids):
            return False
        prefixes = {pid.rstrip("0123456789-") for pid in pt_ids}
        return len(prefixes) == 1

    middle_prims = [prim for prim in geo.prims() if is_cap_face(prim)]
    geo.deletePrims(middle_prims, keep_points=True)


def _connect_membrane_to_start_support(geo: hou.Geometry) -> None:
    # Connect socket membrane (4 corner points) to start membrane support (4 points)
    m1, m3, m4, m6 = points_from_geo(
        geo,
        cheliceraemembrane(1),
        cheliceraemembrane(3),
        cheliceraemembrane(4),
        cheliceraemembrane(6),
    )
    ss1, ss2, ss3, ss4 = points_from_geo(
        geo,
        cheliceraestartmembranesupport(1),
        cheliceraestartmembranesupport(2),
        cheliceraestartmembranesupport(3),
        cheliceraestartmembranesupport(4),
    )

    # Medial face: (m1, m6, ss2, ss1)
    fill_face([m1, m6, ss2, ss1], True)
    # Top face: (m6, m4, ss3, ss2)
    fill_face([m6, m4, ss3, ss2], True)
    # Lateral face: (m4, m3, ss4, ss3)
    fill_face([m4, m3, ss4, ss3], True)
    # Bottom face: (m3, m1, ss1, ss4)
    fill_face([m3, m1, ss1, ss4], True)


def _bridge_chelicerae_section_loops(geo: hou.Geometry) -> None:
    tube_loops = [
        points_from_geo(
            geo,
            cheliceraestart(1),
            cheliceraestart(2),
            cheliceraestart(3),
            cheliceraestart(4),
        ),
        points_from_geo(geo, *(cheliceraeintermediate(0.25, j) for j in range(1, 5))),
        points_from_geo(geo, *(cheliceraemiddle(j) for j in range(1, 5))),
        points_from_geo(geo, *(cheliceraeintermediate(0.75, j) for j in range(1, 5))),
        points_from_geo(geo, *(cheliceraeend(j) for j in range(1, 5))),
    ]

    for i in range(len(tube_loops) - 1):
        current_loop = tube_loops[i]
        next_loop = tube_loops[i + 1]
        bridge_loops(geo, current_loop, next_loop, reverse=True)
