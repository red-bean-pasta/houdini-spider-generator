import hou

from . import geometry, membrane, sections, support
from ..heads.attributes import headbasesupport, headchelicerae
from ..helper import rename_left_ids as rename_left_ids_geometry


def build_geometry(node: hou.SopNode) -> None:
    geometry.build_geometry(node)


def inset_flaps(node: hou.SopNode) -> None:
    membrane.inset_flaps(node)


def classify_after_inset(node: hou.SopNode) -> None:
    membrane.classify_after_inset(node)


def prepare_extrusion(node: hou.SopNode) -> None:
    membrane.prepare_extrusion(node)


def remove_left_membrane(node: hou.SopNode) -> None:
    membrane.remove_left_membrane(node)


def add_start_membrane(node: hou.SopNode) -> None:
    membrane.add_start_membrane(node)


def inset_start_membrane(node: hou.SopNode) -> None:
    membrane.inset_start_membrane(node)


def adjust_start_section_left(node: hou.SopNode) -> None:
    membrane.adjust_start_section_left(node)


def add_end_section(node: hou.SopNode) -> None:
    sections.add_end_section(node)


def add_middle_section(node: hou.SopNode) -> None:
    sections.add_middle_section(node)


def add_upper_middle_section(node: hou.SopNode) -> None:
    sections.add_upper_middle_section(node)


def add_lower_middle_section(node: hou.SopNode) -> None:
    sections.add_lower_middle_section(node)


def connect_sections(node: hou.SopNode) -> None:
    sections.connect_sections(node)


def remove_middle_face(node: hou.SopNode) -> None:
    support.remove_middle_face(node)


def middle_loop_cut(node: hou.SopNode) -> None:
    support.middle_loop_cut(node)


def merge_membrane_curves(node: hou.SopNode) -> None:
    support.merge_membrane_curves(node)


def adjust_start_membrane_curve(node: hou.SopNode) -> None:
    support.adjust_start_membrane_curve(node)


def adjust_right_membrane_width(node: hou.SopNode) -> None:
    support.adjust_right_membrane_width(node)


def adjust_head_chelicerae_depth(node: hou.SopNode) -> None:
    support.adjust_head_chelicerae_depth(node)


def inset_chelicerae_support_loop(node: hou.SopNode) -> None:
    support.inset_chelicerae_support_loop(node)


def add_start_membrane_support_loops(node: hou.SopNode) -> None:
    support.add_start_membrane_support_loops(node)


def add_start_section_support_loops(node: hou.SopNode) -> None:
    support.add_start_section_support_loops(node)


def rename_left_ids(node: hou.SopNode) -> None:
    rename_left_ids_geometry(node.geometry(), affix_index=-1)


def deduplicate_base_faces(node: hou.SopNode) -> None:
    geo: hou.Geometry = node.geometry()
    base_id_sets = []
    for sign in (1, -1):
        base_id_sets.append({
            headchelicerae(0),
            headchelicerae(sign * 1),
            headbasesupport(headchelicerae(sign * 1)),
            headbasesupport(headchelicerae(0)),
        })
        base_id_sets.append({
            headchelicerae(sign * 1),
            headchelicerae(sign * 2),
            headbasesupport(headchelicerae(sign * 2)),
            headbasesupport(headchelicerae(sign * 1)),
        })

    duplicate_prims = [
        prim for prim in geo.prims()
        if {pt.stringAttribValue("id") for pt in prim.points()} in base_id_sets
    ]
    geo.deletePrims(duplicate_prims, keep_points=False)
