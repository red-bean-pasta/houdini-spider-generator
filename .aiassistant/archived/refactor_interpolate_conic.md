## Task
refactor the `interpolate_conic` method under `utilities/topology.py`. it currently takes argument "slope0" and "slope1", yet to make caller easier and consitent with returned function, migrate to "normal0" and "normal1", repsectively represent the normal of p0 and p1. "normal" heres means the direction perpendicular to the original slope0 and slope1, and points inwards to the conic shape (since it's a concave shape).

#### Steps
- Read `instructions/general.md`
- Update `interpolate_conic`
- Update `chelicerae._interpolate_middle_section_rotation` and its callsite. This is the only consumer of `interpolate_conic`
