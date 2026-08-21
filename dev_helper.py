from pathlib import Path
import importlib
import sys
import hou


def reload_hip_modules() -> None:
    hip_dir = Path(hou.hipFile.path()).resolve().parent # type: ignore

    modules = []
    for module in list(sys.modules.values()):
        if getattr(module, "__name__", "") == "hou.session":
            continue
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            path = Path(module_file).resolve()
        except (OSError, RuntimeError):
            continue
        if path.is_relative_to(hip_dir):
            modules.append(module)
    for module in modules:
        importlib.reload(module)
