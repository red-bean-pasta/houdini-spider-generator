# Long-method analysis

## Scope and method

Reviewed the Python files in the generator project root, including `../../scripts/build_test_hip.py`, and excluded the `utilities` package. The `utilities` entry is a symlink to the external Houdini utility project, so its implementation was not included. `backup/*.hipnc`, `test.hip`, `test.hipnc`, `legacy/helper.h`, and archived assistant notes were treated as project artifacts rather than Python generator methods.

The scan covered 15 Python files and 5,560 lines. Function length was measured from the declaration through the next declaration or class at the same indentation level. The initial screen was methods of roughly 30 lines or more; each result was then judged by whether it contains multiple understandable phases that could be named. The line count includes signatures, comments, and blank lines.

Locations and line counts in this analysis refer to the pre-refactor source snapshot. The subsequent implementation work is recorded in `long_method_refactor_log.md`.

## Strong extraction candidates

These methods combine several distinct responsibilities. Extracting child methods would leave a short parent that describes the operation in domain terms, even where the child is called only once.

### 1. `leg._adjust_coxa` — 95 lines — high priority

Location: `leg.py:311`

The method validates and unpacks socket data, computes adjusted upper and lower support positions, mutates the generated coxa support loop, calculates the buffer distance, creates two buffered pentagons, creates the front and back side faces, and deletes the temporary coxa start points.

Suggested child methods:

- `_get_adjusted_coxa_support_positions(...)` for the `ratio1`/`ratio2` calculations and the four adjusted positions.
- `_set_coxa_support_loop_positions(...)` for applying those positions to `coxa_start_support_pts`.
- `_build_coxa_socket_faces(...)` for the two buffered pentagons and the five side quads.
- `_remove_coxa_start_points(...)` for the final cleanup.

The parent could then read as validation, support-position adjustment, face construction, and cleanup. The geometry objects and computed positions should stay explicit in the parent or be passed to the child methods; hidden global state would make this topology operation harder to follow.

### 2. `head._fill_back_loop_faces` — 92 lines — high priority

Location: `head.py:341`

This method has four separate stages: three front/cheek faces, a front pentagon with two newly identified points, a table-driven set of top/back faces, and blank-region classification.

Suggested child methods:

- `_fill_head_front_faces(geo)`
- `_add_head_front_pentagon(geo)`
- `_fill_head_top_and_back_faces(geo)`
- `_classify_unassigned_head_faces(geo)`

This is a particularly good extraction because the method already has comments and data structures that mark the stages. The current body is long mainly because each face is written inline.

### 3. `head._fill_side_faces` — 90 lines — high priority

Location: `head.py:455`

The method collects and validates the right-side sternum loop, separates front and back points, computes normalized front/back ratios, creates one trio of named side points per layer, bridges each layer with four faces, and closes the two end faces.

Suggested child methods:

- `_get_head_side_layer_ratios(...)` for loop ordering and ratio calculation.
- `_add_head_side_layer_points(...)` for interpolating and naming the side points.
- `_fill_head_side_layer_faces(...)` for the repeated four-face strip.
- `_fill_head_side_end_faces(...)` for the final two cap faces.

The parent would retain the high-level order and make the topology construction much easier to inspect.

### 4. `chelicerae._add_intermediate_section` — 84 lines — high priority

Location: `chelicerae.py:540`

This method reads four parameter groups, derives start/middle/end frames, computes the elliptical interpolation position and tangent, derives interpolation weights, interpolates section size, constructs and validates the section loop, and finally creates either identified or anonymous points before filling the face.

Suggested child methods:

- `_get_intermediate_section_frame(...)` for the middle pivot, interpolated direction, and normal.
- `_get_intermediate_section_weights(...)` for `f_upper`, `f_lower`, `w_start`, `w_mid`, `w_end`, and `t`.
- `_get_intermediate_section_size(...)` for the weighted start/middle/end dimensions.
- `_add_section_loop_points(...)` for point creation, ID assignment, and face filling.

The three existing thin wrappers (`_add_middle_section`, `_add_upper_middle_section`, and `_add_lower_middle_section`) should remain; their names are useful Houdini graph stage names. The extraction belongs inside the shared implementation.

### 5. `spider._reconnect_upper_sternum_pedicel_loop` — 57 lines — high priority

Location: `spider.py:341`

The method deletes old head-back primitives, computes right and left support positions, creates the two new points, reconnects four head-back faces, and adds two buffer membrane faces.

Suggested child methods:

- `_remove_upper_head_back_faces(...)`
- `_create_upper_pedicel_support_points(...)`
- `_fill_upper_pedicel_head_back_faces(...)`
- `_fill_upper_pedicel_buffer_faces(...)`

The current method is a good example of a topology edit whose mutation phases should be visible in the parent.

### 6. `chelicerae._connect_sections` — 61 lines — high priority

Location: `chelicerae.py:624`

It defines and applies the cap-face predicate, connects the socket membrane to the start support loop with four faces, gathers five tube loops, and bridges adjacent loops.

Suggested child methods:

- `_remove_section_cap_faces(geo)`
- `_connect_membrane_to_start_support(geo)`
- `_bridge_chelicerae_section_loops(geo)`

The local `is_cap_face` predicate would belong with the first child. This would make the parent a compact description of the three topology operations.

### 7. `chelicerae._inset_chelicerae_support_loop` — 58 lines — high priority

Location: `chelicerae.py:830`

The method identifies medial and lateral boundary pairs, traverses two upper strips, calculates the inset distance, performs the inset, delegates point adjustment, and deduplicates IDs.

Suggested child methods:

- `_get_chelicerae_support_strip_prims(geo)` for the two `traverse_faces_between_edges` calls.
- `_inset_chelicerae_support_strips(geo, prims)` for distance calculation and inset.
- Keep `_adjust_chelicerae_support_loop` as the named post-inset stage.

The existing `_adjust_chelicerae_support_loop` already exposes a useful child stage; extracting strip discovery and inset setup would give the method the same clarity throughout.

### 8. `leg_builder._append_segment` — 81 lines — high priority

Location: `leg_builder.py:148`

The method unpacks the former segment, derives its dimensions, computes the latter segment dimensions, solves the membrane offset and wedge, builds all eight latter positions, then modifies the former segment's bottom end to apply the wedge.

Suggested child methods:

- `_get_former_segment_dimensions(...)`
- `_build_latter_segment_positions(...)`
- `_apply_former_segment_wedge(...)`

The call to `_calc_segment_offset_and_wedge` already marks the boundary between solving and construction. Naming the remaining two construction phases would make the coordinate math substantially easier to review.

### 9. `leg_builder._fill_membranes` — 64 lines — high priority

Location: `leg_builder.py:499`

The loop body extracts two joint loops, derives membrane length and midpoint positions, adjusts the lower midpoint, creates four points, and bridges the former-to-middle and middle-to-latter loops.

Suggested child methods:

- `_get_membrane_midpoint_positions(former_end, latter_start)`
- `_create_membrane_midpoints(geo, positions)`
- `_bridge_membrane_joint(geo, former_loop, mid_loop, latter_loop)`

The outer method would remain responsible for iterating joints and returning the accumulated points.

## Medium-priority candidates

These methods are long enough to benefit from named phases, but the improvement is smaller or depends on whether the surrounding topology API is being changed at the same time.

- `abdomen._add_height_frame`, `abdomen.py:203`, 53 lines. Parameter and temporary-attribute lookup, height derivation, and vertical-frame point materialization are separate phases. `_get_abdomen_height_frame_positions(...)` would isolate the coordinate calculation. `_add_width_frame` at `abdomen.py:164` is shorter and more linear, but could follow the same pattern if consistency between the paired frame builders matters.
- `abdomen._prepare_cephalothorax_info`, `abdomen.py:125`, 39 lines. It measures the source geometry, derives pedicel and upper/lower-span values, and writes four temporary global attributes. `_get_cephalothorax_measurements(...)` could return the derived values while the parent handles attribute storage.
- `pedicel._connect_pedicel`, `pedicel.py:82`, 87 lines. Most of the length is a declarative four-quadrant configuration. Extracting `_get_pedicel_quadrant_configs(...)` and `_connect_pedicel_quadrant(...)` would make the repeated operation explicit, but the current tuple already documents the four cases reasonably well.
- `leg._get_right_coxa_socket_points`, `leg.py:201`, 40 lines. Extract `_get_socket_group_points(group)` for shared-point detection, outer-point classification, and ordering. The outer method would only sort primitives, group them, and collect results.
- `chelicerae._build_geometry`, `chelicerae.py:212`, 43 lines. Split input point collection from face creation: `_get_chelicera_base_and_upper_positions(...)`, `_fill_chelicera_base_face(...)`, and the existing `_retain_headbase_faces(...)`.
- `chelicerae._add_start_membrane`, `chelicerae.py:341`, 44 lines. Split `_get_start_membrane_offsets(...)` from `_add_start_membrane_points(...)`. The method currently mixes parameter-derived vector math with topology mutation.
- `chelicerae._adjust_start_membrane_curve`, `chelicerae.py:742`, 40 lines. Extract `_get_start_membrane_curve_offsets(...)` and `_apply_start_membrane_curve_offsets(...)`.
- `head._extrude_lip`, `head.py:610`, 40 lines. The three point groups are independent: chelicerae/support points, front points, and front-mid/float points. A child per group would make the intended extrusion coverage clearer.
- `pedipalp._add_maxilla_quads_to_geo`, `pedipalp.py:313`, 39 lines. Split quad position calculation from point creation and face filling. This is useful if more maxilla topology is added later.
- `leg_builder._calc_membrane_spec`, `leg_builder.py:250`, 56 lines. Validation, initial distance selection, the straight-flex shortcut, wedge solving, and max-wedge/max-distance limiting are separate decisions. `_get_initial_membrane_spec(...)` and `_apply_membrane_spec_limits(...)` would make the branch structure easier to review; the existing solver helpers should remain the numerical boundary.
- `leg_builder._add_segment_thickness`, `leg_builder.py:404`, 44 lines. Each joint repeats the same inset-and-bridge operation for the former end and latter start loops. Extract `_add_joint_thickness_loops(...)` to keep the outer method focused on joint iteration and accumulation.
- `spider._position_vertical_pedicel_points`, `spider.py:274`, 43 lines. Lower-point placement and upper-point placement are independent phases; `_position_lower_pedicel_points(...)` and `_position_upper_pedicel_points(...)` would clarify the two coordinate constructions.
- `sternum._build_subdivided_spine_faces`, `sternum.py:328`, 45 lines. Split front faces, side quads, and rear diamond faces. The nested `_lerp` helper can remain local or become a small geometry child if the interpolation is reused.
- `helper.rename_left_ids`, `helper.py:178`, 46 lines. The method combines left-point filtering, ID parsing, affix negation, and attribute replacement. `_split_id_prefix_and_affixes(...)` would isolate the parsing policy, though this is lower priority because the current nested functions already provide some grouping.

## Long methods that should remain intact

Length alone does not make these methods poor extraction targets.

- `base.build`, `abdomen.build`, `chelicerae.build`, `head.build`, `leg.build`, `pedicel.build`, `pedipalp.build`, and `spider.build` are Houdini graph orchestration methods. Their named intermediate nodes and ordered stages communicate the graph structure. Splitting them would likely hide the build pipeline without reducing domain complexity.
- `_add_parameters` and `_add_controls` methods in `../../spider_generator/chelicerae.py`, `../../spider_generator/head.py`, `../../spider_generator/leg.py`, and `../../spider_generator/sternum.py` are long because they declare the public Houdini UI. The headings and help text already group the intent; child methods would add indirection without grouping geometry logic.
- `leg_builder._solve_membrane_wedge_remain_rad`, `sternum._left_half`, and `head._compute_top_corners` are focused mathematical kernels. They contain several formulas, but the formulas describe one calculation and splitting them would make the data flow harder to trace.
- `spider._open_cepha_pedicel` is 83 lines, but almost all of its body is context lookup followed by calls to already well-named child operations. It is an orchestration method with a long argument unpacking block. A context object could shorten it, but that would be a broader API change rather than a simple readability extraction.
- `leg_builder._get_leg_points` is 48 lines and already delegates each segment transition to `_append_segment`; extracting the initial coxa literal would save lines but would not materially improve the method's purpose.

## Recommended order if refactoring later

1. `leg._adjust_coxa`, `head._fill_back_loop_faces`, and `head._fill_side_faces`, because each has multiple topology phases and the parent methods would become substantially easier to review.
2. `chelicerae._add_intermediate_section`, `_connect_sections`, and `_inset_chelicerae_support_loop`, because they are central to the chelicera construction and have clear phase boundaries.
3. `leg_builder._append_segment` and `_fill_membranes`, because the coordinate math and joint topology are each dense enough to deserve names.
4. `spider._reconnect_upper_sternum_pedicel_loop` and the medium-priority methods as related body-part work is touched.

This analysis report was created before source changes. Existing files in `aitemp` were preserved, and the subsequent refactor log was added separately.
