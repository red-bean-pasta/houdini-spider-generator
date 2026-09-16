from hou import SopNode

from . import coxa, geometry as leg_geometry
from .pedipalp import faces, geometry as pedipalp_geometry


def extract_right_coxa(node: SopNode) -> None:
    coxa.extract_right_coxa(node)


def extrude_legs(node: SopNode) -> None:
    leg_geometry.extrude_legs(node)


def remove_tmp_attributes(node: SopNode) -> None:
    coxa.remove_tmp_attributes(node)


def remove_noise_points(node: SopNode) -> None:
    pedipalp_geometry.remove_noise_points(node)


def build_basic(node: SopNode) -> None:
    pedipalp_geometry.build_basic(node)


def trim_bottom_side_length(node: SopNode) -> None:
    pedipalp_geometry.trim_bottom_side_length(node)


def position_basic(node: SopNode) -> None:
    pedipalp_geometry.position_basic(node)


def delete_start_coxa_supports(node: SopNode) -> None:
    pedipalp_geometry.delete_start_coxa_supports(node)


def prepare_coxa_base_trapezoid(node: SopNode) -> None:
    pedipalp_geometry.prepare_coxa_base_trapezoid(node)


def fill_bottom_right_face(node: SopNode) -> None:
    faces.fill_bottom_right_face(node)


def fill_back_face(node: SopNode) -> None:
    faces.fill_back_face(node)


def fill_top_face(node: SopNode) -> None:
    faces.fill_top_face(node)


def add_front_upper_face(node: SopNode) -> None:
    faces.add_front_upper_face(node)


def add_front_loop_faces(node: SopNode) -> None:
    faces.add_front_loop_faces(node)


def add_maxilla_quads(node: SopNode) -> None:
    faces.add_maxilla_quads(node)


def fill_maxilla_faces(node: SopNode) -> None:
    faces.fill_maxilla_faces(node)


def remove_pedipalp_tmp_attributes(node: SopNode) -> None:
    pedipalp_geometry.remove_tmp_attributes(node)
