- read rules under @folder:rules
## Task
currently, the model directly extrudes chelicerae out, like a hill on the ground. however, in real life, the chelicerae usually has an offset from the front face of spider and is connected by membrane, and i'm implementing this. this is actually quite simple to implement.

#### Steps
- read @file:head.py
- add new item "HEADCHELICERAEUPPER" to ID, and of course its affix_id wrapper method
- add a CONTROL node to head subnet; add a vector2 parameter called "lip_extrusion_ratio" of XYZW naming, and pass the help argument explaining that lip refers to the touching line between chelicerae and head, and the ratio is relative to the base support loop (membrane) height. min_max as (-1.0, 1.0)
- you can see that method _inset_base_loop adds a support loop along the base-chelicerae side of the head, and chelicerae is like a door on front face of the head. "headcheliceraeupper*" refers to the point above chliceraemembraneupper* points, so there are three points: headcheliceraeupper1, 0 and 1
- attribute headcheliceraeupper1, 0 and 1. it should ideally be its standalone method, as we wish to keep the method modular and small. it can be called by _inset_base_loop between inset(...) and deduplicate_id_attr(...) so it can easily reference: point with chliceraemembraneupper* attributes but later in index
- add a sop method (method that will be sopified as standalone node) called "_extrude_lips":
    - get baseline distance: base = headcheliceraeupper0.y() - chliceraemembraneupper0.y()
    - calculate offset_z and _y as base * lip_extrusion_ratiox and ...y
    - offset headcheliceraeupper*. positive offset_z decreases z (moves forward), and pos _y decreases y (moves down)
