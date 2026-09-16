from enum import StrEnum, auto
from typing import Callable

from ..helper import affix_id


class ID(StrEnum):
    CHELICERAEMEMBRANE = auto()
    CHELICERAESTARTMEMBRANESUPPORT = auto()
    CHELICERAESTART = auto()
    CHELICERAEMIDDLE = auto()
    CHELICERAEEND = auto()
    CHELICERAEINTERMEDIATE = auto()


class Region(StrEnum):
    CHELICERA = auto()
    CHELICERASOCKET = auto()
    CHELICERAMEMBRANE = auto()
    FANG = auto()


def cheliceraemembrane(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMEMBRANE, *i)


def cheliceraestartmembranesupport(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTARTMEMBRANESUPPORT, *i)


def cheliceraestart(*i: int | str) -> str:
    return affix_id(ID.CHELICERAESTART, *i)


def cheliceraemiddle(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEMIDDLE, *i)


def cheliceraeend(*i: int | str) -> str:
    return affix_id(ID.CHELICERAEEND, *i)


def cheliceraeintermediate(ratio: float | None = None, *i: int | str) -> str:
    if ratio is None:
        return affix_id(ID.CHELICERAEINTERMEDIATE)
    return affix_id(ID.CHELICERAEINTERMEDIATE, ratio, *i)


def bottom_middle(
    id_factory: Callable[..., str],
    *i: int | str | float,
    j: tuple[int | str | float, ...] | int | str | float = (),
) -> str:
    j_tuple = j if isinstance(j, tuple) else (j,)
    return id_factory(*j_tuple, "", "bottommiddle", *i)


def upper_middle(
    id_factory: Callable[..., str],
    *i: int | str | float,
    j: tuple[int | str | float, ...] | int | str | float = (),
) -> str:
    j_tuple = j if isinstance(j, tuple) else (j,)
    return id_factory(*j_tuple, "", "uppermiddle", *i)
