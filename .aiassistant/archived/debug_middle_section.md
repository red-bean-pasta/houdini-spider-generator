## Task
verify `chelicerae._build_extrusion`

#### Steps
- read `instructions/general.md`
- verify c1_4 is directly above c1_1, c1_2 is directly to the right of c1_1, and c1_3 is the other rectangle corner;
- verify that (c1_4 - c1_1) is pointing directly along +y, and `normal0` is therefore along -y;
- verify socket_prims `socket_prims[0]` is to the right of world origin, and that `-get_prim_normal(socket_prims[0])` is pointing along +z;
- verify `normal1` is pointing towards +y since end_section rotates by -90 degrees. 
- verify the points order to middle section loop and end section loop follows the order of start loop (c1..4)

If any of these step fails, analyze why and apply fix.
