# Repetitive abstraction findings

## Scope and method

Reviewed the Python generator modules in the project root and excluded `utilities/**` from the scan as requested. The review covered 14 Python files and 5,697 lines. `backup/**`, `.hip/.hipnc` files, and archived assistant notes were treated as artifacts rather than production source. `legacy/helper.h` was also treated as historical code, separate from the current Python generator.

Source files were not changed. This file is the only artifact produced by the review.

The scan found approximately 40 direct `geo.createPoint()` sites across nine modules, 69 `fill_face(geo, ...)` sites, eight `geo.clear()` geometry rebuilds, five mirror-node sites, and 87 `sopify(...)` calls. The repetition is concentrated in geometry construction and attribute bookkeeping.

## High-value candidates

### 1. Use the existing `LegParam.from_specs` factory

**Locations**

- `leg_builder.py:42-63` defines `LegParam.from_specs`, including the two length validations and the `zip` that creates `yaw_flex_specs`.
- `leg.py:275-310` reads the same parameter groups and manually constructs `LegParam`.
- `pedipalp.py:462-488` repeats the same manual construction.

**Recommendation**

Build both parameter objects through `LegParam.from_specs(...)`. In `pedipalp.py`, slice the yaw and flex arrays to the same length as the pedipalp length-ratio array before passing them, preserving the current truncation behavior.

**Why it helps**

This removes duplicated construction and keeps the length-mismatch validation in one place. It also makes future `LegParam` fields less likely to be added in one call site and forgotten in the other. No new helper is needed; the existing class method is currently unused.

### 2. Centralize rebuilding geometry from `(id, position)` records

**Locations**

- `head.py:221-230` — `_add_points` already implements the pattern locally.
- `base_sops.py:82-89` — clear geometry, create the `id` attribute, recreate points, then add rim edges.
- `pedicel.py:72-83` — materialize selected point data, clear geometry, recreate identified points.
- `abdomen.py:191-204` and `abdomen.py:245-262` — the same point recreation loop appears twice.
- `chelicerae.py:222-237` — two nearly identical recreation loops for base and upper points.
- `sternum.py:197-200` and `sternum.py:243-253` — related point recreation loops, one without IDs and one with IDs.

**Suggested boundary**

Add a helper such as `replace_points(geo, point_data, *, add_id=True)` to `helper.py`. It should clear the geometry, ensure the ID attribute when requested, create points, assign positions and IDs, and return the created points. The helper should accept already materialized positions because callers must finish reading old point positions before clearing the geometry.

**Why it helps**

The current implementation repeats Houdini mutation details in several body builders. A single helper makes the destructive reset explicit and gives every rebuild the same ID initialization behavior. `head._add_points` is the natural first implementation to move into the shared helper.

### 3. Centralize creation of an identified point

**Locations**

The recurring sequence is `geo.createPoint()`, `setPosition(...)`, then `setAttribValue("id", ...)` or `set_point_id(...)`. Examples include:

- `base_sops.py:147-154`, `base_sops.py:280-284`, and `base_sops.py:306-310`.
- `head.py:577-580` and `head.py:615-622`.
- `spider.py:253-268`, `spider.py:295-312`, and `spider.py:371-375`.
- `chelicerae.py:257-267`, `chelicerae.py:391-396`, `chelicerae.py:451-459`, and `chelicerae.py:627-634`.
- `abdomen.py:202-204`, `abdomen.py:260-262`, and `abdomen.py:302-304`.
- `leg_builder.py:482-485` and `leg_builder.py:560-568`.

**Recommendation**

Standardize on the existing `utilities.common.add_point(...)` where its attribute form fits, or add an ID-specific `add_id_point(geo, position, point_id)` wrapper in `helper.py`. It should return the new point. The current `add_point` utility is already used in `pedipalp.py:217`, `pedipalp.py:249`, `pedipalp.py:338`, `pedipalp.py:372`, and `pedipalp.py:401`, so this would also remove the current inconsistency between modules.

**Why it helps**

It removes low-level attribute-ordering boilerplate and prevents new identified points from accidentally omitting the ID attribute. This helper can also be used internally by the geometry-rebuild helper above.

### 4. Add a helper for filling a face and assigning an attribute

**Locations**

Many sites do this in two statements:

```python
prim = fill_face(geo, points, reverse)
prim.setAttribValue("region", region)
```

Examples are `base_sops.py:155`, `base_sops.py:283-284`, `head.py:349-383`, `chelicerae.py:269-270`, `chelicerae.py:457-459`, `leg_builder.py:98-104`, `leg_builder.py:435-461`, `leg_builder.py:578-591`, `leg_builder.py:641-642`, and `spider.py:378-386`.

**Suggested boundary**

Add a generic `fill_face_with_attr(geo, points, attr_name, value, reverse=False)` helper near the topology helpers. A narrower `fill_face_with_region(...)` would also work, but the generic form avoids creating another one-purpose wrapper if other primitive attributes need the same treatment.

**Why it helps**

The important operation is “construct this face as part of this classified surface.” Keeping face creation and classification together makes it harder to create an unclassified primitive and reduces repeated temporary-variable code.

### 5. Add a helper for bridging two cyclic four-point loops

**Locations**

- `chelicerae.py:692-706` bridges successive tube loops with the same cyclic index calculation.
- `leg_builder.py:433-462` repeats the same four-edge bridge twice, with different winding.
- `leg_builder.py:576-591` repeats the same four-edge bridge for both halves of a membrane.
- `abdomen.py:322-326` contains the same strip-building structure across four parallel loop families.
- `sternum.py:326-329` and `sternum.py:353-373` contain related loop-to-loop face stitching.

**Suggested boundary**

Add a topology helper such as `bridge_loops(geo, loop_a, loop_b, *, reverse=False, primitive_attr=None)`. It should iterate the cyclic pairs, create one quad per edge, optionally reverse the winding, and optionally assign an attribute through the face-attribute helper.

**Why it helps**

The cyclic indexing and winding rules are easy to get subtly wrong and are currently copied. The body-part code would describe which loops are connected while the topology helper owns the indexing mechanics. Callers must still pass loops in the correct semantic order; the helper should not try to infer orientation.

## Medium-value candidates

### 6. Centralize primitive filtering and blank-attribute classification

**Locations**

Primitive filters repeat across:

- `base_sops.py:348-358` and `base_sops.py:371-377`.
- `chelicerae.py:284-302`, `chelicerae.py:332-345`, and `chelicerae.py:649-650`.
- `leg.py:176-180` and `leg.py:204-207`.
- `spider.py:207-211` and `spider.py:452-463`.
- `pedipalp.py:132-133` and `pedipalp.py:503-511`.

The blank-region fallback repeats at `pedicel.py:172-174`, `head.py:432-434`, and `spider.py:425-427`.

**Suggested boundary**

Add `prims_by_attr(geo, attr_name, value, *, startswith=False)` to the common geometry helpers, plus `set_prim_attr_where_blank(geo, attr_name, value)` for the fallback classification. The filtering helper should support exact equality and prefix matching because both forms are present.

**Why it helps**

The repeated list comprehensions currently mix selection policy with the geometry operation that follows. Named helpers make intent visible and provide one place to standardize blank or missing attribute behavior. The existing `points_by_attr` helper suggests this is a natural complementary operation.

### 7. Use the existing `position_from_geo` helper

**Location**

`helper.py:41-47` already defines `position_from_geo`, but it has no callers.

**Repeated callers to simplify**

- `chelicerae.py:207-220` converts three `point_from_geo(...)` results into position lists.
- `head.py:251-264` converts looked-up points into a position dictionary.
- `base_sops.py:68-70` performs the same point-to-position conversion while collecting the sternum rim.
- Similar lookup-then-`.position()` sequences appear throughout `sternum.py`, `abdomen.py`, and `pedipalp.py`.

**Recommendation**

Use `position_from_geo(...)` whenever only positions are needed. This is a small cleanup, but it keeps ID lookup and position extraction consistent and makes the intended data shape apparent.

### 8. Centralize repeated point translation

**Locations**

- `head.py:340-342` translates two points by the same offset.
- `head.py:641-661` translates several groups of points by one shared offset.
- `spider.py:430-438` translates three opening points by the same Z offset.
- `chelicerae.py:800-803`, `chelicerae.py:819-822`, `chelicerae.py:959-960`, and `chelicerae.py:988-991` translate selected points by calculated offsets.

**Suggested boundary**

Add `translate_points(points, offset)` to `helper.py` or a geometry utility. It should apply `point.setPosition(point.position() + offset)` to each point.

**Why it helps**

This removes repeated mutation loops and makes it obvious which points move together. It is intentionally a small helper; it should remain limited to pure translation and should not absorb the callers' geometry-specific offset calculations.

### 9. Share the node-to-geometry adapter for left-ID renaming

**Locations**

- `head.py:590-592`
- `abdomen.py:355-357`
- `chelicerae.py:1023-1025`

Each wrapper exists only to pass `node.geometry()` into `helper.rename_left_ids`; the chelicerae variant additionally selects `affix_index=-1`.

**Suggested boundary**

Add `rename_left_ids_node(node, affix_index=0)` to `helper.py`. Use it directly for head and abdomen. Keep a tiny local adapter for the chelicerae-specific `-1` argument if the node-building API needs a stable callback name.

**Why it helps**

This removes two identical adapters without hiding the actual left-ID behavior. It is lower priority because each current wrapper is already short and clear.

## Small same-file candidates

- `chelicerae.py:80-85` has two identical `bottom_middle` and `upper_middle` functions differing only by the inserted label. A private `_middle_id(label, id_factory, ...)` helper would remove that duplication. Keep it in `chelicerae.py`; the naming convention is domain-specific and does not belong in a general utility.
- `sternum.py:212`, `sternum.py:220`, and `sternum.py:229` call `set_points_id([point], [point_id])` for one point. Use the existing `set_point_id(point, point_id)` helper for those cases and reserve `set_points_id` for actual batches.
- `chelicerae.py:544-554` has three thin section-specific wrappers around `_add_intermediate_section`. This is already a reasonable abstraction because each wrapper gives `sopify` a meaningful graph-stage name; collapsing the wrappers into a data table would make the node pipeline harder to read.

## Repetition that should remain explicit

- The long `sopify` chains in `base.py`, `head.py`, `chelicerae.py`, and `pedipalp.py` are repetitive by syntax, but each named variable corresponds to a visible Houdini graph stage. A generic chain runner would obscure stage names, intermediate outputs, and debug points.
- The `add_float_param` blocks are repetitive UI configuration, but labels, tuple sizes, ranges, and help text are part of each body-part module's public interface. A data-driven parameter registry could reduce lines, but it would make the UI definition harder to scan and is not an ideal first refactor.
- The one-line ID factory functions in `base_sops.py`, `head.py`, `abdomen.py`, `pedicel.py`, `chelicerae.py`, `spider.py`, and `sternum.py` share a shape, but their explicit names are the readable domain vocabulary used throughout the geometry code. Replacing them with dynamic factories would save boilerplate at the cost of discoverability and typing.
- `add_reloadable_subnet`, `add_merge`, `add_fuse`, `add_mirror`, `add_output`, and `sopify` already provide the right level of node-construction abstraction. Wrapping those calls again in a project-wide builder would mostly hide the Houdini network structure.

## Suggested implementation order

1. Replace the two manual `LegParam` constructions with `LegParam.from_specs`.
2. Add and adopt the identified-point and geometry-rebuild helpers.
3. Add the face-with-attribute and cyclic-loop bridge helpers together, since they address the same topology-construction layer.
4. Add primitive filtering/default-classification helpers.
5. Apply the smaller existing-helper cleanups (`position_from_geo`, `set_point_id`, translation, and the rename adapter).
