import hou

from sop_helper import add_fuse, add_merge, add_mirror, add_output


IDS = (
    "sternumrim0", "sternumrim1", "sternummiddle1", "sternumrim2", "sternummiddle2",
    "sternumrim3", "sternummiddle3", "sternumrim4", "sternummiddle4", "sternumrim5",
    "sternummiddle-4", "sternumrim-4", "sternummiddle-3", "sternumrim-3",
    "sternummiddle-2", "sternumrim-2", "sternummiddle-1", "sternumrim-1",
)

def build(cephalothroax: hou.SopNode) -> hou.SopNode:
    sternum = cephalothroax.createNode("subnet", "sternum")
    parameters = _add_parameters(sternum)
    control = _add_controls(sternum)
    half = _add_left_half(sternum)
    midpoints = _add_midpoints(sternum, half)

    mirror = add_mirror(sternum, midpoints, "right_mirror", (1, 0, 0), True, False)
    point_ids = _add_point_ids(sternum, mirror)

    spine = _add_spine(sternum, point_ids)

    merge = add_merge(sternum, "merge_boundary_and_spine", point_ids, spine)
    fuse = add_fuse(sternum, "fuse_center_points", merge)
    depth = _add_depth(sternum, fuse)
    faces = _add_faces(sternum, depth)

    output = add_output(sternum, "OUT_STERNUM", faces)
    sternum.layoutChildren()
    return sternum


def _add_parameters(sternum: hou.SopNode) -> hou.SopNode:
    templates = sternum.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "width_length_ratio",
            "Width Length Ratio",
            3,
            default_value=(1.0, 2.0, 1.825),
            min=0.0,
            min_is_strict=True,
            naming_scheme=hou.parmNamingScheme.XYZW,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "top_width_ratio",
            "Top Width Ratio",
            1,
            default_value=(0.5,),
            min=0.0,
            max=1.0,
            min_is_strict=True,
            max_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "width_depth_ratio",
            "Width Depth Ratio",
            1,
            default_value=(0.5,),
            min=0.0,
            min_is_strict=True,
        )
    )
    sternum.setParmTemplateGroup(templates)
    return sternum


def _add_controls(parent: hou.SopNode) -> hou.SopNode:
    control = parent.createNode("null", "CONTROL")
    templates = control.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "half_width",
            "Half Width",
            1,
            default_value=(100.0,)
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "leg_angle",
            "Leg Angle",
            1,
            default_value=(165.0,),
            min=0.0,
            max=180.0,
            min_is_strict=True,
            max_is_strict=True,
        )
    )
    control.setParmTemplateGroup(templates)

    return control


def _add_left_half(parent: hou.SopNode) -> hou.SopNode:
    half = parent.createNode("attribwrangle", "left_half")
    half.parm("class").set(0)  # detail mode
    half.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        vector ratio = set(
            ch("../width_length_ratiox"),
            ch("../width_length_ratioy"),
            ch("../width_length_ratioz")
        );
        float angle = radians(ch("../CONTROL/leg_angle"));
        float w = ch("../CONTROL/half_width");
        float forward_height = w / ratio.x * ratio.y;
        float back_half = w / ratio.x * ratio.z;
        float l = sqrt(back_half * back_half + w * w) / (2.0 * sin(angle / 2.0));
        float top_width = w * ch("../top_width_ratio");

        vector p0 = set(0, 0, -forward_height);
        vector p1 = set(top_width, 0, -forward_height);
        vector p3 = set(w, 0, 0);
        vector p5 = set(0, 0, back_half);
        
        float p3_p5_p4 = (M_PI - angle) / 2.0;
        float o_p3_p5 = atan2(back_half, w);
        float o_p3_p4 = p3_p5_p4 + o_p3_p5;
        vector p4 = p3 + l * set(-cos(o_p3_p4), 0, sin(o_p3_p4));

        float p1_p3_x = p3.x - p1.x;
        float p1_p3_z = p3.z - p1.z;
        float p1_p3_length = sqrt(p1_p3_x * p1_p3_x + p1_p3_z * p1_p3_z);
        float midpoint_x = (p1.x + p3.x) / 2.0;
        float midpoint_z = (p1.z + p3.z) / 2.0;
        float midpoint_p2 = sqrt(l * l - p1_p3_length * p1_p3_length / 4.0);
        vector p2 = set(
            midpoint_x + p1_p3_z / p1_p3_length * midpoint_p2,
            0,
            midpoint_z - p1_p3_x / p1_p3_length * midpoint_p2
        );

        vector p[] = array(p0, p1, p2, p3, p4, p5);
        int curve = addprim(0, "polyline");
        foreach (vector pos; p)
            addvertex(0, curve, addpoint(0, pos));
    ''')
    return half


def _add_midpoints(parent: hou.SopNode, half: hou.SopNode) -> hou.SopNode:
    midpoints = parent.createNode("attribwrangle", "add_midpoints")
    midpoints.setInput(0, half)
    midpoints.parm("class").set(0)
    midpoints.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int original[] = primpoints(0, 0);
        int points[] = {};
        for (int index = 0; index < len(original) - 1; ++index) {
            append(points, original[index]);
            if (index == 0)
                continue;

            vector a = point(0, "P", original[index]);
            vector b = point(0, "P", original[index + 1]);
            append(points, addpoint(0, (a + b) / 2));
        }
        append(points, original[-1]);
        removeprim(0, 0, 0);
        int curve = addprim(0, "polyline");
        foreach (int point_number; points)
            addvertex(0, curve, point_number);
    ''')
    return midpoints


def _add_point_ids(parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    point_ids = parent.createNode("attribwrangle", "add_point_ids")
    point_ids.setInput(0, p_input)
    point_ids.parm("class").set(0)
    point_ids.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        addattrib(0, "point", "id", "");
        int right_points[] = primpoints(0, 0);
        int left_points[] = primpoints(0, 1);

        setid(array(right_points[0]), array("sternumrim0"));
        for (int index = 1; index < len(right_points); ++index) {
            string id = index % 2
                ? sprintf("sternumrim%d", (index + 1) / 2)
                : sprintf("sternummiddle%d", index / 2);
            setid(array(right_points[index]), array(id));
        }
        for (int index = 1; index < len(left_points) - 1; ++index) {
            // The mirrored primitive runs from sternumrim5 back to sternumrim0, so count the negative-side IDs from its sternumrim0 end.
            int id_index = (len(left_points) - index) / 2;
            string id = index % 2
                ? sprintf("sternummiddle-%d", id_index)
                : sprintf("sternumrim-%d", id_index);
            setid(array(left_points[index]), array(id));
        }
    ''')
    return point_ids


def _add_spine(p_parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    spine = p_parent.createNode("attribwrangle", "center_spine")
    spine.setInput(0, p_input)
    spine.parm("class").set(0)
    spine.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        for (int prim = nprimitives(0) - 1; prim >= 0; --prim)
            removeprim(0, prim, 1);
        addattrib(0, "point", "id", "");
        int right_points[] = primpoints(1, 0);
        for (int index = 2; index < len(right_points) - 1; ++index) {
            vector position = point(1, "P", right_points[index]);
            int spine_point = addpoint(0, set(0, 0, position.z));
            setid(array(spine_point), array(sprintf("sternumspine%d", index - 1)));
        }
    ''')
    spine.setInput(1, p_input)
    return spine


def _add_depth(p_parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    depth = p_parent.createNode("attribwrangle", "descend_sternum_spine")
    depth.setInput(0, p_input)
    depth.parm("class").set(0)
    depth.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        float d = ch("../CONTROL/half_width")
            * ch("../width_depth_ratio");

        int sternumrim0 = findbyid("sternumrim0");
        int sternumrim3 = findbyid("sternumrim3");
        int sternumrim5 = findbyid("sternumrim5");
        vector top = point(0, "P", sternumrim0);
        vector middle = point(0, "P", sternumrim3);
        vector bottom = point(0, "P", sternumrim5);

        for (int point_number = 0; point_number < npoints(0); ++point_number) {
            if (!startswith(point(0, "id", point_number), "sternumspine"))
                continue;

            vector position = point(0, "P", point_number);
            if (position.z <= middle.z)
                position.y = -abs(position.z - top.z) / abs(middle.z - top.z) * d;
            else
                position.y = -abs(bottom.z - position.z) / abs(bottom.z - middle.z) * d;
            setpointattrib(0, "P", point_number, position);
        }
    ''')
    return depth


def _add_faces(p_parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    faces = p_parent.createNode("attribwrangle", "build_sternum_faces")
    faces.setInput(0, p_input)
    faces.parm("class").set(0)
    faces.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        string ids[] = array(__IDS__);
        int n = (len(ids) - 4) / 2;
        for (int i = 0; i < n; ++i) {
            string spine0 = i == 0 ? ids[0] : sprintf("sternumspine%d", i);
            string spine1 = sprintf("sternumspine%d", i + 1);
            fillfacebyids(array(spine0, ids[i + 1], ids[i + 2], spine1));
            fillfacebyids(array(spine0, spine1, ids[len(ids) - 2 - i], ids[len(ids) - 1 - i]));
        }
        fillfacebyids(array(sprintf("sternumspine%d", n), ids[n + 1], ids[n + 2], ids[n + 3]));
    '''.replace("__IDS__", ", ".join(f'"{p}"' for p in IDS)))
    return faces


def _get_root() -> hou.Node:
    obj = hou.node("/obj")
    assert obj is not None
    return obj
