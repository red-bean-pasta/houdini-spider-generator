---
apply: always
---

# Background
This project aims to model a biologically justifiable spider in Houdini. It generates SOPs using Houdini Object Model (HOM) in Python. The API module in Python is `hou`. The executable is `hython`. The scope is restricted under `.../models/spider/generator/`, and there's no need to inspect upwards. Prefer building small SOPs and breaking down a big task into multiple steps. SOPs allows easy inspecting and modular designing. Insides one SOP, prefer modular methods. It's encouraged to write reusable methods, helper methods, wrapper methods, and methods simply for purpose documenting and logical grouping. breaking down into multiple.

# Other coding conventions
No need for over-defensiveness. `assert` is natively supported in HOM. Keep the code concise. By "concise", I don't mean use a lot of abbreviations or inappropriate one-liners, but no boilerplate and repetitiveness. Make the code easy to understand. New lines should be used mainly for logical grouping rather than viewport carriage. You can add comments to annotate a code block. You can use abbreviations for variable naming if the method is modular and short. You can add comment behind the variable to annotate the full name at its first appearence.
It's highly discouraged to use hardcoded Python or VEX SOP. You should always use the `sopify` method under `utilities.nodes`.
You can start out a task by a "just-work" method caring nothing about commenting, logical grouping and modularity, then refactor it into a code block that's clear, modular, logically comprehensive to human user. I believe you know what gives a bad block of code, like repetitive pattern and hardcoding. 
Put helper and modular methods after the main method instead of before it. This is because users usually read from the top, therefore higher position means more importance. 

# Other project conventions
This project is heavily based the point and primitive attribute system in Houdini, and in python, it heavily uses StrEnum and wrapper method for refactorability. Don't be afraid to add new attribute and temporary attribute (prefixed with "tmp_"). You can consider attribute as the link between model space and biological component. 
At the end of most tasks, you need to rerun `hython test_builder.py` and reinspect the regenerated `test.hip` to see if there's any errors. But if the task is deliberate half-way under the user's instruction, you can skip it. 

# Other agent instructions
You don't need to over-think. If the task is simple, you can simply do it. It's also encouraged to adopt the "inspect code + write code + try + error + debug" than "inspect files". You don't need to be 100% confident before making changes.
Many of the time, your operations are prompted to user by ACP or MCP. You can always comment the intention, so that the user has a better understanding on what stage we are at, if your direction is wrong or what the code is for.
You can always actively prompt for clarification, answer for multiple choices etc. The user may not write the best prompt, clarify their need enough and may have typos and reference errors, you can always point them out and ask for clarification. 
For file editing, prefer ACP tool `client_edit_file`. It's discouraged to use `apply_patch`, `pycharm_execute_terminal_command` and python's `file.write` because their formatting is hard for user to inspect. 
You can use `sed` or `head` for file segmentation. But if you don't know the exact position, you can cat the whole file, or identify it first using grep. Do not use sed to "nudge" along the file because the user may get frustrated. You can also combine multiple commands into one to save turns and tokens.
You can use MCP or `python.read` to read out-of-scope files.
Also prefer to use MarkDown instead of LaTex in your answer, because LaTex have proble rendering in PyCharm.
You can use git stash, commit and branch. But those are quite powerful moves so always clarify your intent then ask for permit. 

# Examples
## Example for inspecting output HIP file
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
