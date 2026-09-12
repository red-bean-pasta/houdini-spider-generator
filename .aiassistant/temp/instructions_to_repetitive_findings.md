# High and medium value candidates
1. Use the existing `LegParam.from_specs` factory: Yes
2. Centralize rebuilding geometry: Yes
3. Centralize creation of an identified point: Yes, and a `add_id_point(geo, position, point_id)` wrapper makes sense
4. filling a face and assigning an attribute: Yes
5. bridging two cyclic four-point loops: Yes
6. Centralize primitive filtering and blank-attribute classification: Yes
7. Use the existing `position_from_geo` helper: Yes
8. Centralize repeated point translation: This is already defined in `utilities.topology` tho haven't applied
9. Share the node-to-geometry adapter for left-ID renaming: Share

# Small same-file candidates:
1. `bottom_middle` and `upper_middle`: this is fine. no change needed.
2. `set_points_id([point], [point_id])`: you can refactor this
3. `_add_intermediate_section`: then no refactor


# Repetition that should remain explicit
1. the long sopify chains can be refactored into something like `sopify_chain` so that when inserting new nodes, there's less refrences updating need to do. variable name does not affect Houdini graph naming, but the method name. Many of the time the variable name are themselves just repeating the method name. 
so in fact, a generic runner is desierable. Tho it cannot really generalize non-sopify nodes like "merge"
2. the add_float_param is fine.
3. thos one-line ID factory is explicitly defined to save typing and discovering trouble despiter more boilerplate. this is fine.
