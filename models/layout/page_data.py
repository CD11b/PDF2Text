from dataclasses import dataclass
from models.lines.styled_line import StyledLine
from models.layout.layoutprofile import LayoutProfile

@dataclass(frozen=True)
class ColumnData:
    line_groups: list[list[StyledLine]]
    heuristics: LayoutProfile

@dataclass(frozen=True)
class PageData:
    lines: list[StyledLine]
    heuristics: LayoutProfile
    columns: list[ColumnData]
    ocr: bool
