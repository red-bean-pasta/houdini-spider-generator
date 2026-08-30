#### Background
Currently, the chelicerae extrusion method doesn't address the pentagon problem: c1_1 (cheliceraestart1) and c1_2 actually have a point in the middle, cheliceramiddlelower1.
We need to wire it into quads but also avoid it spreading throughout the whole model, so a loop cut is not an option.

The solution is easy: because there are two pentagons, the (cheliceraestart1, cheliceramiddlelower1, cheliceraestart2, cheliceraeuppermiddle1, cheliceraeuppermiddle2), and its left mirror, we can keep it local by making (cheliceraestart1, cheliceraeuppermiddle1, chlicerateuppermiddle4, chelicerae4), (cheliceraestart1, cheliceraestart4, cheliceraeupper0, cheliceraelower0), and their left mirror, pentagons, or loop cutted. 
In another word, the backface of the right start-uppermiddle loop, the loop's left side face, the two in-the-middle membranes, and the left loop's right side face, and the backface of the left side face.

we need to add points on each connecting edges between these faces:
1. cheliceraestart1, cheliceraeuppermiddle1
2. cheliceraestart1, cheliceraestart4
3. cheliceraeupper0, cheliceraelower0

and the left side of these three points.

I hope you understand what model I'm describing.

#### Steps:
- read `instructions/general.md`
- add method "_remove_retopology_faces", in it delete the current faces of the mentioned faces that requires retopology, keep points.
note that (cheliceraestart1, cheliceramiddlelower1, cheliceraestart2, cheliceraeuppermiddle1, cheliceraeuppermiddle2) and its left counterpart are constructed without taking cheliceramiddlelower1 into account.
- add method "_add_retopology_points", add the mentioned points
- add method "_fill_retopology_faces", fill the quads. I believe you can correctly identify them. 

Each method should be its own SOP and get sopified.

- add method "_retopology_upper_membrane". remove cheliceraeupper1, cheliceramiddleupper1, and their -1 points. then fill the now clean faces:
cheliceraeupper0, cheliceraeupper2, cheliceraestart3, chelicerae4; and its left part

You can mind the face orientation or maybe not.
all of these methods are of course called after `renamed = sopify(chelicerae, mirrored, _rename_left_ids)`
