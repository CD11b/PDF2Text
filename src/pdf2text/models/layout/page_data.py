from dataclasses import dataclass
from src.pdf2text.models.lines.styled_line import StyledLine
from src.pdf2text.models.layout.layoutprofile import LayoutProfile

from itertools import groupby

@dataclass(frozen=True, slots=True)
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
            rows = [sorted(y_group, key=lambda line: line.start_x)
                for _, y_group in groupby(y_sorted_lines, key=lambda line: line.start_y)]

            object.__setattr__(self, "_rows", rows)
        return self._rows

@dataclass(frozen=True, slots=True)
class ColumnData:
    lines: list[StyledLine]
    heuristics: LayoutProfile

@dataclass(frozen=True, slots=True)
class PageData:
    heuristics: LayoutProfile
    columns: list[ColumnData]
    ocr: bool

    @property
    def column_count(self):
        return len(self.columns)