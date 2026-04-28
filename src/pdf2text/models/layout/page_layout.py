from dataclasses import dataclass
from src.pdf2text.models.lines.styled_line import Span
from src.pdf2text.models.layout.layout_profile import LayoutProfile

@dataclass(frozen=True, slots=True)
class ColumnLayout:
    spans: list[Span]
    heuristics: LayoutProfile

@dataclass(frozen=True, slots=True)
class PageLayout:
    heuristics: LayoutProfile
    columns: list[ColumnLayout]
    is_ocr: bool

    @property
    def column_count(self):
        return len(self.columns)