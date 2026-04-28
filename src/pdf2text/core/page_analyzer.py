from src.pdf2text.core.text_heuristics import ColumnCountHeuristic
from src.pdf2text.models import Spans, HorizontalClusters, Columns, LayoutProfile, ColumnLayout, PageLayout

import logging

logger = logging.getLogger(__name__)

class SpansAnalysis:

    def __init__(self, spans: Spans):
        self.spans = spans
        self._coordinate_tolerance = 0

    def compute_tolerance(self, heuristics):
        self._coordinate_tolerance = heuristics.gaps.within_rows.upper if self.spans.is_ocr else 0.0

    def detect_columns(self, column_count_heuristic) -> int:
        column_count_heuristic.build_counter(self.spans, self._coordinate_tolerance)
        column_count_bounds = column_count_heuristic.compute_bounds(self.spans)
        return column_count_bounds.upper

    def create_columns(self, horizontal_clusters, column_count_heuristic, column_count):
        result = []
        start_x_columns = column_count_heuristic.compute_column_starts(self.spans, int(column_count))
        columns = Columns.create(horizontal_clusters, start_x_columns)

        for start_x in sorted(columns.keys()):
            column_spans = Spans(columns[start_x])
            layout_profile = LayoutProfile.create(column_spans)
            column_horizontal_clusters = HorizontalClusters.create(column_spans, self._coordinate_tolerance)
            result.append(ColumnLayout(column_horizontal_clusters, layout_profile))

        return result

    def analyze_page(self):

        page_heuristics = LayoutProfile.create(self.spans)
        self.compute_tolerance(page_heuristics)

        column_count_heuristic = ColumnCountHeuristic(self.spans.is_ocr)
        column_count = self.detect_columns(column_count_heuristic)
        horizontal_clusters = HorizontalClusters.create(self.spans, self._coordinate_tolerance)

        if column_count > 1:
            columns = self.create_columns(horizontal_clusters, column_count_heuristic, column_count)
        else:
            columns = [ColumnLayout(horizontal_clusters, page_heuristics)]

        return PageLayout(page_heuristics, columns, self.spans.is_ocr)
