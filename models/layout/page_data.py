from dataclasses import dataclass
from models.lines.styled_line import StyledLine
from models.layout.layoutprofile import LayoutProfile

from itertools import groupby

@dataclass(slots=True)
class PageLines:
    lines: list
    _rows: list | None = None

    def __iter__(self):
        return iter(self.lines)

    def __getitem__(self, item):
        return self.lines[item]

    def __len__(self):
        return len(self.lines)

    @property
    def rows(self):
        if self._rows is None:
            y_sorted_lines = sorted(self.lines, key=lambda line: line.start_y)
            self._rows = [sorted(y_group, key=lambda line: line.start_x)
                          for _, y_group in groupby(y_sorted_lines, key=lambda line: line.start_y)]
        return self._rows

@dataclass(frozen=True)
class PageData:
    lines: list[StyledLine]
    heuristics: LayoutProfile
    columns: list[ColumnData]
    ocr: bool

@dataclass(frozen=True)
class ColumnData:
    lines: list[list[StyledLine]]
    heuristics: LayoutProfile
