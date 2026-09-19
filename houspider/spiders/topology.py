import hou

from . import abdomen_pedicel, cepha_pedicel, sockets


def open_cepha_pedicel(node: hou.SopNode) -> None:
    cepha_pedicel.open_cepha_pedicel(node)


def open_abdomen_pedicel(node: hou.SopNode) -> None:
    abdomen_pedicel.open_abdomen_pedicel(node)


def remove_coxa_sockets(node: hou.SopNode) -> None:
    sockets.remove_coxa_sockets(node)
