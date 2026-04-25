from __future__ import annotations
from collections import Counter
from typing import Optional, Any
import logging

from src.pdf2text.models import FeatureStats, Bounds, Distribution, PageLines

logger = logging.getLogger(__name__)

class Heuristic:

    def __init__(self, ocr: bool, override_threshold: Optional[float] = None) -> None:
        self.ocr: bool = ocr
        self.override_threshold = override_threshold

        self._counter = None
        self._feature_stats = None
        self._distribution = None
        self._bounds = None

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def threshold(self) -> float:
        """Override if subclass needs a custom threshold."""

        _THRESHOLD: float = 1.0
        _OCR_THRESHOLD: float = 3.0

        if self.override_threshold is not None:
            threshold: float = self.override_threshold
        else:
            threshold = _OCR_THRESHOLD if self.ocr else _THRESHOLD

        return threshold

    @staticmethod
    def get_styling_counter(lines: PageLines, attribute: str) -> Counter[Any]:
        """Count occurrences of a given attribute across lines, weighted by text length."""

        counter: Counter[Any] = Counter()
        for line in lines:
            attr_value = getattr(line, attribute)
            counter[attr_value] += len(line.text)
        return counter

    def build_counter(self, lines: PageLines) -> Counter[Any]:
        """Override in subclasses."""
        raise NotImplementedError

    def _get_counter(self, lines: PageLines):
        if self._counter is None:
            self._counter = self.build_counter(lines)
        return self._counter

    def compute_distribution(self, lines: PageLines) -> Distribution:
        if self._distribution is None:
            counter = self._get_counter(lines)
            self._distribution = Distribution.create(counter)

        return self._distribution

    def compute_bounds(self, lines: PageLines) -> Bounds:
        if self._bounds is None:
            counter = self._get_counter(lines)
            self._bounds = Bounds.create(counter, self.threshold)

        return self._bounds

    def compute_feature_stats(self, lines: PageLines) -> FeatureStats:
        self._feature_stats = FeatureStats(self.compute_distribution(lines), self.compute_bounds(lines))
        return self._feature_stats

class FontSizeHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[Any]:
        return self.get_styling_counter(lines, "font_size")


class CharacterCountHeuristic(Heuristic):
    _THRESHOLD: float = 2.0

    @property
    def threshold(self) -> float:
        return self._THRESHOLD

    def build_counter(self, lines: PageLines)-> Counter[float]:

        counter: Counter[float] = Counter()
        for row in lines.rows:
            character_count = sum(line.character_count for line in row)
            if character_count > 0:
                counter[character_count] += 1

        return counter


class IndentHeuristic(Heuristic):
    _THRESHOLD = 2.0

    @property
    def threshold(self) -> float:
        return self._THRESHOLD

    def build_counter(self, lines: PageLines) -> Counter[float]:

        counter: Counter[float] = Counter()
        for row in lines.rows:
            indent = row[0].start_x
            counter[indent] += 1

        return counter

class GapBetweenRowsHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[float]:
        start_y_counter = self.get_styling_counter(lines, "start_y")

        counter: Counter[float] = Counter()
        values = sorted(start_y_counter)

        for y1, y2 in zip(values, values[1:]):
            gap = abs(y2 - y1)
            counter[gap] += start_y_counter[y1]

        return counter

class GapWithinRowsHeuristic(Heuristic):

    def build_counter(self, lines) -> Counter[float]:
        counter: Counter[float] = Counter()

        for row in lines.rows:
            for i in range(len(row) - 1):
                gap = row[i + 1].start_x - row[i].end_x
                if gap > 0:
                    counter[gap] += 1

        return counter

    def compute_bounds(self, lines: PageLines) -> Bounds:
        if self._bounds is None:
            if not self.ocr:
                self._bounds = Bounds(None, None)
            else:
                counter = self.build_counter(lines)
                self._bounds = Bounds.create(counter, self.threshold)

        return self._bounds

class EndXHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[float]:
        return self.get_styling_counter(lines, "end_x")

class StartXHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[float]:
        return self.get_styling_counter(lines, "start_x")

class StartYHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[float]:
        return self.get_styling_counter(lines, "start_y")

    def compute_bounds(self, lines: PageLines) -> Bounds:
        self._bounds = Bounds(None, None)
        return self._bounds

class FontNameHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[float]:
        return self.get_styling_counter(lines, "font_name")

    def compute_distribution(self, lines: PageLines) -> Distribution:
        counter = self.build_counter(lines)
        return Distribution.create(counter, discrete=True)

    def compute_bounds(self, lines: PageLines) -> Bounds:
        self._bounds = Bounds(None, None)
        return self._bounds

class ColumnCountHeuristic(Heuristic):

    def build_counter(self, lines: PageLines) -> Counter[float]:

        counter = Counter()
        for row in lines.rows:
            row_character_count = sum(line.character_count for line in row)
            counter[len(row)] += row_character_count

        return counter

    @staticmethod
    def compute_column_starts(lines: PageLines, number_columns) -> list:
        counter = Counter()
        for row in lines.rows:
            for line in row:
                counter[line.start_x] += line.character_count

        return sorted([column[0] for column in counter.most_common(number_columns)])