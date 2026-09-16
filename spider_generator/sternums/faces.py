import hou

from houkit.topology import fill_face

def build_sternum_faces(node: hou.SopNode) -> None:
    geo = node.geometry()

    sort_by_z = lambda p: p.position().z()
    center = sorted((p for p in geo.points() if p.position().x() == 0), key=sort_by_z)
    right = sorted((p for p in geo.points() if p.position().x() > 0), key=sort_by_z)
    left = sorted((p for p in geo.points() if p.position().x() < 0), key=sort_by_z)

    build_base_faces(center, right, left)

def build_base_faces(
    center: list[hou.Point],
    right: list[hou.Point],
    left: list[hou.Point],
) -> None:
    for index in range(len(center) - 2):
        fill_face([center[index], right[index], right[index + 1], center[index + 1]], True)
        fill_face([center[index], center[index + 1], left[index + 1], left[index]], True)
    fill_face([center[-2], right[-1], center[-1], left[-1]], True)


