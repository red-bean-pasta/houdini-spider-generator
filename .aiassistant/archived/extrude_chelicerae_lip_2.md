## Task 1
prepare the topology for lip (head and chelicerae membrane area).

#### Background
since we don't want to blindly add loop cuts at the base side of head, yet we still needs support edges at the membrane side for extrusion and sharpening, we need to keep it local. we need a total of 4 points. let's take edge  (cheliceraemembraneupper0, headcheliceraeupper0) as example, it needs three points at the upper half: two for support, and one for extrusion; and also one at the lower half for support.
therefore, there are 4 points on (cheliceraemembraneupper0, headcheliceraeupper0), (cheliceraemembraneupper1, headcheliceraeupper1) and -1 side. 
we then need to refill the (cheliceraemembraneupper1, headcheliceraeupper1, basemaxilla1, headbasemaxilla1): it's now 2 + 2 + 4 = 8 side faces. note that headbasemaxilla1 isn't attributed but you can guess it's the point on the inset loop from basemaxilla1.
The retopology is simple. but we'll talk about it later.
 
#### Steps
1. preparation
- create a new file called `lip.py`
- create a new subnet "lip" under cephalothorax subnet. put it under `fuse_base_and_head`. it should simply call `lip.build`. you can see `head.py` for reference on how to do this.
- migrate `lip_extrusion_ratio` to `lip` subnet. not as CONTROL, but direct subnet level parameter. it can simply be renamed to `extrusion_ratio`.
- clean up `head.py` since now it doesn't handle lip extrusion: unneeded point referencing etc. skip if there's nothing to do.
