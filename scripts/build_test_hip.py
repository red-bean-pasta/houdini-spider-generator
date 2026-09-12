from pathlib import Path

from spider_generator import main
from utilities.developing import save


SEARCH_DEPTH = 2


def build() -> None:
    spider = main.build()
    spider.displayNode().geometry()


def _find_test_output_path() -> Path:
    directory = Path(__file__).resolve().parent
    test_directory = None

    for _ in range(SEARCH_DEPTH):  # Search this directory and one parent directory.
        candidate = directory / "test"
        if test_directory is None and candidate.is_dir():
            test_directory = candidate

        if (directory / "pyproject.toml").is_file():
            if test_directory is None:
                test_directory = candidate
            test_directory.mkdir(exist_ok=True)
            return test_directory / "test.hip"

        directory = directory.parent

    raise FileNotFoundError(f"Could not find pyproject.toml within {SEARCH_DEPTH} depths")


if __name__ == "__main__":
    output_path = _find_test_output_path()
    save(output_path, build)
