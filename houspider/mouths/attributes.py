from enum import StrEnum, auto

from ..helper import affix_id


class ID(StrEnum):
    MOUTH = auto()


class Region(StrEnum):
    MOUTH = auto()


def mouth(*i: int | str) -> str:
    return affix_id(ID.MOUTH, *i)
