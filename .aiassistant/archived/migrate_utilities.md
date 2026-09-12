## Task 1

update stale utility method references across this project

#### Background

the original utility class, `hom_helper`, `sop_helper` and `dev_helper` are now migrated to its own project. they are system linked under `./utilities` and get rearranged into six scripts. Some project specific helper methods are still retained and put in `../../spider_generator/helper.py`.


#### Steps

* read `instructions/general.md`.

* query stale references across `*.py` scripts under `../generator`, aka this very project.
you can query them easily by `grep 'hom_helper|sop_helper|dev_helper'` or similar commands.

* patch those references file by file. do not patch them all together as i will revise the changes.

* this proejcts directly creates a lot of subnets by e.g., `createNode("subnet", "base")`. they should now migrate to use `utilities.nodes.add_reloadable_subnet` for hot reload capability.

* migrate test_build.py logic to `utilities.developing.save`

#### Notes

* the method names, argument signatures and its inner logics may be updated or generalized. 

* the generalized utility methods can wrapped further in `./utilities/helper.py` if you find it can benefiticial. for example, `add_id_attr`, `points_by_id` and `set_id` etc., since this project is heavily built around "id" as the identifier. 

* if you happen to find bugs in utility scripts, you can request to patch them if your sandbox allows. if it doesn't, record them in the answer. but this is not the focus of the task, and you don't have to inspect the scripts just for this.
