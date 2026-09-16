from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Self


class Region(StrEnum):
    LEGSEGMENT = auto()
    LEGMEMBRANE = auto()


@dataclass
class LegParam:
    coxa_width_length: tuple[float, float]
    length_ratios: tuple[float, ...] | list[float]
    yaw_flex_specs: tuple[tuple[float, float], ...]

    tarsus_wedge_angle: float = 45.0

    coxa_trochanter_height_ratio: float = 0.63
    other_segment_height_ratio: float = 1.15
    spine_ratio: float = 0.5
    shrink_ratios: tuple[float, float] = (0.95, 0.875)
    support_loop_ratio: float = 0.015

    minimum_membrane: tuple[float, float] = (1.0, 5.0)

    def __post_init__(self) -> None:
        assert len(self.length_ratios) == len(self.yaw_flex_specs), (
            f"Length mismatch: length_ratios ({len(self.length_ratios)}) != yaw_flex_specs ({len(self.yaw_flex_specs)})"
        )

    @classmethod
    def from_specs(
        cls,
        coxa_width_length: tuple[float, float],
        length_ratios: tuple[float, ...] | list[float],
        max_segment_yaws: tuple[float, ...] | list[float],
        min_segment_flexes: tuple[float, ...] | list[float],
        **kwargs,
    ) -> Self:
        assert len(max_segment_yaws) == len(min_segment_flexes), (
            f"Spec mismatch: max_segment_yaws ({len(max_segment_yaws)}) != min_segment_flexes ({len(min_segment_flexes)})"
        )
        assert len(length_ratios) == len(max_segment_yaws), (
            f"Length mismatch: length_ratios ({len(length_ratios)}) != max_segment_yaws ({len(max_segment_yaws)})"
        )
        segment_specs = tuple(zip(max_segment_yaws, min_segment_flexes))
        return cls(
            coxa_width_length=coxa_width_length,
            length_ratios=length_ratios,
            yaw_flex_specs=segment_specs,
            **kwargs,
        )
