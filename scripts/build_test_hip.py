import sys
import textwrap
from pathlib import Path


def _find_project_root() -> Path:
    """Find the project root independently of the current working directory."""
    script_directory = Path(__file__).resolve().parent
    for directory in (script_directory, *script_directory.parents):
        if (directory / "pyproject.toml").is_file():
            return directory

    raise FileNotFoundError(f"Could not find project root above {script_directory}")

PROJECT_ROOT = _find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from spider_generator import main
from utilities.developing import save


def build() -> None:
    _set_session_module_source()
    spider = main.build()
    spider.displayNode().geometry()

def _set_session_module_source() -> None:
    """
    The default Houdini setup adds only the directory containing the .hip file.
    This method searches for project root and insert it.
    """
    project_root_literal = repr(str(PROJECT_ROOT))
    hou_source = textwrap.dedent(f"""
        from pathlib import Path
        import sys
        import hou

        hip_directory = Path(hou.hipFile.path()).resolve().parent
        embedded_root = Path({project_root_literal})
        candidates = (hip_directory, *hip_directory.parents, embedded_root)
        source_root = next(
            (directory for directory in candidates if (directory / "pyproject.toml").is_file()),
            embedded_root,
        )

        source_root = str(source_root)
        if source_root not in sys.path:
            sys.path.insert(0, source_root)
    """)
    import hou

    hou.setSessionModuleSource(hou_source)


def _find_test_output_path() -> Path:
    test_directory = PROJECT_ROOT / "test"
    test_directory.mkdir(exist_ok=True)
    return test_directory / "test.hip"

if __name__ == "__main__":
    output_path = _find_test_output_path()
    save(output_path, build)
