import hou

from houkit.attributer import add_prim_attrib
from houkit.models import Moject
from .segments import connection, tube
from .attributes import LegParam


def build_leg(
    geo: hou.Geometry,
    param: LegParam,
) -> Moject[tuple[list[hou.Point], list[hou.Point], list[hou.Point]]]:
    add_prim_attrib(geo, "region", "")

    seg_pts, warnings = tube.build_segment_tubes(geo, param)
    thickness_pts = connection.inset_segment_thickness(geo, seg_pts, param.support_loop_ratio)
    all_seg_pts = connection.add_segment_loop_cuts(geo, seg_pts, param.support_loop_ratio)
    mem_pts = connection.fill_membranes(geo, thickness_pts)
    all_mem_pts = connection.add_membrane_loop_cuts(geo, seg_pts, thickness_pts, mem_pts, param.support_loop_ratio)
    connection.close_tarsus(geo, all_seg_pts, param.tarsus_wedge_angle)
    return Moject((all_seg_pts, thickness_pts, all_mem_pts), warnings)
