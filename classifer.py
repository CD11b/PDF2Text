from statistics import mean
from models import *

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

        start_y_upper_bound = self.layout.column.heuristics.start_y.upper_bound

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

        if line_start in self.layout.document.get_all_left_margins():
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
                if line_start <= self.layout.top_boundary + self.layout.page.heuristics.start_y.upper_bound:
                    return VerticalRegion.HEADER

                for top_boundary, lower_bound in self.layout.document.get_all_top_boundaries():
                    if line_start <= top_boundary + lower_bound:
                        return VerticalRegion.HEADER
            else:
                if line_start <= self.layout.top_boundary:
                    return VerticalRegion.HEADER

            return VerticalRegion.BODY

        else:
            if self.layout.has_default_bottom:
                if line_start >= self.layout.bottom_boundary - self.layout.page.heuristics.start_y.upper_bound:
                    return VerticalRegion.FOOTER
                for bottom_boundary, lower_bound in self.layout.document.get_all_bottom_boundaries():
                    if line_start >= bottom_boundary - lower_bound:
                        return VerticalRegion.FOOTER
            else:
                if line_start >= self.layout.bottom_boundary:
                    return VerticalRegion.FOOTER

            return VerticalRegion.BODY

class DensityClassifier(Classifier):

    def _extract_features(self, line_group):
        line_density = sum((line.character_density for line in line_group))
        return line_density

    def _compute(self, features) -> Density:

        line_density = features

        if line_density >= self.layout.page.heuristics.character_density.lower_bound:
            return Density.DENSE
        else:
            return Density.SPARSE

class FontNameClassifier(Classifier):

    def _extract_features(self, line_group):
        return line_group[0].font_name

    def _compute(self, features) -> FontName:

        line_font_name = features

        if line_font_name in self.layout.document.get_all_font_names():
            return FontName.MAIN
        return FontName.OTHER

class FontSizeClassifier(Classifier):

    def _extract_features(self, line_group):
        line_font_size = mean((line.font_size for line in line_group))
        return line_font_size

    def _compute(self, features) -> FontSize:

        line_font_size = features

        for most_common, lower_bound, upper_bound in self.layout.document.get_all_font_sizes():
            if lower_bound <= line_font_size <= upper_bound:
                return FontSize.MAIN

        if line_font_size < self.layout.page.heuristics.font_size.lower_bound:
            return FontSize.SMALL
        else:
            return FontSize.LARGE
