from enum import StrEnum, auto

from ..helper import affix_id


class ID(StrEnum):
    BASESTERNUM = auto()
    BASESTERNUMMIDDLE = auto()
    BASEMAXILLA = auto()
    BASEMAXILLAMEMBRANE = auto()
    BASEMOUTHMEMBRANE = auto()
    BASEEND = auto()


class Region(StrEnum):
    COXA = auto()
    LABIUM = auto()
    MAXILLA = auto()
    COXASOCKET = auto()
    COXAMEMBRANE = auto()
    LABIUMSOCKET = auto()
    LABIUMMEMBRANE = auto()
    MAXILLASOCKET = auto()
    MAXILLAMEMBRANE = auto()
    BASEBUFFERMEMBRANE = auto()
    BASEPEDICELMEMBRANE = auto()


def basesternum(*i: int | str) -> str:
    return affix_id(ID.BASESTERNUM, *i)


def basesternummiddle(*i: int | str) -> str:
    return affix_id(ID.BASESTERNUMMIDDLE, *i)


def basemaxilla(*i: int | str) -> str:
    return affix_id(ID.BASEMAXILLA, *i)


def basemaxillamembrane(*i: int | str) -> str:
    return affix_id(ID.BASEMAXILLAMEMBRANE, *i)


def basemouthmembrane(*i: int | str) -> str:
    return affix_id(ID.BASEMOUTHMEMBRANE, *i)


def baseend(*i: int | str) -> str:
    return affix_id(ID.BASEEND, *i)


def outer_loop_ids() -> tuple[str, ...]:
    return ID.BASESTERNUM, ID.BASEMAXILLA, ID.BASESTERNUMMIDDLE, ID.BASEEND
