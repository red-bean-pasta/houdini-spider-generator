** always read rules under `.aiassistant/rules/` **

## Task 1
> finished

prepare the topology for lip (head and chelicerae membrane area).

#### Background
since we don't want to blindly add loop cuts at the base side of head, yet we still needs support edges at the membrane side for extrusion and sharpening, we need to keep it local. we need a total of 4 points. let's take edge  (cheliceraemembraneupper0, headcheliceraeupper0) as example, it needs three points at the upper half: two for support, and one for extrusion; and also one at the lower half for support.
therefore, there are 4 points on (cheliceraemembraneupper0, headcheliceraeupper0), (cheliceraemembraneupper1, headcheliceraeupper1) and -1 side. 
we then need to refill the (cheliceraemembraneupper1, headcheliceraeupper1, basemaxilla1, headbasemaxilla1): it's now 2 + 2 + 4 = 8 side faces. note that headbasemaxilla1 isn't attributed but you can guess it's the point on the inset loop from basemaxilla1.
The retopology is simple. but we'll talk about it later.
 
#### Steps
1. preparation
- create a new file called `lip.py`
- create a new subnet "lip" under cephalothorax subnet. put it under `fuse_base_and_head`. it should simply call `lip.build`. you can see `../../spider_generator/head.py` for reference on how to do this.
- migrate `lip_extrusion_ratio` to `lip` subnet. not as CONTROL, but direct subnet level parameter. it can simply be renamed to `extrusion_ratio`.
- clean up `../../spider_generator/head.py` since now it doesn't handle lip extrusion: unneeded point referencing etc. skip if there's nothing to do.


## Task 2
> finished

add the 4 loops on two faces: (cheliceraemembraneupper0, headcheliceraeupper0, cheliceraemembraneupper1, headcheliceraeupper1) and -1 side.
to do that, we can add points manually. but it may be better to extend the exisiting `loop_cut` method in `utilities.topology.py`. We can extend an optional argument "scope: list[hou.Prim] | None = None". it can then check if the continous loop is in the scope, if not, that side is discontinued. this is an useful extension.

#### Steps
- verify if loop_cut does loop cuts on both direction
- extend loop_cut to support the `scope` parameter
- in `lip.py`, add a sopify method `_add_loops`, then call loop_cut five times, passing only the two faces as scope. however, due to each loop cut will change the prim and edge, we need to calculate the delta distance beforehand and then pass in distance. 

we don't do retopology for now. 
bug: using distance will result the two other edges, (cheliceraemembraneupper1, headcheliceraeupper1) to be out of proportion, because distance is fixed. we should use delta ratio then.


## Task 3
> finished

refactor `../../spider_generator/head.py` so that the support loop does add public attributes instead of private ones. 
I've already added wrapper method:
```
def headbasesupport(*i: int | str) -> str:
    return affix_id(ID.HEADBASESUPPORT, *i)
```
you need to refactor `_attribute_inset_points` so that it attributes everything instead of just the original `headcheliceraeupper*` attributes. `headcheliceraeupper*` is already deleted.
the attribute is simple. if the original point is baseend0, then the inset point should be attributed as `headbasesupport("baseend0")`, returnning `headbasesupport_baseend0`

This method will disrupt serveral downstream nodes: `lip.py` and `../../spider_generator/spider.py`. for example, `lip.py` uses `headcheliceraeupper` and `../../spider_generator/spider.py` doesn't utilize the new introduction of `headbasesupport_baseend0`. fix them.


## Task 4
> finished

remove the two faces that need retopology and retopo them.

#### Steps
1. refactor the script:
- add ID enum 
- add item LIPSUPPORT
- add wrapper method `lip_support(*i)`

you can reference similar designs at `../../spider_generator/head.py`

- refactor `_add_loops` to attribute added points. first loop is attributed as `lipsupport1_[1|0|-1]`

2. remove the faces: (cheliceraemembraneupper1, headsupport_cheliceraemembraneupper1, basemaxilla1, headsupport_basemaxilla1), and its left sibling.
make this its own sopify node

3. retopology these two faces:
(cheliceraemembraneupper1, basemaxilla1, headsupport_basemaxilla1) forms an triangle angle. we can get the formula of its middle line, the line that evenly divide this angle. the we can get the y offset, given the x offset of lipsupport4_1, let's attributed it as i4. (i4, basemaxilla1, cheliceraemembraneupper1, lipsupport4_1) therefore forms a quad. same rule apply to (i4, i3, lipsupport3_1, lipsupport4_1).
The same rules apply to the other side: the (headsupport_cheliceraemembraneupper1, headsupport_basemaxilla1, basemaxilla1). then, two quads can be formed: (i1, headsupport_basemaxilla1, headsupport_cheliceraemembraneupper1, lipsupport1_1), (i2, i1, lipsupport1_1, lip_suppor2_1).
then we can fill the rest quads: (i4, i1, headsupport_basemaxilla1, basemaxilla1), (i4, i1, i2, i3), (i3, i2, lipsupport2_1, lipsupport3_1)
i may order or name them wrong. but you know the shape i'm describing.
you can write working method first, verify them, then refactor the code to avoid excessive hardcoding and too long boilerplate, with hlper submethods.

the same rules apply to the left side. so it can be generalized into one helper method. 


## Task 5
> finished

extrude lip

#### Steps
- add a method before _retopo_faces called _extrude_lip
- read extrusion_ratio
- get baseline = headsupport_cheliceraemembraneupper0.y() - cheliceraemembraneupper0.y()
- get z_offset = -baseline * extrusion_ratiox
- get y_offset = -baseline * extrusion_ratioy
- offset suppor loop 2 by (0, y_offset, z_offset)
- align loop 3 and 4 to the line of (loop2_i, cheliceraemembraneupper_i)

* loop 3 should keep the same distance to loop 2, not same ratio; loop 4 should keep same distance to cheliceraemembraneupper. that's what support loop mean.
* fix: move loop1, headbasesupport_cheliceraemembraneupper[0|1|-1], headfront[0|1|-1] and headsupport[0|1|1] by (0, y_offset, z_offset) as well


## Task 6
> finished

give smoother transition between loop1-loop2-loop3. 

#### Steps
- add float parameter `lip_width_ratio`. add help message indicating it's evaluated against the height of head support loop.
- add a new sopify method after `_extrude_lip` called "_adjust_lip_width". 
- in `_adjust_lip_width`:
    - baseline, aka head support loop height, is easy to calculate: headsupport_basemaxilla1.y() - basemaxilla1.y()
    - calculate existing_width, which is loop1_0.y() - loop2_0.y()
    - move headbasesupport_cheliceraemembraneupper* and headsupport1_* up by `lip_width_ratio * baseline - exsiting_width`
    note that headsupport1_1 and -1, and headbasesupport_cheliceraemembraneupper1 and -1, should be moved along their original line, instead of just +y
    
    
## Task 7
> finished

the retopo in Task 5 is too "croweded" at the basemaxilla1 and headsupport_basemaxilla1 side. the subdivision would therefore look very weird.
help me identify how to improve the topology flow.
you can be wild on this one.


## Task 8
refactor @file:lip.py : remove the four loops and the retopology and related logic. simply extrude headsupport_cheliceraemembraneupper* by the offset

