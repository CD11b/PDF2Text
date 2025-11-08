import numpy as np
from collections import Counter
from typing import Optional
from itertools import groupby
import logging

from styled_line import StyledLine
from heuristics import Bounds, Heuristics

logger = logging.getLogger(__name__)

class TextHeuristics:

    _NORMAL_THRESHOLD = 1.0
    _OCR_THRESHOLD = 3.0
    _INDENT_THRESHOLD = 2.0

    def __init__(self, ocr, override_threshold: Optional[float] = None) -> None:
        self.ocr = ocr
        if override_threshold is not None:
            self.threshold = override_threshold
        else:
            self.threshold = self._OCR_THRESHOLD if ocr else self._NORMAL_THRESHOLD

    @staticmethod
    def get_styling_counter(lines: list, attribute: str) -> Counter:

        counter = Counter()
        for line in lines:
            attr_value = getattr(line, attribute)
            counter[attr_value] += len(line.text)
        return counter

    @staticmethod
    def most_common_value(counter: Counter):

        return counter.most_common(1)[0][0] if counter else None

    def compute_bounds(self, data: Counter, threshold: Optional[float] = None) -> tuple[float, float]:

        if threshold is None:
            threshold = self.threshold

        values = np.array(list(data.keys()))
        weights = np.array(list(data.values()))

        mean = np.average(values, weights=weights)
        variance = np.average((values - mean) ** 2, weights=weights)
        std = np.sqrt(variance)

        if std == 0 or np.isnan(std):
            return values.min(), values.max()

        z_scores = np.abs((values - mean) / std)
        inliers = values[z_scores <= threshold]

        if len(inliers) == 0:
            return values.min(), values.max()

        return float(inliers.min()), float(inliers.max())

    def compute_word_gaps(self, lines: list[StyledLine]) -> tuple[float, float]:

        counter = Counter()
        for _, group in groupby(lines, key=lambda line: line.start_y):
            group_lines = sorted(group, key=lambda line: line.start_x)

            for i in range(len(group_lines) - 1):
                gap = group_lines[i + 1].start_x - group_lines[i].end_x
                if gap > 0:
                    counter[gap] += 1

        return self.compute_bounds(counter)

    def compute_line_gaps(self, start_y_counter: Counter) -> tuple[float, float]:

        if len(start_y_counter) < 2:
            logger.warning("Only one line detected on page. Line gaps may be misleading.")
            return 0.0, 0.0

        counter = Counter()
        values = sorted(start_y_counter)

        for y1, y2 in zip(values, values[1:]):
            gap = abs(y2 - y1)
            counter[gap] += start_y_counter[y1]

        return self.compute_bounds(counter)

    def compute_indent_gaps(self, lines: list) -> tuple[float, float]:

        counter = Counter()

        for _, group in groupby(lines, key=lambda line: line.start_y):

            group_lines = sorted(group, key=lambda line: line.start_x)
            indent = group_lines[0].start_x
            counter[indent] += 1

        return self.compute_bounds(counter, threshold=self._INDENT_THRESHOLD)

    def analyze(self, lines: list) -> Heuristics:

        logger.debug("Analyzing text heuristics.")

        counters = {
            attr: self.get_styling_counter(lines, attr)
            for attr in ['font_size', 'font_name', 'start_x', 'start_y', 'end_x']
        }

        most_common = {k: self.most_common_value(v) for k, v in counters.items()}

        font_bounds = self.compute_bounds(counters['font_size'])

        line_gaps = self.compute_line_gaps(counters['start_y'])

        indent_bounds = self.compute_indent_gaps(lines=lines)

        edge_bounds = self.compute_bounds(counters['end_x'])

        if self.ocr:
            word_gaps = self.compute_word_gaps(lines=lines)
        else:
            word_gaps = [None, None]

        return Heuristics(
            start_x=Bounds(
                most_common=most_common['start_x'],
                minimum=min(counters['start_x']),
                maximum=max(counters['start_x']),
                lower_bound=indent_bounds[0],
                upper_bound=indent_bounds[1]
            ),
            start_y=Bounds(
                most_common=most_common['start_y'],
                minimum=min(counters['start_y']),
                maximum=max(counters['start_y']),
                lower_bound=line_gaps[0],
                upper_bound=line_gaps[1]
            ),
            end_x=Bounds(
                most_common=most_common['end_x'],
                minimum=min(counters['end_x']),
                maximum=max(counters['end_x']),
                lower_bound=edge_bounds[0],
                upper_bound=edge_bounds[1]
            ),
            word_gaps=word_gaps,
            font_size=Bounds(
                most_common=most_common['font_size'],
                minimum=min(counters['font_size']),
                maximum=max(counters['font_size']),
                lower_bound=font_bounds[0],
                upper_bound=font_bounds[1]
            ),
            font_name=most_common['font_name']
        )