from enum import StrEnum, auto

from ..helper import affix_id


class ID(StrEnum):
    STERNUMRIM = auto()
    STERNUMRIMINNER = auto()
    STERNUMMIDDLE = auto()
    STERNUMSPINE = auto()


def sternumrim(*i: int | str) -> str:
    return affix_id(ID.STERNUMRIM, *i)


def sternumriminner(*i: int | str) -> str:
    return affix_id(ID.STERNUMRIMINNER, *i)


def sternummiddle(*i: int | str) -> str:
    return affix_id(ID.STERNUMMIDDLE, *i)


def sternumspine(*i: int | str) -> str:
    return affix_id(ID.STERNUMSPINE, *i)


def outer_loop_ids() -> tuple[str, str]:
    return ID.STERNUMRIM, ID.STERNUMMIDDLE
