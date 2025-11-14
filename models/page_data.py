from dataclasses import dataclass
from models.styled_line import StyledLine
from models.heuristics import Heuristics

@dataclass(frozen=True)
class ColumnData:
    line_groups: list[list[StyledLine]]
    heuristics: Heuristics

@dataclass(frozen=True)
class PageData:
    lines: list[StyledLine]
    heuristics: Heuristics
    columns: list[ColumnData]
    ocr: bool
