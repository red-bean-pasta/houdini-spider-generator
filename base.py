import hou

from helper import add_fuse, add_merge, add_output, propagate_parameters
from sternum import build as build_sternum
from sternum import IDS as STERNUM_IDS


_BASE_STERNUM = "basesternum"
_BASE_STERNUM_MIDDLE = "basesternummiddle"

def _build_ids() -> tuple[str, ...]:
    bs = _BASE_STERNUM
    bsm = _BASE_STERNUM_MIDDLE
    ids = [bs + "0"]
    for index in range(1, 6):
        ids.extend((f"{bs}{index}_1", f"{bs}{index}_2"))
        if index < 5:
            ids.append(f"{bsm}{index}")
    for index in range(-4, 0):
        ids.extend((f"{bsm}{index}", f"{bs}{index}_2", f"{bs}{index}_1"))
    return tuple(ids)


def _build_edge_ids() -> tuple[tuple[str, str], ...]:
    bs = _BASE_STERNUM
    bsm = _BASE_STERNUM_MIDDLE
    edges = [(bs + "0", bs + "1_1")]
    for index in range(1, 5):
        edges.extend(
            (
                (f"{bs}{index}_2", f"{bsm}{index}"),
                (f"{bsm}{index}", f"{bs}{index + 1}_1"),
            )
        )
    edges.append((bs + "5_2", bsm + "-4"))
    for index in range(-4, -1):
        edges.extend(
            (
                (f"{bsm}{index}", f"{bs}{index}_2"),
                (f"{bs}{index}_1", f"{bsm}{index + 1}"),
            )
        )
    edges.extend(((bsm + "-1", bs + "-1_2"), (bs + "-1_1", bs + "0")))
    return tuple(edges)


IDS = _build_ids()
EDGE_IDS = _build_edge_ids()
_RING_POINT_IDS_VEX = ", ".join(f'"{p}"' for p in STERNUM_IDS)
_OUTER_EDGE_START_IDS_VEX = ", ".join(f'"{p}"' for p, _ in EDGE_IDS)
_OUTER_EDGE_END_IDS_VEX = ", ".join(f'"{p}"' for _, p in EDGE_IDS)


def build(cephalothroax: hou.SopNode) -> hou.SopNode:
    base = cephalothroax.createNode("subnet", "base")
    _add_parameters(base)

    sternum = build_sternum(base)
    propagate_parameters(base, sternum, prefix="sternum_")

    rim = _extract_sternum_rim(base, sternum)
    flaps = _build_coxa_flaps(base, rim)
    fused = add_fuse(base, "fuse_coxa_flaps", flaps)
    connected = _connect_side_flaps(base, fused)
    fused_connected = add_fuse(base, "fuse_connected_side_flaps", connected)
    cleaned_connected = _cleanup_connected_side_flap_ids(base, fused_connected)
    rotated = _rotate_coxa_flaps(base, cleaned_connected)
    adjusted = _adjust_frontest_line(base, rotated)

    maxilla = _fill_maxilla(base, adjusted)

    pedicel = _fill_pedicel_membrane(base, maxilla)
    fused_pedicel = add_fuse(base, "fuse_pedicel_membrane", pedicel)
    membrane = _inset_membrane(base, fused_pedicel)

    merge = add_merge(base, "merge_sternum_and_coxa", membrane, sternum)
    fuse = add_fuse(base, "fuse_sternum_and_coxa", merge)
    output = add_output(base, "OUT_BASE", fuse)

    base.layoutChildren()
    return base


def _add_parameters(base: hou.SopNode) -> hou.SopNode:
    templates = base.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "coxa_width_ratio",
            "Coxa Width Ratio",
            2,
            default_value=(1.0, 1.2),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "coxa_depth_ratio",
            "Coxa Depth Ratio",
            1,
            default_value=(0.35,),
            min=0.0,
            min_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "membrane_ratio",
            "Membrane Ratio",
            1,
            default_value=(0.035,),
            min=0.0,
            min_is_strict=True,
        )
    )
    base.setParmTemplateGroup(templates)
    return base


def _extract_sternum_rim(
    parent: hou.SopNode,
    sternum: hou.SopNode,
) -> hou.SopNode:
    rim = parent.createNode("attribwrangle", "extract_sternum_rim")
    rim.setInput(0, sternum)
    rim.parm("class").set(0)
    rim.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        string ring_ids[] = array(__RING_POINT_IDS__);
        for (int primitive = nprimitives(0) - 1; primitive >= 0; --primitive)
            removeprim(0, primitive, 0);

        for (int point_number = npoints(0) - 1; point_number >= 0; --point_number) {
            string id = point(0, "id", point_number);
            if (find(ring_ids, id) < 0) {
                removepoint(0, point_number);
            }
        }
    '''.replace("__RING_POINT_IDS__", _RING_POINT_IDS_VEX))
    return rim


def _build_coxa_flaps(
    parent: hou.SopNode,
    sternum: hou.SopNode,
) -> hou.SopNode:
    """Create one separate, flat flap per sternum boundary edge in VEX."""
    flaps = parent.createNode("attribwrangle", "build_coxa_flaps")
    flaps.setInput(0, sternum)
    flaps.parm("class").set(0)
    flaps.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        string ring_ids[] = array(__RING_POINT_IDS__);
        string outer_start_ids[] = array(__OUTER_EDGE_START_IDS__);
        string outer_end_ids[] = array(__OUTER_EDGE_END_IDS__);
        int ring[] = {};
        foreach (string id; ring_ids) {
            int point_number = findbyid(id);
            if (point_number < 0)
                error("Expected sternum boundary point %s", id);
            append(ring, point_number);
        }
        int ring_size = len(ring);
        if (len(ring) < 3)
            error("Expected a closed sternum loop, found %d points", len(ring));

        float flap_ratio = ch("../coxa_width_ratioy") / max(ch("../coxa_width_ratiox"), 1e-6);
        for (int edge = 0; edge < ring_size; ++edge) {
            int a = ring[edge];
            int b = ring[(edge + 1) % ring_size];
            vector pa = point(0, "P", a);
            vector pb = point(0, "P", b);
            vector direction = pb - pa;
            float edge_length = length(set(direction.x, 0, direction.z));
            vector outward = normalize(set(direction.z, 0, -direction.x));
            vector offset = outward * edge_length * flap_ratio * 2;

            int oa = addpoint(0, pa + offset);
            int ob = addpoint(0, pb + offset);
            setid(array(oa, ob), array(outer_start_ids[edge], outer_end_ids[edge]));
            fillfacebypoints(array(a, b, ob, oa));
        }
    '''.replace("__RING_POINT_IDS__", _RING_POINT_IDS_VEX)
        .replace("__OUTER_EDGE_START_IDS__", _OUTER_EDGE_START_IDS_VEX)
        .replace("__OUTER_EDGE_END_IDS__", _OUTER_EDGE_END_IDS_VEX))
    return flaps


def _connect_side_flaps(
    parent: hou.SopNode,
    flaps: hou.SopNode,
) -> hou.SopNode:
    connected = parent.createNode("attribwrangle", "connect_side_flaps")
    connected.setInput(0, flaps)
    connected.parm("class").set(0)
    connected.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        for (int side = -1; side <= 1; side += 2) {
            for (int index = 2; index <= 4; ++index) {
                string prefix = sprintf("basesternum%d", side * index);
                int first = findbyid(prefix + "_1");
                int second = findbyid(prefix + "_2");
    
                if (first < 0 || second < 0)
                    error("Expected side-flap points %s_1 and %s_2", prefix, prefix);
    
                vector first_position = point(0, "P", first);
                vector second_position = point(0, "P", second);
                vector midpoint = (first_position + second_position) / 2.0;
    
                setpointattrib(0, "P", first, midpoint, "set");
                setpointattrib(0, "P", second, midpoint, "set");
            }
        }
    ''')
    return connected


def _cleanup_connected_side_flap_ids(
    parent: hou.SopNode,
    fused: hou.SopNode,
) -> hou.SopNode:
    cleaned = parent.createNode("attribwrangle", "cleanup_connected_side_flap_ids")
    cleaned.setInput(0, fused)
    cleaned.parm("class").set(0)
    cleaned.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int merged_sternums[] = array(2, 3, 4, -2, -3, -4);
        foreach (int sternum; merged_sternums) {
            string merged_id = sprintf(sternum < 0 ? "basesternum%d_2" : "basesternum%d_1", sternum);
            int point_number = findbyid(merged_id);
            if (point_number < 0)
                error("Expected fused side-flap point %s", merged_id);
            setid(array(point_number), array(sprintf("basesternum%d", sternum)));
        }
    ''')
    return cleaned


def _adjust_frontest_line(
    parent: hou.SopNode,
    coxa: hou.SopNode,
) -> hou.SopNode:
    adjusted = parent.createNode("attribwrangle", "adjust_frontest_line")
    adjusted.setInput(0, coxa)
    adjusted.parm("class").set(0)
    adjusted.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int e0 = findbyid("basesternum0");
        int e1_1 = findbyid("basesternum1_1");
        int e1_2 = findbyid("basesternum1_2");
        int e_neg1_2 = findbyid("basesternum-1_2");
        int e_neg1_1 = findbyid("basesternum-1_1");
        vector line_start = point(0, "P", e_neg1_2);
        vector line_end = point(0, "P", e1_2);
        vector line_direction = line_end - line_start;
        float line_length_squared = dot(line_direction, line_direction);
        if (line_length_squared <= 1e-12)
            error("Expected distinct frontest line endpoints");

        int front_points[] = array(e0, e1_1, e_neg1_1);

        for (int index = 0; index < len(front_points); ++index) {
            int point_number = front_points[index];
            vector position = point(0, "P", point_number);
            float line_parameter = dot(position - line_start, line_direction) / line_length_squared;
            vector aligned_position = line_start + line_parameter * line_direction;
            setpointattrib(0, "P", point_number, aligned_position, "set");
        }
    ''')
    return adjusted


def _fill_maxilla(parent: hou.SopNode, coxa: hou.SopNode) -> hou.SopNode:
    maxilla = parent.createNode("attribwrangle", "fill_maxilla")
    maxilla.setInput(0, coxa)
    maxilla.parm("class").set(0)
    maxilla.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int starts[] = findarraybyid("basesternum1_1", "basesternum-1_1");
        int ends[] = findarraybyid("basesternum1_2", "basesternum-1_2");
        int centers[] = findarraybyid("basesternum0", "basesternum0");
        int pivots[] = findarraybyid("sternumrim1", "sternumrim-1");
        for (int side = 0; side < len(starts); ++side) {
            vector start_position = point(0, "P", starts[side]);
            vector end_position = point(0, "P", ends[side]);
            vector center_position = point(0, "P", centers[side]);
            vector direction = normalize(end_position - start_position);
            int mx = addpoint(0, start_position + direction * distance(center_position, start_position));
            setid(array(mx), array(basemaxilla1 + side == 0 ? "1" : "-1"));
            int prim = fillfacebypoints(array(starts[side], mx, ends[side], pivots[side]));
            setprimattrib(0, "region", prim, "maxilla", "set");
        }
    ''')
    return maxilla


def _fill_pedicel_membrane(parent: hou.SopNode, coxa: hou.SopNode) -> hou.SopNode:
    pedicel = parent.createNode("attribwrangle", "fill_pedicel_membrane")
    pedicel.setInput(0, coxa)
    pedicel.parm("class").set(0)
    pedicel.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int p5 = findbyid("sternumrim5");
        int e5_1 = findbyid("basesternum5_1");
        int e5_2 = findbyid("basesternum5_2");
        vector p5_position = point(0, "P", p5);
        vector e5_1_offset = point(0, "P", e5_1) - p5_position;
        vector e5_2_offset = point(0, "P", e5_2) - p5_position;
        vector horizontal_direction = normalize(set(
            e5_1_offset.x + e5_2_offset.x,
            0,
            e5_1_offset.z + e5_2_offset.z
        ));
        vector px_offset = horizontal_direction * length(set(e5_1_offset.x, 0, e5_1_offset.z));
        px_offset.y = (e5_1_offset.y + e5_2_offset.y) / 2;
        int px0 = addpoint(0, p5_position + px_offset);
        setid(array(px0), array("baseend0"));
        int prim = fillfacebypoints(array(px0, e5_1, p5, e5_2));
        setprimattrib(0, "region", prim, "cephalothraox_pedicel", "set");
    ''')
    return pedicel


def _identify_side_inset_split(
    parent: hou.SopNode,
    input_node: hou.SopNode,
) -> hou.SopNode:
    node = parent.createNode("attribwrangle", "identify_side_inset_split")
    node.setInput(0, input_node)
    node.parm("class").set(0)
    node.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int split_points[];
        for (int point_number = 0; point_number < npoints(0); ++point_number) {
            if (startswith(point(0, "id", point_number), "sternummiddle"))
                append(split_points, point_number);
        }
        findpolyextrudesplits(split_points, "tmp_inset_split");
    ''')
    return node


def _inset_membrane(parent: hou.SopNode, coxa: hou.SopNode) -> hou.SopNode:
    regions = parent.createNode("attribwrangle", "identify_membrane_regions")
    regions.setInput(0, coxa)
    regions.parm("class").set(0)
    regions.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        addattrib(0, "prim", "tmp_insetscale", 0.0);

        for (int primitive = 0; primitive < nprimitives(0); ++primitive) {
            int points[] = primpoints(0, primitive);
            string primitive_id = prim(0, "id", primitive);
            if (primitive_id == "maxilla") {
                int pivot = -1;
                int outer = -1;
                foreach (int point_number; points) {
                    string point_id = point(0, "id", point_number);
                    if (point_id == "sternumrim1" || point_id == "sternumrim-1")
                        pivot = point_number;
                    if (point_id == "basesternum1_1" || point_id == "basesternum-1_1")
                        outer = point_number;
                }
                vector pivot_position = point(0, "P", pivot);
                vector outer_position = point(0, "P", outer);
                setprimattrib(0, "tmp_insetscale", primitive, distance(pivot_position, outer_position));
                continue;
            }
            int p0 = -1;
            int e0 = -1;
            foreach (int point_number; points) {
                string point_id = point(0, "id", point_number);
                if (point_id == "sternumrim0")
                    p0 = point_number;
                if (point_id == "basesternum0")
                    e0 = point_number;
            }
            if (p0 >= 0 && e0 >= 0) {
                setprimattrib(0, "id", primitive, "front_flap", "set");
                vector p0_position = point(0, "P", p0);
                vector outer_position = point(0, "P", e0);
                setprimattrib(0, "tmp_insetscale", primitive, distance(p0_position, outer_position));
                continue;
            }

            int midpoint = -1;
            int outer = -1;
            foreach (int point_number; points) {
                if (startswith(point(0, "id", point_number), "sternummiddle"))
                    midpoint = point_number;
            }
            if (midpoint < 0)
                continue;

            int midpoint_index = find(points, midpoint);
            if (midpoint_index == 0)
                outer = points[3];
            else if (midpoint_index == 1)
                outer = points[2];
            if (outer < 0)
                continue;

            setprimattrib(0, "id", primitive, "side_flap", "set");
            int boundary_point = points[midpoint_index == 0 ? 1 : 0];
            int boundary_outer = points[midpoint_index == 0 ? 2 : 3];
            setedgegroup(0, "tmp_side_flap_borders", boundary_point, boundary_outer, 1);
            vector midpoint_position = point(0, "P", midpoint);
            vector outer_position = point(0, "P", outer);
            float height = distance(midpoint_position, outer_position);
            setprimattrib(0, "tmp_insetscale", primitive, height);
        }
    ''')

    fused = parent.createNode("fuse", "fuse_membrane_midpoints")
    fused.setInput(0, regions)

    side = parent.createNode("polyextrude", "inset_side_membrane")
    side.setInput(0, fused)
    side.parm("group").set("@id=side_flap")
    side.parm("splittype").set(1)
    side.parm("usesplitgroup").set(1)
    side.parm("splitgroup").set("tmp_side_flap_borders")
    side.parm("inset").setExpression('ch("../membrane_ratio")')
    side.parm("uselocalinsetscaleattrib").set(1)
    side.parm("localinsetscaleattrib").set("tmp_insetscale")

    front = parent.createNode("polyextrude", "inset_front_membrane")
    front.setInput(0, side)
    front.parm("group").set("@id=front_flap")
    front.parm("splittype").set(1)
    front.parm("inset").setExpression('ch("../membrane_ratio")')
    front.parm("uselocalinsetscaleattrib").set(1)
    front.parm("localinsetscaleattrib").set("tmp_insetscale")

    maxilla = parent.createNode("polyextrude", "inset_maxilla")
    maxilla.setInput(0, front)
    maxilla.parm("group").set("@id=maxilla")
    maxilla.parm("splittype").set(0)
    maxilla.parm("inset").setExpression('ch("../membrane_ratio")')
    maxilla.parm("uselocalinsetscaleattrib").set(1)
    maxilla.parm("localinsetscaleattrib").set("tmp_insetscale")

    cleanup = parent.createNode("attribwrangle", "cleanup_membrane_groups")
    cleanup.setInput(0, maxilla)
    cleanup.parm("class").set(0)
    cleanup.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        removeprimattrib(0, "tmp_insetscale");
        removeprimattrib(0, "id");

        for (int point_number = 0; point_number < npoints(0); ++point_number) {
            string name = point(0, "id", point_number);
            if (name == "")
                continue;
            int original = findbyid(name);
            if (point_number != original)
                setid(array(point_number), array(""));
        }
    ''')

    groups = parent.createNode("groupdelete", "cleanup_tmp_side_flap_borders")
    groups.setInput(0, cleanup)
    groups.parm("deletions").set(1)
    groups.parm("enable1").set(1)
    groups.parm("grouptype1").set(3)
    groups.parm("group1").set("tmp_side_flap_borders")
    return groups


def _rotate_coxa_flaps(
    parent: hou.SopNode,
    coxa: hou.SopNode,
) -> hou.SopNode:
    rotated = parent.createNode("attribwrangle", "rotate_coxa_flaps")
    rotated.setInput(0, coxa)
    rotated.parm("class").set(0)
    rotated.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        float height_ratio = ch("../coxa_width_ratioy") / max(ch("../coxa_width_ratiox"), 1e-6);
        float depth_ratio = min(ch("../coxa_depth_ratio"), height_ratio);
        float rise_scale = height_ratio > 1e-6 ? depth_ratio / height_ratio : 0;

        for (int primitive = 0; primitive < nprimitives(0); ++primitive) {
            int points[] = primpoints(0, primitive);
            int ring_points[] = array(points[0], points[1]);
            int outer_points[] = array(points[3], points[2]);
            for (int index = 0; index < len(ring_points); ++index) {
                int ring_point = ring_points[index];
                int outer = outer_points[index];
                vector origin = point(0, "P", ring_point);
                vector offset = point(0, "P", outer) - origin;
                float height = length(offset);
                if (height <= 1e-6)
                    continue;

                float rise = height * rise_scale;
                float projected = sqrt(max(0, height * height - rise * rise));
                float projection_scale = projected / height;
                offset.x *= projection_scale;
                offset.z *= projection_scale;
                offset.y = rise;
                setpointattrib(0, "P", outer, origin + offset);
            }
        }
    ''')
    return rotated
