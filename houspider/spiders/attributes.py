from enum import StrEnum, auto

from ..helper import affix_id


class ID(StrEnum):
    CEPHAPEDICELUPPER = auto()
    CEPHAPEDICELLOWER = auto()
    CEPHAPEDICELRIGHT = auto()
    CEPHAPEDICELLEFT = auto()


def cephapedicelupper(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELUPPER, *i)


def cephapedicellower(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELLOWER, *i)


def cephapedicelright(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELRIGHT, *i)


def cephapedicelleft(*i: int | str) -> str:
    return affix_id(ID.CEPHAPEDICELLEFT, *i)
