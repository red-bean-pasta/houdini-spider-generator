## Task
build leg segments as basic cubes with wedge

## Steps
- read `instructions/general.md`;
- read `chelicerae.py` for basic references to handy helper methods and dependencies, from line 1 to 174;
- add following parameters to `leg.py`:
    - float parameter joint_height_ratio
    - float parameter joint_lateral_spine_ratio
    - vector2 parameter joint_shrink_ratio
- try understand and verify the correctness of the existing method `_calc_segment_offset` and its called methods. Essentially it calculates the wedged angle and offset needed, when the laternal spine is aligned. A few convention to note first: if two segments forms straight chain, the yaw is 0 as expected, but the flex is 180 degrees, not 0. This is because flex measures the "unfold" degrees, not "vector" degrees.
