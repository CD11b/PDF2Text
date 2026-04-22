from __future__ import annotations
from collections import Counter
from typing import Optional, Any
from itertools import groupby
import logging

from models import StyledLine, FeatureStats, LayoutProfile, Bounds, Distribution

logger = logging.getLogger(__name__)

class Heuristic:

    def __init__(self, ocr: bool, override_threshold: Optional[float] = None) -> None:
        self.ocr: bool = ocr
        self.override_threshold = override_threshold

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
    def get_styling_counter(lines: list[StyledLine], attribute: str) -> Counter[Any]:
        """Count occurrences of a given attribute across lines, weighted by text length."""

        counter: Counter[Any] = Counter()
        for line in lines:
            attr_value = getattr(line, attribute)
            counter[attr_value] += len(line.text)
        return counter

    def build_counter(self, lines: list[StyledLine]) -> Counter[Any]:
        """Override in subclasses."""
        raise NotImplementedError

    def compute_distribution(self, lines: list[StyledLine]):
        counter = self.build_counter(lines)
        return Distribution.create(counter)

    def compute_bounds(self, lines: list[StyledLine]):
        counter = self.build_counter(lines)
        return Bounds.create(counter, self.threshold)

    def compute_feature_stats(self, lines: list[StyledLine]):
        counter = self.build_counter(lines)
        bounds = Bounds.create(counter, self.threshold)

        return FeatureStats(distribution=Distribution.create(counter),
                            bounds = bounds)

class FontSizeHeuristic(Heuristic):

    def build_counter(self, lines):
        return self.get_styling_counter(lines, "font_size")


class CharacterCountHeuristic(Heuristic):
    _THRESHOLD: float = 2.0

    @property
    def threshold(self) -> float:
        return self._THRESHOLD

    def build_counter(self, lines: list[StyledLine])-> Counter[float]:

        counter: Counter[float] = Counter()
        for _, group in groupby(lines, key=lambda line: line.start_y):
            group_lines = sorted(group, key=lambda line: line.start_x)
            character_count = sum(line.character_count for line in group_lines)
            if character_count > 0:
                counter[character_count] += 1

        return counter


class IndentHeuristic(Heuristic):
    _THRESHOLD = 2.0

    @property
    def threshold(self) -> float:
        return self._THRESHOLD

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:

        counter: Counter[float] = Counter()
        for _, group in groupby(lines, key=lambda line: line.start_y):
            group_lines = sorted(group, key=lambda line: line.start_x)
            indent = group_lines[0].start_x
            counter[indent] += 1

        return counter

class LineGapHeuristic(Heuristic):

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:
        start_y_counter = self.get_styling_counter(lines, "start_y")

        # if len(start_y_counter) < 2:
        #     logger.warning("Only one line detected on page.")
        #     return 0.0, 0.0

        counter: Counter[float] = Counter()
        values = sorted(start_y_counter)

        for y1, y2 in zip(values, values[1:]):
            gap = abs(y2 - y1)
            counter[gap] += start_y_counter[y1]

        return counter

class WordGapHeuristic(Heuristic):

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:
        counter: Counter[float] = Counter()

        for _, group in groupby(lines, key=lambda line: line.start_y):
            group_lines = sorted(group, key=lambda line: line.start_x)

            for i in range(len(group_lines) - 1):
                gap = group_lines[i + 1].start_x - group_lines[i].end_x
                if gap > 0:
                    counter[gap] += 1

        return counter

class EndXHeuristic(Heuristic):

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:
        return self.get_styling_counter(lines, "end_x")

class StartXHeuristic(Heuristic):

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:
        return self.get_styling_counter(lines, "start_x")

class StartYHeuristic(Heuristic):

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:
        return self.get_styling_counter(lines, "start_y")

class FontNameHeuristic(Heuristic):

    def build_counter(self, lines: list[StyledLine]) -> Counter[float]:
        return self.get_styling_counter(lines, "font_name")