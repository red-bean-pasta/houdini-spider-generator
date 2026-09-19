from enum import StrEnum, auto

from ..helper import affix_id


class ID(StrEnum):
    HEADCHELICERAE = auto()
    HEADFRONT = auto()
    HEADBACK = auto()
    HEADTOPMIDDLE = auto()
    HEADSIDEFRONT = auto()
    HEADSIDEMIDDLE = auto()
    HEADSIDEBACK = auto()
    HEADSUPPORT = auto()
    HEADBASESUPPORT = auto()
    HEADFRONTFLOAT = auto()
    HEADFRONTMID = auto()


class Region(StrEnum):
    HEADFRONTMAIN = auto()
    HEADFRONTCHEEK = auto()
    HEADTOP = auto()
    HEADBACK = auto()
    HEADSIDE = auto()


def headchelicerae(*i: int | str) -> str:
    return affix_id(ID.HEADCHELICERAE, *i)


def headfront(*i: int | str) -> str:
    return affix_id(ID.HEADFRONT, *i)


def headback(*i: int | str) -> str:
    return affix_id(ID.HEADBACK, *i)


def headtopmiddle(*i: int | str) -> str:
    return affix_id(ID.HEADTOPMIDDLE, *i)


def headsidefront(*i: int | str) -> str:
    return affix_id(ID.HEADSIDEFRONT, *i)


def headsidemiddle(*i: int | str) -> str:
    return affix_id(ID.HEADSIDEMIDDLE, *i)


def headsideback(*i: int | str) -> str:
    return affix_id(ID.HEADSIDEBACK, *i)


def headsupport(*i: int | str) -> str:
    return affix_id(ID.HEADSUPPORT, *i)


def headbasesupport(*i: int | str) -> str:
    return affix_id(f"{ID.HEADBASESUPPORT}_", *i)


def headfrontfloat(*i: int | str) -> str:
    return affix_id(ID.HEADFRONTFLOAT, *i)


def headfrontmid(*i: int | str) -> str:
    return affix_id(ID.HEADFRONTMID, *i)
