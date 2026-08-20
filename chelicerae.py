import hou

from helper import add_output


IDS = (
    "cheliceraeupper-2",
    "cheliceraeupper-1",
    "cheliceraeupper0",
    "cheliceraeupper1",
    "cheliceraeupper2",
)

def build(cephalothorax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    chelicerae = cephalothorax.createNode("subnet", "chelicerae")
    chelicerae.setInput(0, base)
    parameters = _add_parameters(chelicerae)
    geometry = _add_geometry(chelicerae)
    regions = _identify_inset_flaps(chelicerae, geometry)
    inset = _inset_flaps(chelicerae, regions)
    cleanup = _cleanup_inset_flaps(chelicerae, inset)
    output = add_output(chelicerae, "OUT_CHELICERAE", cleanup)

    chelicerae.layoutChildren()
    return chelicerae


def _add_parameters(chelicerae: hou.SopNode) -> hou.SopNode:
    templates = chelicerae.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "height_ratio",
            "Height Ratio",
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
    chelicerae.setParmTemplateGroup(templates)
    return chelicerae


def _add_geometry(chelicerae: hou.SopNode) -> hou.SopNode:
    geometry = chelicerae.createNode("attribwrangle", "build_chelicerae")
    geometry.setInput(0, chelicerae.indirectInputs()[0])
    geometry.parm("class").set(0)
    geometry.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int e0 = findbyid("basesternum0");
        int e1_1 = findbyid("basesternum1_1");
        int mx1 = findbyid("basemaxilla1");
        int mx_neg1 = findbyid("basemaxilla-1");
        int e_neg1_1 = findbyid("basesternum-1_1");
        if (e0 < 0 || e1_1 < 0 || mx1 < 0 || e_neg1_1 < 0 || mx_neg1 < 0)
            error("Expected five chelicerae base-loop points");

        vector e0_position = point(0, "P", e0);
        vector e1_1_position = point(0, "P", e1_1);
        vector e_neg1_1_position = point(0, "P", e_neg1_1);
        vector mx1_position = point(0, "P", mx1);
        vector mx_neg1_position = point(0, "P", mx_neg1);
        vector base_positions[] = array(
            mx_neg1_position,
            e_neg1_1_position,
            e0_position,
            e1_1_position,
            mx1_position
        );
        string base_ids[] = array("basemaxilla-1", "basesternum-1_1", "basesternum0", "basesternum1_1", "basemaxilla1");
        for (int primitive = nprimitives(0) - 1; primitive >= 0; --primitive)
            removeprim(0, primitive, 1);

        int base_points[];
        for (int index = 0; index < len(base_positions); ++index) {
            int base_point = addpoint(0, base_positions[index]);
            setid(array(base_point), array(base_ids[index]));
            append(base_points, base_point);
        }

        int upper_points[];
        string upper_ids[];
        float height = distance(mx1_position, e0_position) * ch("../height_ratio");
        vector height_offset = set(0, height, 0);

        for (int index = 0; index < len(base_points); ++index) {
            int upper_point = addpoint(0, base_positions[index] + height_offset);
            string upper_id = sprintf("cheliceraeupper%d", index - 2);
            setid(array(upper_point), array(upper_id));
            append(upper_points, upper_point);
            append(upper_ids, upper_id);
        }

        for (int segment = 0; segment < len(base_points) - 1; ++segment) {
            fillfacebypoints(array(
                base_points[segment],
                base_points[segment + 1],
                upper_points[segment + 1],
                upper_points[segment]
            ));
            setprimattrib(0, "id", nprimitives(0) - 1, "chelicera", "set");
        }
    ''')
    return geometry


def _identify_inset_flaps(parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    regions = parent.createNode("attribwrangle", "identify_inset_flaps")
    regions.setInput(0, p_input)
    regions.parm("class").set(0)
    regions.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        addattrib(0, "prim", "tmp_insetscale", 0.0);
        int lower = findbyid("basesternum0");
        int upper = findbyid("cheliceraeupper0");
        if (lower < 0 || upper < 0)
            error("Expected chelicera points basesternum0 and cheliceraeupper0");
        vector lower_position = point(0, "P", lower);
        vector upper_position = point(0, "P", upper);
        float insetscale = distance(lower_position, upper_position);
        for (int primitive = 0; primitive < nprimitives(0); ++primitive)
            setprimattrib(0, "tmp_insetscale", primitive, insetscale);
        setedgegroup(0, "tmp_chelicera_flap_borders", lower, upper, 1);
    ''')
    return regions


def _inset_flaps(parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    inset = parent.createNode("polyextrude", "inset_flaps")
    inset.setInput(0, p_input)
    inset.parm("group").set("@id=chelicera")
    inset.parm("splittype").set(1)
    inset.parm("usesplitgroup").set(1)
    inset.parm("splitgroup").set("tmp_chelicera_flap_borders")
    inset.parm("inset").setExpression('ch("../membrane_ratio")')
    inset.parm("uselocalinsetscaleattrib").set(1)
    inset.parm("localinsetscaleattrib").set("tmp_insetscale")
    return inset


def _cleanup_inset_flaps(parent: hou.SopNode, p_input: hou.SopNode) -> hou.SopNode:
    cleanup = parent.createNode("attribwrangle", "cleanup_inset_flaps")
    cleanup.setInput(0, p_input)
    cleanup.parm("class").set(0)
    cleanup.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        removeprimattrib(0, "tmp_insetscale");
        for (int point_number = npoints(0) - 1; point_number >= 0; --point_number) {
            string id = point(0, "id", point_number);
            if (id == "")
                continue;
            int original = findbyid(id);
            if (point_number != original)
                setid(array(point_number), array(""));
        }
    ''')

    groups = parent.createNode("groupdelete", "cleanup_inset_flap_borders")
    groups.setInput(0, cleanup)
    groups.parm("deletions").set(1)
    groups.parm("enable1").set(1)
    groups.parm("grouptype1").set(3)
    groups.parm("group1").set("tmp_chelicera_flap_borders")
    return groups
