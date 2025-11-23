from dataclasses import dataclass

@dataclass(frozen=True)
class Bounds:
    """Statistical bounds for a metric."""
    most_common: float
    minimum: float
    maximum: float
    lower_bound: float
    upper_bound: float

@dataclass(frozen=True)
class Heuristics:
    """Statistical analysis of page layout."""
    start_x: Bounds
    start_y: Bounds
    end_x: Bounds
    word_gaps: tuple[float, float] | None
    character_density: Bounds
    font_size: Bounds
    font_name: str