from pathlib import Path

import main
from utilities.developing import save


def build() -> None:
    spider = main.build()
    spider.displayNode().geometry()


if __name__ == "__main__":
    output_path = Path(__file__).resolve().with_name("test.hip")
    save(output_path, build)
