from src.pdf2text.core.text_heuristics import ColumnCountHeuristic
from src.pdf2text.models import Spans, LayoutProfile, ColumnLayout, PageLayout

import logging

logger = logging.getLogger(__name__)

class SpansAnalysis:

    def __init__(self, spans: Spans):
        self.spans = spans
        self._horizontal_clusters = None
        self._coordinate_tolerance = 0

    def compute_tolerance(self, heuristics):
        return heuristics.gaps.within_rows.upper if self.spans.ocr else 0.0

    def detect_columns(self, column_count_heuristic) -> int:
        column_count_heuristic.build_counter(self.spans, self._coordinate_tolerance)
        column_count_bounds = column_count_heuristic.compute_bounds(self.spans)
        return column_count_bounds.upper

    def create_columns(self, column_count_heuristic, column_count):
        columns = []
        start_x_columns = column_count_heuristic.compute_column_starts(self.spans, int(column_count))
        columned_groups = self.spans.group_into_columns(start_x_columns, self._coordinate_tolerance)

        for start_x in sorted(columned_groups.keys()):
            column_spans = Spans(columned_groups[start_x])
            column_heuristics = LayoutProfile.create(column_spans)
            column_line_groups = column_spans.cluster_spans_by_proximity(self._coordinate_tolerance)
            columns.append(ColumnLayout(column_line_groups, column_heuristics))

        return columns

    def analyze_page(self):

        columns = []
        page_heuristics = LayoutProfile.create(self.spans)
        self._coordinate_tolerance = self.compute_tolerance(page_heuristics)

        column_count_heuristic = ColumnCountHeuristic(self.spans.ocr)
        column_count = self.detect_columns(column_count_heuristic)

        if column_count > 1:
            columns = self.create_columns(column_count_heuristic, column_count)
        else:
            columns.append(ColumnLayout(self.spans.cluster_spans_by_proximity(self._coordinate_tolerance), page_heuristics))

        return PageLayout(page_heuristics, columns, self.spans.ocr)
