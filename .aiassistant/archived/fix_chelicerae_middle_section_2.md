## Task
debug chelicerae._build_extrusion and apply corresponding fix. its end section is currently wrong, with its longer side along z-axis. the middle section is worse. you can inspect the .hip file for more info.

you must understand the consturction model: 
the conic has three points, start pivot, middle pivot and end pivot. start pivot's conic normal (not face normal), is c1_1 - c1_4, which is the -y axis. end pivot's conic normal is +y, in this -90 degrees setup, where end section's face normal is -y, while start section's normal is -z. we can then get the conic normal of middle pivot, which is its along direction (c2_1 - c2_2), while its face normal is the start section's face normal rotated.
note that conic_normal1 is a sparate control, not something conic_normal0 derived. 
