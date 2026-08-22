from pathlib import Path
import textwrap

import hou
import main

OUTPUT_PATH = Path(__file__).with_name("test.hip")

OUTPUT_PATH.unlink(missing_ok=True)
hou.hipFile.save(str(OUTPUT_PATH)) # type: ignore

hou.setSessionModuleSource(textwrap.dedent("""
    from pathlib import Path
    import sys
    import hou

    hip_dir = str(Path(hou.hipFile.path()).resolve().parent)
    if hip_dir not in sys.path:
        sys.path.insert(0, hip_dir)
"""))

spider = main.build()
spider.displayNode().geometry()

hou.hipFile.save() # type: ignore
print(f"Saved {OUTPUT_PATH}")