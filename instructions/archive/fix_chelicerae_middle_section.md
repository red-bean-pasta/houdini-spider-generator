## Task 1
Fix the middle section point order of chelicerae. 
Currently, the middle section (variables are c2_i) are ordered wrong, for example, its c2_1 should be c2_4, and c2_4 should c2_1. But the end section and start section are correctly ordered.

#### Steps

* read `instructions/general.md`.

* pin down why the order is wrong, instead of brutally change the loop order.

* apply corresponding fix.


## Task 2
refactor the chelicerae "id" naming. It currently use `checlierae$i_$j`. it should now migrate to cheliceraestart$j, cheliceraemiddle$j and cheliceraeend$j. 

#### Steps
* add `CHELICERAESTART` etc., to `ID(StrEnum)`.

* add `cheliceraestart(*i: int|str)` etc., methods after `cheliceraeupper`.

* remove the original c3 loop for now, the one explicitly constrcuted by 1/3 and 2/3 logic.

* you can still use c1/2/3 to shorthand variables, but in `set_point_id`, update the value assignment logic.
