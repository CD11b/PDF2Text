from dataclasses import dataclass
from itertools import groupby
from src.pdf2text.models.lines import Span
from collections import defaultdict

@dataclass(slots=True)
class Spans:
    spans: tuple(list[Span])
    _rows: list | None = None
    _ocr: bool | None = None
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
    def ocr(self):
        if self._ocr is None:
            if len(self.spans) == 0:
                return False

            words = 1
            phrases = 1

            for line in self.spans:
                text = line.text.strip()
                if not text:
                    continue
                elif " " not in text:
                    words += 1
                else:
                    phrases += 1

            self._ocr = (words / (words + phrases)) > 0.95

        return self._ocr

    def cluster_spans_by_proximity(self, coordinate_tolerance):
        if self._horizontal_clusters is None:

            horizontal_clusters = []
            for row in self.rows:
                buffer = [row[0]]
                for previous, current in zip(row, row[1:]):
                    if current.start_x - previous.end_x <= coordinate_tolerance:
                        buffer.append(current)
                    else:
                        horizontal_clusters.append(buffer)
                        buffer = [current]
                horizontal_clusters.append(buffer)

            self._horizontal_clusters = horizontal_clusters

        return self._horizontal_clusters

    def group_into_columns(self, start_x_columns, coordinate_tolerance):

        sorted_columns = sorted(start_x_columns)
        first_column = min(start_x_columns)
        spans_by_column = defaultdict(list)
        for cluster in self.cluster_spans_by_proximity(coordinate_tolerance):
            for span in cluster:

                if span.start_x < first_column:
                    spans_by_column[first_column].append(span)
                    continue

                for column_start_x in reversed(sorted_columns):
                    if span.start_x >= column_start_x:
                        spans_by_column[column_start_x].append(span)
                        break

        return spans_by_column