from dataclasses import dataclass
from itertools import groupby
from src.pdf2text.models.lines import Span
from collections import defaultdict

@dataclass(slots=True)
class Spans:
    spans: tuple(list[Span])
    _rows: list | None = None
    _is_ocr: bool | None = None
    _horizontal_clusters: list | None = None

    def __iter__(self):
        return iter(self.spans)

    def __getitem__(self, item):
        return self.spans[item]

    def __len__(self):
        return len(self.spans)

    @property
    def rows(self):
        if self._rows is None:
            y_sorted_spans = sorted(self.spans, key=lambda span: span.start_y)
            self._rows = [sorted(y_group, key=lambda span: span.start_x)
                          for _, y_group in groupby(y_sorted_spans, key=lambda span: span.start_y)]


        return self._rows

    @property
    def is_ocr(self):
        if self._is_ocr is None:
            word_like = sum(" " not in span.text.strip() for span in self.spans)
            phrase_like = len(self.spans) - word_like
            self._is_ocr = word_like > phrase_like

        return self._is_ocr