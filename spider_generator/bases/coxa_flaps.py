import hou

from houkit.noder import get_parent
from houkit.parameterizer import get_float_parm
from houkit.topology import fill_face
from ..sternums import attributes as sternum_attributes
from ..helper import add_id_point
from .attributes import ID


def build_coxa_flaps(node: hou.SopNode) -> None:
    geo = node.geometry()
    parent = get_parent(node)

    flap_ratio = get_float_parm(parent, "coxa_flap_extension_ratio")

    flap_edges = [
        tuple(edge.points())
        for edge in geo.globEdges("*")
        if not any(
            point.stringAttribValue("id").startswith(sternum_attributes.ID.STERNUMSPINE)
            for point in edge.points()
        )
    ]
    assert flap_edges, "Expected sternum rim edges"
    flap_edges.sort(
        key=lambda edge: (
            (edge[0].position()[2] + edge[1].position()[2]) / 2.0,
            -(edge[0].position()[0] + edge[1].position()[0]) / 2.0,
        )
    )
    geo.deletePrims(list(geo.prims()), keep_points=True)
    for start, end in flap_edges:
        _extrude_edge_outward(geo, start, end, flap_ratio)


def _extrude_edge_outward(
    geo: hou.Geometry,
    start: hou.Point,
    end: hou.Point,
    flap_ratio: float,
) -> None:
    def _get_extruded_id(source: hou.Point) -> str:
        source_id = source.stringAttribValue("id")
        source_id = source_id.replace(sternum_attributes.ID.STERNUMRIM, ID.BASESTERNUM)
        source_id = source_id.replace(sternum_attributes.ID.STERNUMMIDDLE, ID.BASESTERNUMMIDDLE)
        return source_id

    start_position = start.position()
    end_position = end.position()
    direction = end_position - start_position
    edge_length = start_position.distanceTo(end_position)
    assert edge_length > 1e-6, f"Expected nonzero edge from {start.number()} to {end.number()}"

    outward = hou.Vector3(
        -direction[2],
        0.0,
        direction[0],
    ) / edge_length
    offset = outward * edge_length * flap_ratio * 2.0

    outer_start = add_id_point(geo, start_position + offset, _get_extruded_id(start))
    outer_end = add_id_point(geo, end_position + offset, _get_extruded_id(end))
    fill_face([start, end, outer_end, outer_start], True)
