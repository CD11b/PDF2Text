from src.pdf2text.models import Bounds
from collections import Counter

class DocumentCache:

    def __init__(self):
        self._left_margins = set()
        self._font_size_bounds = set()
        self._font_names = set()
        self._start_y_ranges = set()
        self._row_separations = set()
        self._font_size_most_common = Counter()

    def update_cache(self, page_data):
        for column in page_data.columns:
            self._left_margins.add(column.heuristics.start_x.most_common)

        self._start_y_ranges.add(page_data.heuristics.start_y.distribution.range)
        self._row_separations.add(page_data.heuristics.row_separation)
        self._font_size_bounds.add(page_data.heuristics.font_size.bounds)
        self._font_size_most_common[page_data.heuristics.font_size.most_common] += 1
        self._font_names.add(page_data.heuristics.font_name.most_common)

    def left_margins(self) -> set[float]:
        return self._left_margins

    def start_y_ranges(self):
        return self._start_y_ranges

    def row_separations(self) -> set[float]:
        return self._row_separations

    def font_size_bounds(self) -> set[tuple[float, Bounds]]:
        return self._font_size_bounds

    def dominant_font_sizes(self) -> set[tuple[float, Bounds]]:
        return self._font_size_most_common

    def font_names(self) -> set[str]:
        return self._font_names
