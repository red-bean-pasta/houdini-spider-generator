## Task

based on `checlierae_extrusion_model.md`, help me refactor the current extrusion model because it's maybe too big and hard to debug. 
break it down to multiple methods:
1. _prepare_extrusion:
do the `geo.deletePrims(socket_prims)`
do the `cheliceraestart*` attributing
2. _add_end_section:
do the end section calculation
add the points
attribute them
and do fill them from c1_1 to c4_1
attribute the prim with "region" as "fang"
3. _add_middle_section
do the somewhat complex math we've already done
add the points
attribute them as well
and do fill them
do not connect between sections (this allows easy debugging in the editor)
4. _connect_sections
delete middle section prim since it should be hollow
do the connection
