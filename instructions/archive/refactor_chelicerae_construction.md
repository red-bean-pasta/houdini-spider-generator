## Task
Refactor chelicerae extrusion logic to utilize `utilities.topology.interpolate_conic`.

#### Steps

###### prerequisites
* read `instructions/general.md`.

###### adjust parameters
* move parameters "end_section_offset" and "end_section_rotation" before "middle_section_..."
* remove "middle_section_rotation"
* remove "section_offsets_y" by merging it into "end_section_offset" and "middle_section_offset". thus, "..._section_offset" is now vector3, with its second value as the "..._offset_y"

###### refactor construction logic
the original construction first determines middle and end pivots first, then builds the corresponding cross section, add another layer of section(c3), then connect the dots.
we now migrate to this:
* determine end and middle pivots, similar as before
* derive the middle pivot's rotation from `utilities.topology.interpolate_conic`. this can benefit from making its own method "_interpolate_middle_section_rotation":
    * pass up_pivot as p0, end_pivot as p1, middle_pivot as p2, up_pivot's direction (the normal to the up section c1_1-c1_2-c1_3-c1_4) as slope0, and end_pivot's rotation as slope1 (up_pivot's normal rotated by end_section_rotation)
    * get the result evaluation function, pass p2 back to it, get its normal, which is the rotation
* similar connecting as before
