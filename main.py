import os
import re
import unicodedata
import logging
import argparse
from itertools import tee, groupby
from statistics import mean
from collections import defaultdict
from functools import wraps
from enum import Enum, auto

from IO import PDFReader, OutputWriter
from models import *

from rule_engine import RuleEngine
from rule_engine.indented import *
from rule_engine.footer import *
from rule_engine.header import *
from rule_engine.continuous_paragraph import *
from rule_engine.at_left_margin import *
from rule_engine.before_left_margin import *

from document_analysis import DocumentAnalysis
from logger_config import setup_logging
from text_heuristics import TextHeuristics
from line_collector import LineCollector

os.environ["TESSDATA_PREFIX"] = "./training"

logger = logging.getLogger(__name__)


class PeekableIterator:

    def __init__(self, iterable):
        self.iterator, self.peek_iterator = tee(iterable)
        self._advance_peek()

    def _advance_peek(self):
        try:
            self._peeked = next(self.peek_iterator)
            self._has_peek = True
        except StopIteration:
            self._has_peek = False

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self.iterator)
        self._advance_peek()
        return item

    def peek(self):
        return self._peeked if self._has_peek else None

    def has_next(self):
        return self._has_peek

class BracketCleaner:

    def __init__(self, hanging_open = None):
        self.current_open = None
        self.current_close = None
        self.hanging_open = hanging_open


    def get_hanging_open(self):
        return self.hanging_open

    def prioritized_pairs(self):

        pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}

        if self.hanging_open:
            self.current_open = self.hanging_open
            self.current_close = pairs[self.hanging_open]
            yield self.current_open, self.current_close
        for open_bracket, close_bracket in pairs.items():
            if open_bracket != self.hanging_open:
                self.current_open = open_bracket
                self.current_close = close_bracket
                yield self.current_open, self.current_close

    def partition_by_brackets(self, text):

        before_open, _, _ = text.partition(self.current_open)
        _, _, after_close = text.partition(self.current_close)

        return before_open, after_close

    def handle_hanging_bracket(self, text):

        before_open, after_close = self.partition_by_brackets(text)

        cleaned_text = after_close.lstrip()
        self.hanging_open = None

        logging.debug(f"Resolved hanging bracket: text={cleaned_text}")
        return cleaned_text

    def handle_hanging_close(self, before_open, after_close):

        before_typo, _, after_typo = before_open.partition(self.current_close)
        before_open = before_typo + after_typo
        _, _, after_close = after_close.partition(self.current_close)

        return ''.join([before_open.rstrip(), after_close])

    def handle_opening_bracket(self, text, lines_iter):

        if self.current_close in text:
            logging.debug(f"Found open and close brackets in line: {text}")
            cleaned_text = self.clean_and_join(text)

        elif lines_iter.peek() and self.current_close in lines_iter.peek().text:
            next_line = next(lines_iter)
            combined = text + " " + next_line.text
            logging.debug(f"Found open and close brackets across consecutive lines: {text}, {next_line}")
            cleaned_text = self.clean_and_join(combined)

        else:
            cleaned_text = self.handle_multiline_bracket(text, lines_iter)

        return cleaned_text

    def handle_multiline_bracket(self, text, lines_iter):
        buffer_lines = [text]
        found_close = False

        for lookahead in lines_iter:
            buffer_lines.append(lookahead.text)
            if self.current_close in lookahead.text:
                found_close = True
                break

        if found_close:
            logging.debug(f"Found open and close brackets across multiple lines: {text} ... {buffer_lines[-1]}")
            block_text = "\n".join(buffer_lines)
            cleaned_text = self.clean_and_join(block_text)
            self.hanging_open = None
        else:
            logging.debug(f"Found hanging open bracket: {text}")
            self.hanging_open = self.current_open
            cleaned_text = text.partition(self.current_open)[0].rstrip()

        return cleaned_text

    def clean_and_join(self, text):

        before_open, after_close = self.partition_by_brackets(text)

        if self.current_close in before_open:  # Author typo: hanging close
            logging.warning(f"Cleaning [CASE: Author typo - Hanging Close]: line={text}")
            cleaned_text = self.handle_hanging_close(before_open, after_close)

        else:
            logging.debug(f"Cleaning [CASE: Brackets Closed on Same Line]: line={text}")
            cleaned_text = ''.join([before_open.rstrip(), after_close])

        return cleaned_text

    def clean_brackets(self, filtered_lines) -> list[StyledLine]:

        result = []
        lines_iter = PeekableIterator(filtered_lines)

        for line in lines_iter:

            text = line.text
            for open_b, close_b in self.prioritized_pairs():
                line_cleaned = False
                while not line_cleaned:
                    if self.hanging_open and close_b in text:
                        logging.debug(f"Found closing bracket of hanging open: {line}")
                        cleaned_text = self.handle_hanging_bracket(text)

                    elif open_b in text:
                        cleaned_text = self.handle_opening_bracket(text, lines_iter)

                    else:
                        cleaned_text = text

                    if open_b not in cleaned_text:
                        line_cleaned = True
                    else:
                        text = cleaned_text

                text = cleaned_text

            cleaned_line = line.with_text(cleaned_text)
            result.append(cleaned_line)

        return result

class CleanText:

    BROKEN_WORD_PATTERN = re.compile(r'\w-\s*$')
    HYPHEN_END_PATTERN = re.compile(r'-\s*$')
    PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')
    COMMON_OCR_ERRORS = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "“": "\"",
        "”": "\"",
        "‘": "'",
        "’": "'",
        "|": "I"
    }

    @staticmethod
    def clean_page_numbers(filtered_lines) -> list:

        logging.debug(f"Cleaning page numbers")

        return [
            line for line in filtered_lines if not CleanText.PAGE_NUMBER_PATTERN.fullmatch(line.text)
        ]

    @staticmethod
    def join_broken_sentences(filtered_lines) -> str:

        logging.debug(f"Joining broken sentences.")

        def merge_broken_lines(lines):

            line_iter = iter(lines)

            for line in line_iter:
                text = line.text

                while CleanText.BROKEN_WORD_PATTERN.search(text):
                    try:
                        next_line = next(line_iter)
                        text = CleanText.HYPHEN_END_PATTERN.sub('', text) + next_line.text.lstrip()
                    except StopIteration:
                        break

                yield text

        return " ".join(merge_broken_lines(filtered_lines))

    @staticmethod
    def normalize_unicode(text):
        compatability_mapped = unicodedata.normalize('NFKC', text)
        decomposed = unicodedata.normalize('NFD', compatability_mapped)

        # Step 2: Remove combining marks
        return ''.join(c for c in decomposed if not unicodedata.combining(c))

    @staticmethod
    def correct_ocr_errors(text):
        for bad, good in CleanText.COMMON_OCR_ERRORS.items():
            text = text.replace(bad, good)

        return text


class FilterText:

    def __init__(self, page, document):
        self.page = page
        self.document = document
        self.layout = None
        self.collector = LineCollector()

        self.indented_rule_engine = RuleEngine([
            IndentedBlockLastLineRule(),
            IndentedBlockParagraphRule(),
            IndentedMainFontRule(),
            OCRFooterRule(),
            OCRContinuousLineRule(),
            FallbackIndentedRule()
        ])

        self.header_rule_engine = RuleEngine([
            BodyParagraphAtHeaderRegionRule(),
            DenseLineAtHeaderRegionRule(),
            FallbackHeaderRegionRule()
        ])

        self.footer_rule_engine = RuleEngine([
            FooterRegionBodyParagraphRule(),
            FooterRegionLoneIndentedTextRule(),
            FooterRegionDenseLineRule(),
            FallbackFooterRegionRule()
        ])

        self.continuous_paragraph_engine = RuleEngine([
            ContinuousParagraphMainFontRule(),
            ContinuousParagraphMultiLineTitleRule(),
            FallbackContinuousParagraphRule()
        ])

        self.at_left_margin_engine = RuleEngine([
            SingleLineHeaderAtLeftMarginRule(),
            EndParagraphAtLeftMarginRule(),
            FallbackAtLeftMarginRule()
        ])

        self.before_left_margin_engine = RuleEngine([
            FooterBeforeLeftMarginRule(),
            HeadingBeforeLeftMarginRule(),
            FallbackBeforeLeftMarginRule()
        ])


    def add_paragraph_breaks(self, filtered_lines):

        result = []

        for line in filtered_lines:
            text = line.text
            if self.layout.is_new_paragraph([line], filtered_list=result):
                new_line = line.with_text("\n" + text)
                result.append(new_line)
            else:
                result.append(line)

        return result

    def _handle_new_paragraph(self, ctx, groups_iter, result):

        if ctx.region is VerticalRegion.HEADER:
            engine = self.header_rule_engine

        elif ctx.position_in_paragraph is not PositionInParagraph.SINGLE_LINE:
            engine = self.continuous_paragraph_engine

        else:
            decision = Decision(Action.UNHANDLED, "Unhandled new paragraph", "_handle_new_paragraph")
            result.extend(self.collector.process(ctx.line_group, decision))
            return

        decision = engine.decide(ctx, self.layout, groups_iter)
        result.extend(self.collector.process(ctx.line_group, decision))

    def _handle_at_left_margin(self, ctx, groups_iter, result):

        if ctx.region is VerticalRegion.FOOTER:
            engine = self.footer_rule_engine

        elif ctx.position_in_paragraph is PositionInParagraph.START:
            self._handle_new_paragraph(ctx, groups_iter, result)
            return

        elif ctx.position_in_paragraph is PositionInParagraph.BODY:
            engine = self.continuous_paragraph_engine

        else:
            engine = self.at_left_margin_engine

        decision = engine.decide(ctx, self.layout, groups_iter)
        result.extend(self.collector.process(ctx.line_group, decision))

    def _handle_before_left_margin(self, ctx, groups_iter, result):

        if ctx.region is VerticalRegion.HEADER:
            engine = self.header_rule_engine

        else:
            engine = self.before_left_margin_engine

        decision = engine.decide(ctx, self.layout, groups_iter)
        result.extend(self.collector.process(ctx.line_group, decision))

    def _handle_after_left_margin(self, ctx, groups_iter, result):

        if ctx.region is VerticalRegion.HEADER:
            engine = self.header_rule_engine

        elif ctx.region is VerticalRegion.FOOTER:
            engine = self.footer_rule_engine

        else:
            engine = self.indented_rule_engine

        decision = engine.decide(ctx, self.layout, groups_iter)
        result.extend(self.collector.process(ctx.line_group, decision))

    def _handle_left_margins(self, ctx, groups_iter, result):

        if ctx.margin_position is MarginPosition.BEFORE:
            self._handle_before_left_margin(ctx, groups_iter, result)

        elif ctx.margin_position is MarginPosition.AT:

            self._handle_at_left_margin(ctx, groups_iter, result)

        elif ctx.margin_position is MarginPosition.AFTER:  # Edge case: Indented main body
            self._handle_after_left_margin(ctx, groups_iter, result)

        else:
            result.extend(self.collector.process(ctx.line_group, Decision(Action.UNHANDLED, "Unhandled Footer @ Left Margin", "_handle_left_margins")))

    def filter_by_boundaries(self):

        result = []


        logging.debug(f"Page: {self.page.heuristics}")
        # if remove_references and self.layout.is_reference_page():
        #     return []

        for column in self.page.columns:

            buffer = []
            self.layout = PageLayout(self.page, column, self.document)
            logging.debug(f"Column: {column.heuristics}")
            groups_iter = PeekableIterator(column.line_groups)
            for line_group in groups_iter:

                ctx = LineContext.create(self.layout, line_group, groups_iter, buffer)

                if not self.layout.is_in_order(line_group, buffer):
                    result.extend(self.collector.process(ctx.line_group, Decision(Action.SKIP, "Text outside regular read-order", "filter_by_boundaries")))
                else:
                    self._handle_left_margins(ctx, groups_iter, buffer)

            if buffer:
                buffer[-1] = buffer[-1].with_text(buffer[-1].text + "\n\n")
                result.extend(buffer)
        return result


def memoize_group_method(method):
    @wraps(method)
    def wrapper(self, line_group, *args, **kwargs):
        key = (method.__name__, id(line_group), args, tuple(kwargs.items()))
        if key not in self._cache:
            self._cache[key] = method(self, line_group, *args, **kwargs)
        return self._cache[key]
    return wrapper


class ParagraphType:
    def __init__(self, layout):
        self.layout = layout
        self.word_gap_upper_bound = self.layout.page.heuristics.word_gaps[1] if self.layout.page.ocr else None
        self._cache = {}

    @memoize_group_method
    def _at_left_margin(self, line_group):

        line_start_x = line_group[0].start_x

        if line_start_x == self.layout.left_boundary:
            return True
        elif self.layout.page.ocr:
            difference = abs(line_start_x - self.layout.left_boundary)
            if difference <= self.word_gap_upper_bound:
                return True

        return False

    def classify_indentation(self, line_group, group_iter, filtered_list):

        line_start_x = line_group[0].start_x

        if self._at_left_margin(line_group):
            return LineIndentation.NONE

        max_indent_size = self.layout.column.heuristics.start_x.upper_bound - self.layout.column.heuristics.start_x.most_common # Too aggressive. Must fix. Losing out on first sentence of paragraph
        adjusted_line_start_x = line_start_x - max_indent_size

        if len(filtered_list) > 0:
            previous_start_x = filtered_list[-1].start_x

            if self.layout.page.ocr:
                difference = abs(line_start_x - previous_start_x)
                if difference <= self.word_gap_upper_bound:
                    return LineIndentation.INDENTED_BLOCK

            if adjusted_line_start_x <= previous_start_x:
                return LineIndentation.INDENTED

        next_group = group_iter.peek()
        if next_group:
            next_start_x = next_group[0].start_x

            if line_start_x == next_start_x:
                return LineIndentation.INDENTED_BLOCK
            elif self.layout.page.ocr:
                difference = abs(line_start_x - next_start_x)
                if difference <= self.word_gap_upper_bound:
                    return LineIndentation.INDENTED_BLOCK
            elif adjusted_line_start_x <= next_start_x:
                return LineIndentation.INDENTED

        return LineIndentation.LARGE_INDENTATION

    @staticmethod
    def _is_close_to_last_line(line_start_y, filtered_list, start_y_upper_bound):
        if len(filtered_list) > 0:
            gap = abs(line_start_y - filtered_list[-1].start_y)
            if gap <= start_y_upper_bound:
                return True

        return False

    @staticmethod
    def _is_close_to_next_line(line_start_y, group_iter, start_y_upper_bound):
        next_group = group_iter.peek()
        if next_group:
            gap = abs(line_start_y - next_group[0].start_y)

            if gap <= start_y_upper_bound:
                return True

        return False

    def classify_position(self, line_group, group_iter, filtered_list):

        line_start_y = line_group[0].start_y
        start_y_upper_bound = self.layout.column.heuristics.start_y.upper_bound

        close_to_last_line = self._is_close_to_last_line(line_start_y, filtered_list, start_y_upper_bound)
        close_to_next_line = self._is_close_to_next_line(line_start_y, group_iter, start_y_upper_bound)

        if close_to_last_line:
            if close_to_next_line:
                return PositionInParagraph.BODY
            else:
                return PositionInParagraph.END

        elif close_to_next_line:
            return PositionInParagraph.START

        else:
            return PositionInParagraph.SINGLE_LINE

class LinePosition:

    def __init__(self, layout):
        self.layout = layout
        self.lower_bound = self.layout.page.heuristics.start_x.lower_bound
        self.left_boundary = self.layout.left_boundary
        self._cache = {}

    @memoize_group_method
    def classify_left_margin(self, line_group) -> MarginPosition:
        line_start = line_group[0].start_x

        if self.layout.page.ocr:
            if self.lower_bound <= line_start <= self.left_boundary:
                return MarginPosition.AT

        if line_start in self.layout.document.get_all_left_margins():
            return MarginPosition.AT

        if line_start < self.left_boundary:
            return MarginPosition.BEFORE
        elif line_start == self.left_boundary:
            return MarginPosition.AT
        else:
            return MarginPosition.AFTER


class LineRegion:

    def __init__(self, layout):
        self.layout = layout
        self._cache = {}

    @memoize_group_method
    def classify_vertical_region(self, line_group) -> VerticalRegion:
        line_start = line_group[0].start_y
        midway = (self.layout.bottom_boundary - self.layout.top_boundary) / 2 + self.layout.top_boundary

        if line_start < midway:
            if self.layout.top_boundary == self.layout.page.heuristics.start_y.minimum:
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
            if self.layout.bottom_boundary == self.layout.page.heuristics.start_y.maximum:
                if line_start >= self.layout.bottom_boundary - self.layout.page.heuristics.start_y.upper_bound:
                    return VerticalRegion.FOOTER
                for bottom_boundary, lower_bound in self.layout.document.get_all_bottom_boundaries():
                    if line_start >= bottom_boundary - lower_bound:
                        return VerticalRegion.FOOTER
            else:
                if line_start >= self.layout.bottom_boundary:
                    return VerticalRegion.FOOTER

            return VerticalRegion.BODY

class LineDensity:

    def __init__(self, layout):
        self.layout = layout
        self._cache = {}

    @memoize_group_method
    def classify_density(self, line_group) -> Density:
        line_density = sum((line.character_density for line in line_group))
        if line_density >= self.layout.page.heuristics.character_density.lower_bound:
            return Density.DENSE
        else:
            return Density.SPARSE

class LineFontName:

    def __init__(self, layout):
        self.layout = layout
        self._cache = {}

    @memoize_group_method
    def classify_font_name(self, line_group) -> FontName:

        for most_common in self.layout.document.get_all_font_names():
            if line_group[0].font_name == most_common:
                return FontName.MAIN

        return FontName.OTHER

class LineFontSize:

    def __init__(self, layout):
        self.layout = layout
        self._cache = {}

    @memoize_group_method
    def classify_font_size(self, line_group) -> FontSize:

        line_font_size = mean((line.font_size for line in line_group))

        for most_common, lower_bound, upper_bound in self.layout.document.get_all_font_sizes():
            if line_font_size == most_common:
                return FontSize.MAIN
            elif lower_bound <= line_font_size <= upper_bound:
                return FontSize.MAIN

        if line_font_size < self.layout.page.heuristics.font_size.lower_bound:
            return FontSize.SMALL
        else:
            return FontSize.LARGE


class PageLayout:

    def __init__(self, page, column, document):
        self.page = page
        self.column = column
        self.document = document
        self.bottom_boundary = page.heuristics.start_y.maximum
        self.left_boundary = column.heuristics.start_x.most_common
        self.top_boundary = page.heuristics.start_y.minimum
        self._cache = {}

        self.line_position = LinePosition(self)
        self.line_region = LineRegion(self)
        self.paragraph_type = ParagraphType(self)
        self.line_density = LineDensity(self)
        self.line_font_name = LineFontName(self)
        self.line_font_size = LineFontSize(self)

    @memoize_group_method
    def get_line_position(self, line_group) -> MarginPosition:
        return self.line_position.classify_left_margin(line_group)

    @memoize_group_method
    def get_line_region(self, line_group) -> VerticalRegion:
        return self.line_region.classify_vertical_region(line_group)

    @memoize_group_method
    def get_line_density(self, line_group) -> Density:
        return self.line_density.classify_density(line_group)

    @memoize_group_method
    def get_font_name(self, line_group) -> FontName:
        return self.line_font_name.classify_font_name(line_group)

    @memoize_group_method
    def get_font_size(self, line_group) -> FontSize:
        return self.line_font_size.classify_font_size(line_group)

    def get_position_in_paragraph(self, line_group, group_iter, filtered_list) -> PositionInParagraph:
        return self.paragraph_type.classify_position(line_group, group_iter, filtered_list)

    def get_line_indentation(self, line_group, group_iter, filtered_list) -> LineIndentation:
        return self.paragraph_type.classify_indentation(line_group, group_iter, filtered_list)

    def set_top_boundary(self, top_boundary):
        self.top_boundary = top_boundary

    def set_bottom_boundary(self, bottom_boundary):
        self.bottom_boundary = bottom_boundary

    @memoize_group_method
    def is_last_line(self, line_group) -> bool:
        return line_group is self.column.line_groups[-1]

    @memoize_group_method
    def is_indented_paragraph(self, line_group) -> bool:

        line_start = line_group[0].start_x
        for most_common, upper_bound in self.document.get_all_indents():
            if most_common < line_start <= upper_bound:
                return True

        return False

    def is_continuous_line(self, line_group, groups_iter) -> bool:
        next_group = groups_iter.peek()
        if next_group is None:
            return False

        if line_group[0].start_y != next_group[0].start_y:
            return False

        indent_gap = next_group[-1].end_x - line_group[0].start_x
        return self.column.heuristics.word_gaps[0] <= indent_gap <= self.column.heuristics.word_gaps[1]

    def is_in_order(self, line_group, filtered_lines):
        if not filtered_lines:
            return True
        return line_group[0].start_y + self.page.heuristics.start_y.lower_bound >= filtered_lines[-1].start_y

    def is_reference_page(self):
        current_line_count = len(self.page.lines)
        for page_line_count in self.document.get_all_line_counts():
            if current_line_count > page_line_count * 2:
                return True

        return False

class PageAnalyzer:

    @staticmethod
    def detect_ocr(lines):
        if len(lines) == 0:
            return False

        words = 1
        phrases = 1

        for line in lines:
            text = line.text.strip()
            if not text:
                continue
            elif " " not in text:
                words += 1
            else:
                phrases += 1

        return (words / (words + phrases)) > 0.95

    @staticmethod
    def group_line_groups_by_y(line_groups):

        groups = defaultdict(list)
        for group in line_groups:
            for line in group:
                groups[line.start_y].append(line)

        return groups

    @staticmethod
    def compute_column_count(line_groups_by_y):

        from collections import Counter

        counter = Counter()

        for group in line_groups_by_y.values():
            density = 0
            for line in group:
                density += line.character_density
            counter[len(group)] += density

        number_columns = counter.most_common(1)[0][0]
        return number_columns

    @staticmethod
    def compute_column_starts(line_groups_by_y, number_columns):

        from collections import Counter

        start_x_counter = Counter()
        for group in line_groups_by_y.values():
            for line in group:
                start_x_counter[line.start_x] += line.character_density

        start_x_columns = [column[0] for column in start_x_counter.most_common(number_columns)]

        return start_x_columns

    @staticmethod
    def sort_line_columns(line_groups, start_x_columns):

        sorted_columns = sorted(start_x_columns)
        first_column = min(start_x_columns)
        columned_groups = defaultdict(list)
        for group in line_groups:
            for line in group:

                if line.start_x < first_column:
                    columned_groups[first_column].append(line)
                    continue

                for column_start_x in reversed(sorted_columns):
                    if line.start_x >= column_start_x:
                        columned_groups[column_start_x].append(line)
                        break


        return columned_groups

    @staticmethod
    def group_consecutive_lines_by_y(lines):

        """Group consecutive lines that share the same Y position."""
        return [list(group)
                for _, group in groupby(lines, key=lambda line: line.start_y)
                ]

    def analyze(self, lines):

        ocr = self.detect_ocr(lines)

        heuristics = TextHeuristics(ocr).analyze(lines)

        if ocr and heuristics.font_name != 'GlyphLessFont':
            ocr = False
            heuristics = TextHeuristics(ocr).analyze(lines)

        line_groups = self.group_consecutive_lines_by_y(lines)

        columns = []
        if not ocr:

            line_groups_by_y = self.group_line_groups_by_y(line_groups)
            number_columns = self.compute_column_count(line_groups_by_y)
            start_x_columns = self.compute_column_starts(line_groups_by_y, number_columns)
            columned_groups = self.sort_line_columns(line_groups, start_x_columns)

            for start_x in sorted(columned_groups.keys()):
                column_lines = columned_groups[start_x]
                column_heuristics = TextHeuristics(ocr).analyze(column_lines)
                column_line_groups = self.group_consecutive_lines_by_y(column_lines)
                columns.append(ColumnData(column_line_groups, column_heuristics))
        else:
            columns.append(ColumnData(line_groups, heuristics))

        return PageData(lines, heuristics, columns, ocr)

class DocumentData:
    def __init__(self):
        self.document = None

        self._document_left_margins = set()
        self._document_body_boundaries = set()
        self._document_indents = set()
        self._document_font_sizes = set()
        self._document_font_names = set()
        self._document_bottom_boundary = set()
        self._document_top_boundary = set()
        self._document_line_counts = set()

    def update_cache(self, page_data):
        for column in page_data.columns:
            self._document_left_margins.add(column.heuristics.start_x.most_common)
            self._document_indents.add((column.heuristics.start_x.most_common, column.heuristics.start_x.upper_bound))
            self._document_body_boundaries.add((column.heuristics.start_x.lower_bound, column.heuristics.start_x.upper_bound))

        self._document_bottom_boundary.add((page_data.heuristics.start_y.maximum, page_data.heuristics.start_y.lower_bound))
        self._document_top_boundary.add((page_data.heuristics.start_y.minimum, page_data.heuristics.start_y.lower_bound))
        self._document_font_sizes.add((page_data.heuristics.font_size.most_common, page_data.heuristics.font_size.lower_bound, page_data.heuristics.font_size.upper_bound))
        self._document_font_names.add(page_data.heuristics.font_name)
        self._document_line_counts.add(len(page_data.lines))

    def add_page(self, page_data: PageData):
        self.update_cache(page_data)

    def get_all_left_margins(self) -> set[float]:
        return self._document_left_margins

    def get_all_bottom_boundaries(self) -> set[tuple[float, float]]:
        return self._document_bottom_boundary

    def get_all_top_boundaries(self) -> set[tuple[float, float]]:
        return self._document_top_boundary

    def get_all_indents(self) -> set[tuple[float, float]]:
        return self._document_indents

    def get_all_body_boundaries(self) -> set[tuple[float, float]]:
        return self._document_body_boundaries

    def get_all_font_sizes(self) -> set[tuple[float, float, float]]:
        return self._document_font_sizes

    def get_all_font_names(self) -> set[str]:
        return self._document_font_names

    def get_all_line_counts(self) -> set[int]:
        return self._document_line_counts

def main():

    parser = argparse.ArgumentParser(description="Process a PDF file.")

    default_path = "./docs/test_OCR.pdf"
    parser.add_argument("--input-path", nargs="?", default=default_path, help="Path to the PDF file")
    parser.add_argument("--page-start", type=int, nargs="?", help="Page to start reading")
    parser.add_argument("--page-end", type=int, nargs="?", help="Page to end reading")
    parser.add_argument("--log-level", default="DEBUG", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")
    parser.add_argument("--remove-references", action="store_true", help="Remove references from the document.")

    args = parser.parse_args()

    pdf_path = args.input_path
    page_start = args.page_start
    page_end = args.page_end
    remove_references = args.remove_references

    setup_logging(log_level=args.log_level)

    if os.path.exists(pdf_path) and os.path.isfile(pdf_path):
        with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

            output_writer = OutputWriter()
            output_writer.set_output_path(pdf=pdf_reader.pdf, pdf_path=pdf_path)

            output_writer.write(mode="w")
            hanging_open = None

            document_heuristics = DocumentData()
            for page_blocks in pdf_reader.iter_pages(sort=True):

                lines = list(DocumentAnalysis.iter_pdf_styling_from_blocks(page_blocks=page_blocks))
                if len(lines) == 0:
                    continue

                page_data = PageAnalyzer().analyze(lines)
                document_heuristics.add_page(page_data)
                filter_text = FilterText(page=page_data, document=document_heuristics)

                filtered_lines = filter_text.filter_by_boundaries()
                filtered_lines = CleanText.clean_page_numbers(filtered_lines)

                cleaned_brackets = BracketCleaner(hanging_open)
                filtered_lines = cleaned_brackets.clean_brackets(filtered_lines)
                hanging_open = cleaned_brackets.get_hanging_open()

                # filtered_lines = filter_text.add_paragraph_breaks(filtered_lines=filtered_lines)
                page_text = CleanText.join_broken_sentences(filtered_lines=filtered_lines)

                page_text = CleanText.normalize_unicode(page_text)
                if page_data.ocr:
                    page_text = CleanText.correct_ocr_errors(page_text)
                output_writer.write(mode="a", text=f'{page_text}\n\n')

if __name__ == '__main__':
    main()