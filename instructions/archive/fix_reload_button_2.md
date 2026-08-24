## Task
fix reload button error when i press the button:
```text
Traceback (most recent call last):
  File "Sop/python/reload", line 7, in <module>
  File "/opt/hfs21.0/houdini/python3.11libs/hou.py", line 19183, in cook
    return _hou.OpNode_cook(self, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
hou.OperationFailed: The attempted operation failed.
Error while cooking.
```

for more info about the reload button, refer to `./utilities.nodes._add_reload_button`


#### Steps
* read `instructions/general.md`.
* fix the bug
