import hou

from . import faces, membrane, outline, spine


def left_half(node: hou.SopNode) -> None:
    outline.left_half(node)


def add_midpoints(node: hou.SopNode) -> None:
    outline.add_midpoints(node)


def add_point_ids(node: hou.SopNode) -> None:
    outline.add_point_ids(node)


def add_center_spine(node: hou.SopNode) -> None:
    outline.add_center_spine(node)


def build_sternum_faces(node: hou.SopNode) -> None:
    faces.build_sternum_faces(node)


def inset_spine_loop(node: hou.SopNode) -> None:
    spine.inset_spine_loop(node)


def elevate_spine_loop(node: hou.SopNode) -> None:
    spine.elevate_spine_loop(node)


def descend_sternum_spine(node: hou.SopNode) -> None:
    spine.descend_sternum_spine(node)


def add_prim_regions(node: hou.SopNode) -> None:
    membrane.add_prim_regions(node)


def outset_sternum_loop(node: hou.SopNode) -> None:
    membrane.outset_sternum_loop(node)
