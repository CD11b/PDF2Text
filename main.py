import os
import re
import unicodedata
import logging
import argparse
from itertools import tee, groupby
from statistics import mean
from collections import defaultdict

from IO import PDFReader, OutputWriter
from models import StyledLine, PageData, Heuristics, ColumnData
from document_analysis import DocumentAnalysis
from logger_config import setup_logging
from text_heuristics import TextHeuristics

os.environ["TESSDATA_PREFIX"] = "./training"

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
            self.hanging_open = self.current_close
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

    @staticmethod
    def merge_line(line_group):

        return StyledLine(text=' '.join(line.text for line in line_group if line.text.strip()),
                          character_density=sum((line.character_density for line in line_group)),
                          font_size=mean((line.font_size for line in line_group)),
                          font_name=line_group[0].font_name,
                          start_x=line_group[0].start_x,
                          start_y=line_group[0].start_y,
                          end_x=line_group[-1].end_x)

    @staticmethod
    def skip_group(line_group, case: str, unhandled: bool | None=None):

        whole_line = FilterText.merge_line(line_group)

        if unhandled:
            logging.error(f"Skipped group [CASE: {case}]: {whole_line}")
        else:
            logging.info(f"Skipped group [CASE: {case}]: {whole_line}")

    @staticmethod
    def collect_group(line_group, result, case: str):

        whole_line = FilterText.merge_line(line_group)
        logging.debug(f"Collected group [CASE: {case}]: {whole_line}")

        result.append(whole_line)

    def filter_indented_lines(self, line_group, groups_iter, result):

        if len(result) > 0 and self.layout.is_continued_indented_paragraph(line_group, result):

            if self.layout.is_last_line(line_group):
                FilterText.collect_group(line_group, result, case="Last Line is Continued Indented Paragraph")
            elif self.layout.is_body_paragraph(line_group, groups_iter, result):
                FilterText.collect_group(line_group, result, case="Indented Body Paragraph")
            else:
                FilterText.skip_group(line_group, case="Continued Indent - Unhandled Indented Line", unhandled=True)

        elif self.layout.is_indented_paragraph(line_group):
            if self.layout.is_dominant_font_size(line_group):
                FilterText.collect_group(line_group, result, case="Indented Paragraph")
            else:
                FilterText.skip_group(line_group, case="Indented Line @ Footer")

        elif self.page.ocr:
            if self.layout.is_footer_region(line_group):
                FilterText.skip_group(line_group, case="Indented Line @ Footer")
            elif self.layout.is_continuous_line(line_group, groups_iter):
                FilterText.collect_group(line_group, result, case="OCR - Indented Line Following Dominant Word Gap")
            else:
                if self.layout.is_continuous_paragraph(line_group, groups_iter):
                    self._handle_continuous_paragraph(line_group, result)
                else:
                    FilterText.skip_group(line_group, case="OCR - Unhandled Indented Line", unhandled=True)

        else:
            if self.layout.is_indented_paragraph(line_group, whole_document=True):
                FilterText.collect_group(line_group, result, case="Whole Document - Indented Paragraph")
            else:
                FilterText.skip_group(line_group, case="Unhandled Indented Line", unhandled=True)

    def _handle_footer_region(self, line_group,groups_iter, result):

        if not self.layout.is_new_paragraph(line_group, result):
            if self.layout.is_paragraph_block(line_group, groups_iter, result):
                FilterText.collect_group(line_group, result, case="Body Paragraph")
            else:
                FilterText.skip_group(line_group, case="Unhandled footer", unhandled=True)

        elif self.layout.is_dense_line(line_group):
            FilterText.collect_group(line_group, result, case="Dense line @ Footer")
        else:
            FilterText.skip_group(line_group, case="Footer")

    def _handle_header_region(self, line_group, result):
        if not self.layout.is_new_paragraph(line_group, result):
            FilterText.collect_group(line_group, result, case="Body Paragraph")
        elif self.layout.is_dense_line(line_group):
            FilterText.collect_group(line_group, result, case="Dense line @ Header")
        else:
            FilterText.skip_group(line_group, case="Header")

    def _handle_new_paragraph(self, line_group, groups_iter, result):
        if self.layout.is_header_region(line_group):
            self._handle_header_region(line_group, result)
        elif self.layout.is_continuous_paragraph(line_group, groups_iter):
            self._handle_continuous_paragraph(line_group, result)
        else:
            FilterText.skip_group(line_group, case="Unhandled new paragraph", unhandled=True)

    def _handle_continuous_paragraph(self, line_group, result):

        if self.layout.is_dominant_font_size(line_group, whole_document=True):
            FilterText.collect_group(line_group, result, case="Continued Paragraph")
        else:
            FilterText.skip_group(line_group, case="Multi-line Title")

    def _handle_at_left_margin(self, line_group, groups_iter, result):

        if self.layout.is_footer_region(line_group):
            self._handle_footer_region(line_group, groups_iter, result)

        elif self.layout.is_new_paragraph(line_group, result):
            self._handle_new_paragraph(line_group, groups_iter, result)

        elif self.layout.is_continuous_paragraph(line_group, groups_iter):
            self._handle_continuous_paragraph(line_group, result)

        else:
            FilterText.collect_group(line_group, result, case="End of paragraph")

    def _handle_before_left_margin(self, line_group, groups_iter, result):

        if self.layout.is_header_region(line_group):
            self._handle_header_region(line_group, result)

        elif self.layout.is_footer_region(line_group):
            FilterText.skip_group(line_group, case="Footer before left margin", unhandled=True)

        else:
            FilterText.skip_group(line_group, case="Left-side")

    def _handle_after_left_margin(self, line_group, groups_iter, result):

        if self.layout.is_header_region(line_group):
            self._handle_header_region(line_group, result)

        elif self.layout.is_footer_region(line_group):
            self._handle_footer_region(line_group, groups_iter, result)

        else:
            self.filter_indented_lines(line_group, groups_iter, result)

    def _handle_left_margins(self, line_group, groups_iter, result):
        if self.layout.is_before_left_margin(line_group):
            self._handle_before_left_margin(line_group, groups_iter, result)

        elif self.layout.is_at_left_margin(line_group):

            self._handle_at_left_margin(line_group, groups_iter, result)

        elif self.layout.is_after_left_margin(line_group):  # Edge case: Indented main body
            self._handle_after_left_margin(line_group, groups_iter, result)

        else:
            if self.layout.is_at_left_margin(line_group, whole_document=True):  # Body start
                self._handle_at_left_margin(line_group, groups_iter, result)

            else:
                FilterText.skip_group(line_group, case="Unhandled Footer @ Left Margin", unhandled=True)

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

                    if not self.layout.is_in_order(line_group, buffer):
                        FilterText.skip_group(line_group, case="Text outside regular read-order")

                    else:
                        self._handle_left_margins(line_group, groups_iter, buffer)

            if buffer:
                buffer[-1] = buffer[-1].with_text(buffer[-1].text + "\n\n")
                result.extend(buffer)
        return result

class PageLayout:

    def __init__(self, page, column, document):
        self.page = page
        self.column = column
        self.document = document
        self.bottom_boundary = page.heuristics.start_y.maximum
        self.left_boundary = column.heuristics.start_x.most_common
        self.top_boundary = page.heuristics.start_y.minimum

    def set_top_boundary(self, top_boundary):
        self.top_boundary = top_boundary

    def set_bottom_boundary(self, bottom_boundary):
        self.bottom_boundary = bottom_boundary

    def is_at_left_margin(self, line_group, whole_document: bool | None = None) -> bool:
        line_start = line_group[0].start_x

        if self.page.ocr:
            if self.page.heuristics.start_x.lower_bound <= line_start <= self.left_boundary:
                return True

        if whole_document:
            for heuristic in self.document.get_all_left_margins():
                if line_start == heuristic:
                    return True
        return line_start == self.left_boundary

    def is_after_left_margin(self, line_group, whole_document: bool | None = None) -> bool:

        line_start = line_group[0].start_x
        if whole_document:
            for heuristic in self.document.get_all_left_margins():
                if line_start > heuristic:
                    return True
        return line_start > self.left_boundary

    def is_before_left_margin(self, line_group, whole_document: bool | None = None) -> bool:

        line_start = line_group[0].start_x
        if self.page.ocr:
            if line_start >= self.page.heuristics.start_x.lower_bound:
                return False

        if whole_document:
            for heuristic in self.document.get_all_left_margins():
                if line_start < heuristic:
                    return True
        return line_start < self.left_boundary

    def is_dense_line(self, line_group) -> bool:
        line_character_density = sum((line.character_density for line in line_group))
        return line_character_density >= self.page.heuristics.character_density.lower_bound

    def is_footer_region(self, line_group) -> bool:

        line_start = line_group[0].start_y
        midway_point = ((self.page.heuristics.start_y.maximum - self.page.heuristics.start_y.minimum) / 2 ) + self.page.heuristics.start_y.minimum
        if line_start <= midway_point:
            return False

        elif self.bottom_boundary == self.page.heuristics.start_y.maximum:

            if not line_start >= self.bottom_boundary - self.page.heuristics.start_y.upper_bound:
                for bottom_boundary, lower_bound in self.document.get_all_bottom_boundaries():
                    if line_start >= bottom_boundary - lower_bound:
                        return True
                return False
            else:
                return True

        else:

            return line_group[0].start_y >= self.bottom_boundary


    def is_header_region(self, line_group) -> bool:

        line_start = line_group[0].start_y
        midway_point = ((self.page.heuristics.start_y.maximum - self.page.heuristics.start_y.minimum) / 2 ) + self.page.heuristics.start_y.minimum
        if line_start >= midway_point:
            return False

        if self.top_boundary == self.page.heuristics.start_y.minimum:

            if not line_start <= self.top_boundary + self.page.heuristics.start_y.upper_bound:
                for top_boundary, lower_bound in self.document.get_all_top_boundaries():
                    if line_start <= top_boundary + lower_bound:
                        return True
                return False
            else:
                return True

        else:

            return line_group[0].start_y <= self.top_boundary

    def is_continuous_line(self, line_group, groups_iter) -> bool:
        next_group = groups_iter.peek()
        if next_group is None:
            return False

        vertical_gap = next_group[0].start_y - line_group[0].start_y
        return self.column.heuristics.word_gaps[0] <= vertical_gap <= self.column.heuristics.word_gaps[1]

    def is_indented_paragraph(self, line_group, whole_document: bool | None = None) -> bool:

        line_start = line_group[0].start_x
        if whole_document:
            for most_common, upper_bound in self.document.get_all_indents():
                if most_common < line_start <= upper_bound:
                    return True

        return self.column.heuristics.start_x.most_common < line_start <= self.column.heuristics.start_x.upper_bound

    def is_continued_indented_paragraph(self, line_group, filtered_lines):
        if self.page.ocr:
            return abs(line_group[0].start_x - filtered_lines[-1].start_x) <= self.page.heuristics.word_gaps[1]

        return line_group[0].start_x == filtered_lines[-1].start_x

    def is_paragraph_block(self, line_group, next_group = None, filtered_list = None):

        indent_size = self.column.heuristics.start_x.upper_bound - self.column.heuristics.start_x.most_common
        line_start_x = line_group[0].start_x - indent_size

        if next_group and isinstance(next_group, PeekableIterator):
            next_group = next_group.peek()

            if next_group:
                if line_start_x <= next_group[0].start_x:
                    return True

        if filtered_list:
            if len(filtered_list) > 0:
                return line_start_x <= filtered_list[-1].start_x
            else:
                return True

        else:
            return False


    def is_body_paragraph(self, line_group, next_group = None, filtered_list = None):
        if next_group and isinstance(next_group, PeekableIterator):
            next_group = next_group.peek()

            if next_group:
                gap = abs(line_group[0].start_y - next_group[0].start_y)
                if gap <= self.column.heuristics.start_y.upper_bound:
                    return True

        if filtered_list:
            if len(filtered_list) > 0:
                gap = line_group[0].start_y - filtered_list[-1].start_y
                return gap <= self.column.heuristics.start_y.upper_bound
            else:
                return True

        else:
            return False

    def is_new_paragraph(self, line_group, filtered_list):
        if self.is_body_paragraph(line_group=line_group, filtered_list=filtered_list):
            return False
        else:
            return True

    def is_continuous_paragraph(self, line_group, group_iter):
        return self.is_body_paragraph(line_group=line_group, next_group=group_iter)


    def is_dominant_font_size(self, line_group, whole_document: bool | None = None) -> bool:

        line_font_size = mean((line.font_size for line in line_group))
        if whole_document:
            for most_common, lower_bound, upper_bound in self.document.get_all_font_sizes():
                if line_font_size == most_common:
                    return True
                elif lower_bound <= line_font_size <= upper_bound:
                    return True

        return self.page.heuristics.font_size.lower_bound <= line_font_size <= self.page.heuristics.font_size.upper_bound


    def is_dominant_font_name(self, line_font_name, whole_document: bool | None = None) -> bool:

        if whole_document:
            for most_common in self.document.get_all_font_names():
                if line_font_name == most_common:
                    return True

        return line_font_name == self.page.heuristics.font_name

    def is_last_line(self, line_group) -> bool:
        return line_group is self.column.line_groups[-1]

    def is_in_order(self, line_group, filtered_lines):
        if not filtered_lines:
            return True
        return line_group[0].start_y + self.page.heuristics.start_y.lower_bound > filtered_lines[-1].start_y

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

                for start_x in reversed(sorted_columns):
                    if line.start_x >= start_x:
                        columned_groups[start_x].append(line)
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
        self.all_pages = []

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
        self.all_pages.append(page_data)
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
    # logger = logging.getLogger(__name__)

    if os.path.exists(pdf_path) and os.path.isfile(pdf_path):
        with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

            output_writer = OutputWriter()
            output_writer.set_output_path(pdf=pdf_reader.pdf, pdf_path=pdf_path)

            output_writer.write(mode="w")
            hanging_open = None

            document_heuristics = DocumentData()
            for page_blocks in pdf_reader.iter_pages(sort=True):

                lines = list(DocumentAnalysis.iter_pdf_styling_from_blocks(page_blocks=page_blocks))
                page_data = PageAnalyzer().analyze(lines)
                document_heuristics.add_page(page_data)
                filter_text = FilterText(page=page_data, document=document_heuristics)

                filtered_lines = filter_text.filter_by_boundaries()
                filtered_lines = CleanText.clean_page_numbers(filtered_lines)

                cleaned_brackets = BracketCleaner(hanging_open)
                filtered_lines = cleaned_brackets.clean_brackets(filtered_lines)
                hanging_open = cleaned_brackets.get_hanging_open()

                filtered_lines = filter_text.add_paragraph_breaks(filtered_lines=filtered_lines)
                page_text = CleanText.join_broken_sentences(filtered_lines=filtered_lines)

                page_text = CleanText.normalize_unicode(page_text)
                if page_data.ocr:
                    page_text = CleanText.correct_ocr_errors(page_text)
                output_writer.write(mode="a", text=f'{page_text}\n\n')

if __name__ == '__main__':
    main()