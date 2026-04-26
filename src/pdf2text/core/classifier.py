from statistics import median
from src.pdf2text.models import *

class Classifier:

    def __init__(self, page, column, document_cache):
        self.column = column
        self.document_cache = document_cache
        self._cache = {}

        self.bottom_boundary = page.heuristics.start_y.maximum
        self.left_boundary = column.heuristics.start_x.most_common
        self.top_boundary = page.heuristics.start_y.minimum
        self.coordinate_tolerance = page.heuristics.gaps.within_rows.upper if page.ocr else 0.0
        self.column_count = page.column_count

    @property
    def name(self):
        return self.__class__.__name__

    def _extract_features(self, context):
        """Override in subclasses."""
        raise NotImplementedError

    def _compute(self, features):
        """Override in subclasses."""
        raise NotImplementedError

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

class SplitSpanClassifier(Classifier):

    def _extract_features(self, context):
        line_start_y, line_end_x, next_group = context
        next_start_x = next_group[0].start_x if next_group else None
        next_start_y = next_group[0].start_y if next_group else None

        return line_start_y, line_end_x, next_start_x, next_start_y


    def _compute(self, features):
        line_start_y, line_end_x, next_start_x, next_start_y = features

        if self.coordinate_tolerance == 0.0: # For efficiency
            return False

        if line_start_y != next_start_y:
            return False

        indent_gap = next_start_x - line_end_x
        return self.column.heuristics.gaps.within_rows.lower <= indent_gap <= self.column.heuristics.gaps.within_rows.upper


class IndentationClassifier(Classifier):

    def _extract_features(self, context):
        line_start_x, previous_group, next_group = context
        previous_start_x = previous_group.line.start_x if previous_group else None
        next_start_x = next_group[0].start_x if next_group else None

        return line_start_x, previous_start_x, next_start_x

    def _compute(self, features):

        line_start_x, previous_start_x, next_start_x = features

        if abs(line_start_x - self.left_boundary) <= self.coordinate_tolerance:
            return LineIndentation.NONE

        max_indent_size = self.column.heuristics.start_x.upper_bound - self.column.heuristics.start_x.most_common
        adjusted_line_start_x = line_start_x - max_indent_size

        if previous_start_x is not None:
            if abs(line_start_x - previous_start_x) <= self.coordinate_tolerance:
                return LineIndentation.INDENTED_BLOCK

            elif adjusted_line_start_x <= previous_start_x:
                return LineIndentation.INDENTED

        if next_start_x is not None:
            if abs(line_start_x - next_start_x) <= self.coordinate_tolerance:
                return LineIndentation.INDENTED_BLOCK

            elif adjusted_line_start_x <= next_start_x:
                return LineIndentation.INDENTED

        return LineIndentation.LARGE_INDENTATION

class PositionClassifier(Classifier):

    def _extract_features(self, context):
        line_start_y, previous_group, next_group = context
        previous_start_y = previous_group.line.start_y if previous_group else None
        next_start_y = next_group[0].start_y if next_group else None

        return line_start_y, previous_start_y, next_start_y

    def _compute(self, features):

        line_start_y, previous_start_y, next_start_y = features

        start_y_upper_bound = self.column.heuristics.row_separation

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

        if abs(line_start - self.left_boundary) <= self.coordinate_tolerance:
            return MarginPosition.AT

        if line_start in self.document_cache.left_margins():
            return MarginPosition.AT

        if line_start < self.left_boundary:
            return MarginPosition.BEFORE
        return MarginPosition.AFTER

class RegionClassifier(Classifier):

    def _extract_features(self, line_group):
        return line_group[0].start_y

    def _compute(self, features) -> VerticalRegion:

        line_start = features

        midway = (self.bottom_boundary - self.top_boundary) / 2 + self.top_boundary

        if line_start < midway:
            if line_start <= self.top_boundary + self.column.heuristics.row_separation:
                return VerticalRegion.HEADER

            for start_y_range in self.document_cache.start_y_ranges():
                for row_separation in self.document_cache.row_separations():
                    if line_start <= start_y_range.minimum + row_separation:
                        return VerticalRegion.HEADER

        else:
            if line_start >= self.bottom_boundary - self.column.heuristics.row_separation:
                return VerticalRegion.FOOTER
            for start_y_range in self.document_cache.start_y_ranges():
                for row_separation in  self.document_cache.row_separations():
                    if line_start <= start_y_range.maximum + row_separation:
                        return VerticalRegion.FOOTER


        return VerticalRegion.BODY

class CharacterCountClassifier(Classifier):

    def _extract_features(self, line_group):
        line_character_count = sum((line.character_count for line in line_group))
        return line_character_count

    def _compute(self, features) -> CharacterCount:

        line_character_count = features

        if line_character_count >= self.column.heuristics.character_count.lower_bound:
            return CharacterCount.HIGH
        else:
            return CharacterCount.LOW

class FontNameClassifier(Classifier):

    def _extract_features(self, line_group):
        return line_group[0].font_name

    def _compute(self, features) -> FontName:

        line_font_name = features

        if line_font_name in self.document_cache.font_names():
            return FontName.MAIN

        for font in self.document_cache.font_names():
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

        if line_font_size == self.document_cache.dominant_font_sizes().most_common(1)[0][0]:
            return FontSize.MAIN_DOCUMENT
        elif line_font_size == self.column.heuristics.font_size.most_common:
            return FontSize.MAIN_PAGE
        elif line_font_size in self.document_cache.dominant_font_sizes():
            return FontSize.MAIN_ELSEWHERE
        else:
            for bounds in self.document_cache.font_size_bounds():
                if bounds.lower <= line_font_size <= bounds.upper:
                    return FontSize.IN_RANGE_ELSEWHERE

            if line_font_size < self.column.heuristics.font_size.lower_bound:
                return FontSize.SMALL
            else:
                return FontSize.LARGE

class TextContentClassifier(Classifier):

    def _extract_features(self, context):
        line_group, previous_group, next_group = context

        current_text = ' '.join(line.text for line in line_group if line.text.strip())
        previous_text = previous_group.line.text if previous_group else ""
        next_text = ' '.join(line.text for line in next_group if line.text.strip()) if next_group else ""

        return current_text, previous_text, next_text

    def _compute(self, features) -> FontSize:

        current_text, previous_text, next_text = features
        nearby_text = previous_text.lower() + next_text.lower()

        if "http" in current_text.lower():
            if "doi" in current_text.lower():
                return TextContent.URL_DOI
            return TextContent.URL
        elif "http" in nearby_text:
            if "doi" in nearby_text or "from" in nearby_text:
                return TextContent.REFERENCE
        elif "retrieved from" in current_text.lower() or "retrieved from" in nearby_text:
            return TextContent.REFERENCE




        return TextContent.BODY_TEXT
