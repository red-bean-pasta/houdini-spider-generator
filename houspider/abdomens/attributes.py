from enum import StrEnum, auto

from ..helper import affix_id


class ID(StrEnum):
    ABDOMENORIGIN = auto()
    ABDOMENEND = auto()
    ABDOMENHORIZONTALRIM = auto()
    ABDOMENVERTICALRIM = auto()
    ABDOMENSIDEUPPER = auto()
    ABDOMENSIDELOWER = auto()


class Region(StrEnum):
    ABDOMEN = auto()


def abdomenorigin() -> str:
    return affix_id(ID.ABDOMENORIGIN)


def abdomenend() -> str:
    return affix_id(ID.ABDOMENEND)


def abdomenhorizontalrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENHORIZONTALRIM, *i)


def abdomenverticalrim(*i: int | str) -> str:
    return affix_id(ID.ABDOMENVERTICALRIM, *i)


def abdomensideupper(*i: int | str) -> str:
    return affix_id(ID.ABDOMENSIDEUPPER, *i)


def abdomensidelower(*i: int | str) -> str:
    return affix_id(ID.ABDOMENSIDELOWER, *i)
