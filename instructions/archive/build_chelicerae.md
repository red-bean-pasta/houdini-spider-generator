## Task 1

build chelicerae mesh in the existing `chelicerae.py`, which currently only insets membrane but does no extrusion.

#### Steps

* read `instructions/general.md`

* reactor current "height_ratio" parameter to "socket_height_ratio". add help message "Relative to chelicerae region width"

* add vector2 parameters "middle_section_ratio", "middle_section_offset", "middle_section_rotation", "end_section_ratio", "end_section_offset", and "end_section_rotation", respectively default to (1.1, 1.2), (-0.1, 0), (-90, 0), (0.5, 0.5), (0.25, 0) and (-90, 0).
Yeah, it's kinda complex.

* add vector2 parameter "section_offsets_y", default to (2, 5). add help message "Relative to the socket height"

* add method "_build_extrusion". call it after `cleanup = sopify(chelicerae, classified, _cleanup_inset_flaps)`

* in `_build_extrusion`:
    // following operations only consider the right side
    * get the height and width length of the socket, excluding the membrane. this can be done by identifying the prims with "chelicerasocket" "region" attribute, get the ones who are right to the world origin, get the `h = y_max - y_min` and `w = x_max - x_min`. let's say the (x_min, y_min) point as c1_1, (x_min, y_max) as c1_2, (x_max, y_max) as c1_3, and (x_max, y_min) as c1_4
    * `up_pivot = vector3((x_max + x_min) / 2, ...)`
    * `offset_baseline = vector3(h, h, w)`
    * `middle_pivot_offset =  vector3(middle_section_offset.x, section_offsets_y.x, middle_section_offset.y)`
    * `end_pivot_offset =  vector3(end_section_offset.x, section_offsets_y.y, end_section_offset.y)`
    * `middle_pivot = up_pivot + offset_baseline * middle_pivot_offset`
    * `end_pivot = up_pivot + offset_baseline * end_pivot_offset`
    * you can therefore construct the rectangles around pivot using `(w, h) * middle_section_ratio`, then rotate it to get the roated one. "..._section_rotation" does not contain rotation around `y`.
    * then you can connect the quads. let's name the one connecting c1_1 as ci_1, c1_2 as ci_2 etc. so the rectangle around middle pivot is c2_1...4
    * but before we connect them, let's add another section loop between middle loop c2 and end loop c4:
        * c3_4.x = c2_4.x * 1/3 + c4_4.x * 2/3
        * similar to c3_3.x
        * c3_1.x = c2_1.x * 2/3 + c4_1.x * 1/3
        * similar to c3_2.x
        * c3_i.y = c2_i.y * 1/3 + c4_i * 2/3; same for c3_i.z
        * combine for new loop
    * now connect faces. fill the end loop as well, despite it further extrude as the fang
    * add attributes "cheliceraei_j" to these `ci_j` points. you can `tuple or array((), (), (), ())` structure for storing and then smartly add attributes
    * there are a lot of similar codes. so you can generlize them into small methods or intermediate methods then make _build_extrusion a orchestration method
    * face orientation doesn't matter. use loop
    
    There might be typos and bugs in my description. you can validate and adjust them as long as you understand what mesh i'm building.
    
