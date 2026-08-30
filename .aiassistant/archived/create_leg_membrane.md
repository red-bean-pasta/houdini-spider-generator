## Task
build membrnae topology on each leg segment's gap

#### Background
each leg segment is a flat pyramid shape due to wedge. they are also tubes because they have two open faces. let's annotate the side to the base/sternum/coxa as start, and the other as end. let's also say the point smaller in z, aka more forward, as 1, and the other as 2. so 

#### Steps
- read `leg.py`
- add method `_fill_mebranes` after `_build_leg`: `_fill_mebranes(seg_pts: list[hou.Point]) -> list[hou.Point]`. `list[hou.Point]` are the ordered points from `_build_leg`;
- in `_fill_mebranes`:
    - it should add four points per gap. gap is easy to derive: `gap_pts = seg_pts[3:-3]` and sliced every 8, i think;
    - assert gap_pts % 8 == 0
    - for i in len(gap_pts) / 8
    - fu1, fu2, fb1, fb2, lu1, lu2, lb1, lb2 = gap_pts[i:i+8] # f: former; l: latter; u: upper; b: bottom
    - get lf = fb1.distance_to(fb2), same for ll
    - membrane_length = (lf + ll) * 0.5
    - mu1 = (fu1 + lu1) * 0.5, same for mu2
    - mb1 = mu1 - (0, membrane_length, 0), same for mb2
    - essentially it's adding a loop between the former edge loop and the latter, so it's easy now to fill the faces
    
