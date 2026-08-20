from pathlib import Path

import hou

import main


OUTPUT_PATH = Path(__file__).with_name("test.hip")

# Houdini's generated stub incorrectly treats these module-level functions as instance methods.
# noinspection PyArgumentList
hou.hipFile.clear(suppress_save_prompt=True)

spider = main.build()
spider.displayNode().geometry()  # Force the generated SOP network to cook.

# noinspection PyArgumentList,PyTypeChecker
hou.hipFile.save(str(OUTPUT_PATH))
print(f"Saved {OUTPUT_PATH}")
