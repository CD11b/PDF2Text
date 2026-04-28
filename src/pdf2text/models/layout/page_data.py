from dataclasses import dataclass
from itertools import groupby
from src.pdf2text.models.lines import Span
from collections import defaultdict

@dataclass(frozen=True, slots=True)
class Spans:
    spans: list[Span]
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
            rows = [sorted(y_group, key=lambda span: span.start_x)
                          for _, y_group in groupby(y_sorted_spans, key=lambda span: span.start_y)]

            object.__setattr__(self, "_rows", rows)
        return self._rows

    @property
    def is_ocr(self):
        if self._is_ocr is None:
            word_like = sum(" " not in span.text.strip() for span in self.spans)
            phrase_like = len(self.spans) - word_like
            is_ocr = word_like > phrase_like

            object.__setattr__(self, "_is_ocr", is_ocr)
        return self._is_ocr

@dataclass(frozen=True, slots=True)
class HorizontalClusters:
    spans: list[list[Span]]

    def __iter__(self):
        return iter(self.spans)

    def __getitem__(self, index):
        return self.spans[index]

    @classmethod
    def create(cls, spans: Spans, coordinate_tolerance):
        horizontal_clusters = []
        for row in spans.rows:
            buffer = [row[0]]
            for previous, current in zip(row, row[1:]):
                if current.start_x - previous.end_x <= coordinate_tolerance:
                    buffer.append(current)
                else:
                    horizontal_clusters.append(buffer)
                    buffer = [current]
            horizontal_clusters.append(buffer)

        return cls(spans=horizontal_clusters)


@dataclass(frozen=True, slots=True)
class Column:
    spans: dict[int, list[Span]]

    def __iter__(self):
        return iter(self.spans)

    def __getitem__(self, key):
        return self.spans[key]

    def __len__(self):
        return len(self.spans)

    def keys(self):
        return self.spans.keys()

    def items(self):
        return self.spans.items()

    def values(self):
        return self.spans.values()

    @classmethod
    def create(cls, horizontal_clusters, start_x_columns):
        sorted_columns = sorted(start_x_columns)
        first_column = min(start_x_columns)
        spans_by_column = defaultdict(list)
        for cluster in horizontal_clusters:
            for span in cluster:

                if span.start_x < first_column:
                    spans_by_column[first_column].append(span)
                    continue

                for column_start_x in reversed(sorted_columns):
                    if span.start_x >= column_start_x:
                        spans_by_column[column_start_x].append(span)
                        break

        return cls(spans=spans_by_column)