# Task background

This project originally uses inline VEX. It's now refactored to native python. It's not tested or debugged. Some logic may be inconsistent between legacy design and new design.

# steps

1. read `instructions/general.md`
2. address any user provided bug
3. inspect and solve any further problem in the `test.hip`, with user specifying the target subnet. You can use commands similar to:
```shell
hython -c '
import hou
import sys

hou.hipFile.load("test.hip")

root = hou.node("/obj/spider/cephalothorax/base")

if root is None:
    print("Node not found")
    sys.exit(1)

for node in root.allSubChildren():
    print("Cooking:", node.path())

    try:
        node.cook(force=True)
    except hou.Error as exc:
        print("\nFAILED:", node.path())

        errors = node.errors()
        if errors:
            for err in errors:
                print("  ERROR:", err)
        else:
            print("  ERROR:", exc)

        sys.exit(1)

print("All nodes cooked successfully.")
'
```
to navigate. This command is more as an example. You can use your own.
