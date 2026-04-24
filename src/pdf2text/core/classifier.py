from statistics import median
from src.pdf2text.models import *

class Classifier:

    def __init__(self, layout):
        self.layout = layout
        self._cache = {}

    @property
    def name(self):
        return self.__class__.__name__

    def _cached(self, key, compute_fn):
        if key not in self._cache:
            self._cache[key] = compute_fn()
        return self._cache[key]

    def _make_cache_key(self, features):
        return self.name, features

    def classify(self, context):
        features = self._extract_features(context)
        key = self._make_cache_key(features)
        return self._cached(key, lambda: self._compute(features))

class IndentationClassifier(Classifier):

    def _extract_features(self, context):
        line_start_x, previous_start_x, next_start_x = context
        return line_start_x, previous_start_x, next_start_x

    def _compute(self, features):

        line_start_x, previous_start_x, next_start_x = features

        if abs(line_start_x - self.layout.left_boundary) <= self.layout.coordinate_tolerance:
            return LineIndentation.NONE

        max_indent_size = self.layout.column.heuristics.start_x.upper_bound - self.layout.column.heuristics.start_x.most_common # Too aggressive. Must fix. Losing out on first sentence of paragraph
        adjusted_line_start_x = line_start_x - max_indent_size

        if previous_start_x is not None:
            if abs(line_start_x - previous_start_x) <= self.layout.coordinate_tolerance:
                return LineIndentation.INDENTED_BLOCK

            elif adjusted_line_start_x <= previous_start_x:
                return LineIndentation.INDENTED

        if next_start_x is not None:
            if abs(line_start_x - next_start_x) <= self.layout.coordinate_tolerance:
                return LineIndentation.INDENTED_BLOCK

            elif adjusted_line_start_x <= next_start_x:
                return LineIndentation.INDENTED

        return LineIndentation.LARGE_INDENTATION

class PositionClassifier(Classifier):

    def _extract_features(self, context):
        line_start_y, previous_start_y, next_start_y = context
        return line_start_y, previous_start_y, next_start_y

    def _compute(self, features):

        line_start_y, previous_start_y, next_start_y = features

        start_y_upper_bound = self.layout.column.heuristics.row_separation

        close_to_previous_line = previous_start_y is not None and abs(line_start_y - previous_start_y) <= start_y_upper_bound
        close_to_next_line = next_start_y is not None and abs(line_start_y - next_start_y) <= start_y_upper_bound

        if close_to_previous_line:
            if close_to_next_line:
                return PositionInParagraph.MIDDLE
            else:
                return PositionInParagraph.END

        elif close_to_next_line:
            return PositionInParagraph.START

        else:
            return PositionInParagraph.SINGLE_LINE

class MarginClassifier(Classifier):

    def _extract_features(self, line_group):
        return line_group[0].start_x

    def _compute(self, features) -> MarginPosition:

        line_start = features

        if abs(line_start - self.layout.left_boundary) <= self.layout.coordinate_tolerance:
            return MarginPosition.AT

        if line_start in self.layout.document_cache.left_margins():
            return MarginPosition.AT

        if line_start < self.layout.left_boundary:
            return MarginPosition.BEFORE
        return MarginPosition.AFTER

class RegionClassifier(Classifier):

    def _extract_features(self, line_group):
        return line_group[0].start_y

    def _compute(self, features) -> VerticalRegion:

        line_start = features

        midway = (self.layout.bottom_boundary - self.layout.top_boundary) / 2 + self.layout.top_boundary

        if line_start < midway:
            if self.layout.has_default_top:
                if line_start <= self.layout.top_boundary + self.layout.page.heuristics.row_separation:
                    return VerticalRegion.HEADER

                for start_y_range in self.layout.document_cache.start_y_ranges():
                    for row_separation in self.layout.document_cache.row_separations():
                        if line_start <= start_y_range.minimum + row_separation:
                            return VerticalRegion.HEADER
            else:
                if line_start <= self.layout.top_boundary:
                    return VerticalRegion.HEADER

            return VerticalRegion.BODY

        else:
            if self.layout.has_default_bottom:
                if line_start >= self.layout.bottom_boundary - self.layout.page.heuristics.row_separation:
                    return VerticalRegion.FOOTER
                for start_y_range in self.layout.document_cache.start_y_ranges():
                    for row_separation in  self.layout.document_cache.row_separations():
                        if line_start <= start_y_range.maximum + row_separation:
                            return VerticalRegion.FOOTER
            else:
                if line_start >= self.layout.bottom_boundary:
                    return VerticalRegion.FOOTER

            return VerticalRegion.BODY

class CharacterCountClassifier(Classifier):

    def _extract_features(self, line_group):
        line_character_count = sum((line.character_count for line in line_group))
        return line_character_count

    def _compute(self, features) -> CharacterCount:

        line_character_count = features

        if line_character_count >= self.layout.page.heuristics.character_count.lower_bound:
            return CharacterCount.HIGH
        else:
            return CharacterCount.LOW

class FontNameClassifier(Classifier):

    def _extract_features(self, line_group):
        return line_group[0].font_name

    def _compute(self, features) -> FontName:

        line_font_name = features

        if line_font_name in self.layout.document_cache.font_names():
            return FontName.MAIN

        for font in self.layout.document_cache.font_names():
            if font in line_font_name:
                if "italic" in line_font_name.lower():
                    return FontName.MAIN_ITALIC
                elif "bold" in line_font_name.lower():
                    return FontName.MAIN_BOLD

        return FontName.OTHER

class FontSizeClassifier(Classifier):

    def _extract_features(self, line_group):
        line_font_size = median((line.font_size for line in line_group))
        return line_font_size

    def _compute(self, features) -> FontSize:

        line_font_size = features

        for bounds in self.layout.document_cache.font_size_bounds():
            if bounds.lower <= line_font_size <= bounds.upper:
                return FontSize.MAIN

        if line_font_size < self.layout.page.heuristics.font_size.lower_bound:
            return FontSize.SMALL
        else:
            return FontSize.LARGE
