from pathlib import Path
import importlib
import sys

import hou


def reload_hip_modules() -> None:
    hip_dir = Path(hou.hipFile.path()).resolve().parent  # type: ignore

    modules = []
    seen = set()
    for name, module in list(sys.modules.items()):
        if module is None or id(module) in seen:
            continue
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue

        path = Path(module_file)
        # Critical:
        # Embedded/virtual modules such as PySide/Shiboken use relative
        # __file__ values. Never resolve those against our working directory.
        if not path.is_absolute():
            continue
        try:
            path = path.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not path.is_relative_to(hip_dir):
            continue

        spec = getattr(module, "__spec__", None)
        if spec is None:
            continue
        # Only accept the canonical sys.modules entry for this module.
        # importlib.reload() uses __spec__.name.
        if spec.name != name:
            continue
        # reload() requires the parent of a dotted module name to be an actual package with __path__.
        parent_name = name.rpartition(".")[0]
        if parent_name:
            parent = sys.modules.get(parent_name)
            if parent is None or not hasattr(parent, "__path__"):
                continue

        seen.add(id(module))
        modules.append((name, module))

    # Children first, then their packages.
    modules.sort(
        key=lambda item: item[0].count("."),
        reverse=True,
    )
    for name, module in modules:
        # Make sure nothing changed the module identity/spec while earlier modules were being reloaded.
        if sys.modules.get(name) is not module:
            continue
        spec = getattr(module, "__spec__", None)
        if spec is None or spec.name != name:
            continue
        importlib.reload(module)