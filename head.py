import hou

from helper import add_fuse, add_merge, add_mirror, add_output


def build(cephalothroax: hou.SopNode, base: hou.SopNode) -> hou.SopNode:
    head = cephalothroax.createNode("subnet", "head")
    head.setInput(0, base)
    _add_parameters(head)
    base_rim = _extract_base_rim(head)
    base_points = _extract_head_base(head)
    corners = _add_corners_half(head, base_points)
    back_faces = _fill_back_loop_faces(head, corners)
    right_half = _fill_side_faces(head, back_faces)
    mirrored = add_mirror(head, right_half, "left_mirror", (1, 0, 0), True, False)
    faces = _rename_left_ids(head, mirrored)
    merged = add_merge(head, "merge_base_rim", base_rim, faces)
    fused = add_fuse(head, "fuse_base_rim", merged)
    add_output(head, "OUT_HEAD", fused)
    head.layoutChildren()
    return head


def _add_parameters(head: hou.SopNode) -> None:
    templates = head.parmTemplateGroup()
    templates.append(
        hou.FloatParmTemplate(
            "height_ratio",
            "Height Ratio",
            1,
            default_value=(0.375,),
            min=0.0,
            min_is_strict=True,
        )
    )
    templates.append(
        hou.FloatParmTemplate(
            "flat_ratio",
            "Flat Ratio",
            1,
            default_value=(0.4,),
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
    head.setParmTemplateGroup(templates)


def _extract_head_base(head: hou.SopNode) -> hou.SopNode:
    points = head.createNode("attribwrangle", "extract_head_base")
    points.setInput(0, head.indirectInputs()[0])
    points.parm("class").set(0)
    points.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        string excluded_ids[] = array("basesternum0", "basesternum1_1");
        for (int primitive = nprimitives(0) - 1; primitive >= 0; --primitive)
            removeprim(0, primitive, 0);

        for (int point_number = npoints(0) - 1; point_number >= 0; --point_number) {
            string id = point(0, "id", point_number);
            vector position = point(0, "P", point_number);
            if (position.x < 0 || find(excluded_ids, id) >= 0
                || (!startswith(id, "base") && !startswith(id, "chelicerae") && id != "sternumrim0"))
                removepoint(0, point_number);
        }
    ''')
    return points


def _extract_base_rim(head: hou.SopNode) -> hou.SopNode:
    rim = head.createNode("attribwrangle", "extract_base_rim")
    rim.setInput(0, head.indirectInputs()[0])
    rim.parm("class").set(0)
    rim.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        string excluded_ids[] = array("basesternum0", "basesternum1_1", "basesternum-1_1");
        for (int primitive = nprimitives(0) - 1; primitive >= 0; --primitive)
            removeprim(0, primitive, 0);

        for (int point_number = npoints(0) - 1; point_number >= 0; --point_number) {
            string id = point(0, "id", point_number);
            if (find(excluded_ids, id) >= 0 || (!startswith(id, "base") && !startswith(id, "chelicerae")))
                removepoint(0, point_number);
        }
    ''')
    return rim


def _add_corners_half(
    head: hou.SopNode,
    base_points: hou.SopNode,
) -> hou.SopNode:
    corners = head.createNode("attribwrangle", "add_corners_half")
    corners.setInput(0, base_points)
    corners.parm("class").set(0)
    corners.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int sternumrim0 = findbyid("sternumrim0");
        int cheliceraeupper0 = findbyid("cheliceraeupper0");
        int basesternum1_2 = findbyid("basesternum1_2");
        int baseend0 = findbyid("baseend0");
        if (sternumrim0 < 0 || cheliceraeupper0 < 0 || basesternum1_2 < 0 || baseend0 < 0)
            error("Expected head reference points");

        vector sternumrim0_position = point(0, "P", sternumrim0);
        vector cheliceraeupper0_position = point(0, "P", cheliceraeupper0);
        vector baseend0_position = point(0, "P", baseend0);
        vector basesternum1_2_position = point(0, "P", basesternum1_2);
        float z_baseend0_cheliceraeupper0 = baseend0_position.z - cheliceraeupper0_position.z;
        float y_cheliceraeupper0_sternumrim0 = cheliceraeupper0_position.y - sternumrim0_position.y;
        vector y_offset = set(0, z_baseend0_cheliceraeupper0 * ch("../height_ratio"), 0);
        vector z_offset = set(0, 0, z_baseend0_cheliceraeupper0 * ch("../flat_ratio"));
        
        vector headfront0_position = cheliceraeupper0_position + y_offset - set(0, cheliceraeupper0_position.y - sternumrim0_position.y, 0);
        vector headfront1_position = basesternum1_2_position + y_offset - set(0, basesternum1_2_position.y - sternumrim0_position.y, 0);
        vector headback0_position = headfront0_position + z_offset;
        vector headback1_position = headfront1_position + z_offset;
        vector headtopmiddle1_position = (headfront1_position + headback1_position) / 2;
        vector headtopmiddle0_position = (headfront0_position + headback0_position) / 2;
        int headfront0 = addpoint(0, headfront0_position);
        int headfront1 = addpoint(0, headfront1_position);
        int headback0 = addpoint(0, headback0_position);
        int headback1 = addpoint(0, headback1_position);
        int headtopmiddle1 = addpoint(0, headtopmiddle1_position);
        int headtopmiddle0 = addpoint(0, headtopmiddle0_position);
        setid(
            array(headfront0, headfront1, headback0, headback1, headtopmiddle1, headtopmiddle0),
            array("headfront0", "headfront1", "headback0", "headback1", "headtopmiddle1", "headtopmiddle0")
        );
        removepoint(0, sternumrim0);
    ''')
    return corners


def _fill_back_loop_faces(
    head: hou.SopNode,
    corners: hou.SopNode,
) -> hou.SopNode:
    faces = head.createNode("attribwrangle", "fill_back_loop_faces")
    faces.setInput(0, corners)
    faces.parm("class").set(0)
    faces.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        string points[] = array(
            "cheliceraeupper0", "headfront0", "headfront1", "cheliceraeupper2", "cheliceraeupper1",
            "cheliceraeupper2", "headfront1", "basesternum1_2", "basemaxilla1",
            "headfront0", "headfront1", "headtopmiddle1", "headtopmiddle0",
            "headtopmiddle0", "headtopmiddle1", "headback1", "headback0",
            "headback0", "headback1", "basesternum5_1", "baseend0"
        );
        int face_sizes[] = array(5, 4, 4, 4, 4);
        int offset = 0;
        foreach (int face_size; face_sizes) {
            string face_ids[] = {};
            for (int index = 0; index < face_size; ++index) {
                append(face_ids, points[offset + index]);
            }
            fillfacebyids(face_ids);
            offset += face_size;
        }
    ''')
    return faces


def _fill_side_faces(
    head: hou.SopNode,
    back_faces: hou.SopNode,
) -> hou.SopNode:
    faces = head.createNode("attribwrangle", "fill_side_faces")
    faces.setInput(0, back_faces)
    faces.parm("class").set(0)
    faces.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        int add_named_point(vector position; string id)
        {
            int point_number = addpoint(0, position);
            setid(array(point_number), array(id));
            return point_number;
        }

        int candidates[] = {};
        for (int point_number = 0; point_number < npoints(0); ++point_number) {
            string id = point(0, "id", point_number);
            vector position = point(0, "P", point_number);
            if (!startswith(id, "basesternum") || position.x <= 0)
                continue;
            append(candidates, point_number);
        }

        // Sort by -P.z: back to front.  The two e1 points share a z value;
        // retain the one farther out on the right-side boundary.
        for (int index = 1; index < len(candidates); ++index) {
            int candidate = candidates[index];
            vector candidate_position = point(0, "P", candidate);
            float candidate_z = candidate_position.z;
            int previous = index - 1;
            while (previous >= 0) {
                vector previous_position = point(0, "P", candidates[previous]);
                if (previous_position.z >= candidate_z)
                    break;
                candidates[previous + 1] = candidates[previous];
                --previous;
            }
            candidates[previous + 1] = candidate;
        }

        int right_side[] = {};
        foreach (int candidate; candidates) {
            if (len(right_side) > 0) {
                int previous = right_side[-1];
                vector candidate_position = point(0, "P", candidate);
                vector previous_position = point(0, "P", previous);
                if (abs(candidate_position.z - previous_position.z) <= 1e-6) {
                    if (candidate_position.x > previous_position.x)
                        right_side[-1] = candidate;
                    continue;
                }
            }
            append(right_side, candidate);
        }

        if (len(right_side) < 3 || len(right_side) % 2 == 0)
            error("Expected an odd, symmetric right-side sternum loop");

        int center_index = (len(right_side) - 1) / 2;
        int center = right_side[center_index];
        vector center_position = point(0, "P", center);

        int front_points[] = {};
        for (int index = center_index + 1; index < len(right_side); ++index)
            insert(front_points, 0, right_side[index]);

        int back_points[] = {};
        for (int index = 0; index < center_index; ++index)
            append(back_points, right_side[index]);

        if (len(front_points) != len(back_points))
            error("Expected matching front and back sternum loops");

        vector offsets_front[] = {};
        vector offsets_back[] = {};
        foreach (int point_number; front_points)
            append(offsets_front, center_position - point(0, "P", point_number));
        foreach (int point_number; back_points)
            append(offsets_back, center_position - point(0, "P", point_number));

        float front_outer_length = length(offsets_front[0]);
        float back_outer_length = length(offsets_back[0]);
        if (front_outer_length <= 1e-6 || back_outer_length <= 1e-6)
            error("Expected nonzero sternum side offsets");

        float ratios_front[] = {};
        float ratios_back[] = {};
        for (int index = 1; index < len(offsets_front); ++index)
            append(ratios_front, length(offsets_front[index]) / front_outer_length);
        for (int index = 1; index < len(offsets_back); ++index)
            append(ratios_back, length(offsets_back[index]) / back_outer_length);

        int headfront = findbyid("headfront1");
        int headmiddle = findbyid("headtopmiddle1");
        int headback = findbyid("headback1");
        if (headfront < 0 || headmiddle < 0 || headback < 0)
            error("Expected head side reference points");

        vector headfront_position = point(0, "P", headfront);
        vector headback_position = point(0, "P", headback);
        vector headfront_delta = headfront_position - center_position;
        vector headback_delta = headback_position - center_position;

        int headsidefronts[] = {};
        int headsidemiddles[] = {};
        int headsidebacks[] = {};
        for (int index = 0; index < len(ratios_front); ++index) {
            vector front_position = center_position + headfront_delta * ratios_front[index];
            vector back_position = center_position + headback_delta * ratios_back[index];
            vector middle_position = (front_position + back_position) / 2;
            int layer = index + 1;
            string front_id = sprintf("headsidefront%d", layer);
            string middle_id = sprintf("headsidemiddle%d", layer);
            string back_id = sprintf("headsideback%d", layer);
            append(headsidefronts, add_named_point(front_position, front_id));
            append(headsidemiddles, add_named_point(middle_position, middle_id));
            append(headsidebacks, add_named_point(back_position, back_id));
        }

        int current_front = headfront;
        int current_middle = headmiddle;
        int current_back = headback;
        for (int layer = 0; layer < len(headsidefronts); ++layer) {
            int next_front = headsidefronts[layer];
            int next_middle = headsidemiddles[layer];
            int next_back = headsidebacks[layer];
            fillfacebypoints(array(current_front, front_points[layer], front_points[layer + 1], next_front));
            fillfacebypoints(array(current_front, next_front, next_middle, current_middle));
            fillfacebypoints(array(current_middle, next_middle, next_back, current_back));
            fillfacebypoints(array(current_back, next_back, back_points[layer + 1], back_points[layer]));

            current_front = next_front;
            current_middle = next_middle;
            current_back = next_back;
        }

        fillfacebypoints(array(current_front, front_points[-1], center, current_middle));
        fillfacebypoints(array(current_middle, center, back_points[-1], current_back));
    ''')
    return faces


def _rename_left_ids(
    head: hou.SopNode,
    mirrored: hou.SopNode,
) -> hou.SopNode:
    renamed = head.createNode("attribwrangle", "rename_left_ids")
    renamed.setInput(0, mirrored)
    renamed.parm("class").set(0)
    renamed.parm("snippet").set(r'''
        #include "$HIP/helper.h"
        for (int point_number = 0; point_number < npoints(0); ++point_number) {
            vector position = point(0, "P", point_number);
            if (position.x >= 0)
                continue;

            string id = point(0, "id", point_number);
            int first_digit = -1;
            for (int index = 0; index < len(id); ++index) {
                if (isdigit(slice(id, index, index + 1))) {
                    first_digit = index;
                    break;
                }
            }
            if (first_digit < 0)
                error("Expected a numeric suffix in point id %s", id);

            string renamed_id = sprintf(
                "%s-%s",
                slice(id, 0, first_digit),
                slice(id, first_digit, len(id))
            );
            setid(array(point_number), array(renamed_id));
        }
    ''')
    return renamed
