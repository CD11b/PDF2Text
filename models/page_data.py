from dataclasses import dataclass
from models.styled_line import StyledLine
from models.heuristics import Heuristics

@dataclass(frozen=True)
class PageData:
    lines: list[StyledLine]
    line_groups: list[list[StyledLine]]
    heuristics: Heuristics
    ocr: bool
