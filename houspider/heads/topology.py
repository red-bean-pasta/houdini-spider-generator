import hou

from . import base, front, membrane, side


def extract_base_rim(node: hou.SopNode) -> None:
    base.extract_base_rim(node)


def extract_work_base(node: hou.SopNode) -> None:
    base.extract_work_base(node)


def add_corners_half(node: hou.SopNode) -> None:
    base.add_corners_half(node)


def add_head_dent(node: hou.SopNode) -> None:
    front.add_head_dent(node)


def curve_lip(node: hou.SopNode) -> None:
    front.curve_lip(node)


def fill_back_loop_faces(node: hou.SopNode) -> None:
    front.fill_back_loop_faces(node)


def fill_support_loop_faces(node: hou.SopNode) -> None:
    front.fill_support_loop_faces(node)


def fill_side_faces(node: hou.SopNode) -> None:
    side.fill_side_faces(node)


def add_side_regions(node: hou.SopNode) -> None:
    side.add_side_regions(node)


def inset_base_support_loop(node: hou.SopNode) -> None:
    membrane.inset_base_support_loop(node)


def extrude_lip(node: hou.SopNode) -> None:
    membrane.extrude_lip(node)


def cleanup(node: hou.SopNode) -> None:
    membrane.cleanup(node)
