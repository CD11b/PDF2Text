from typing import Any, Generator
import os
import re
import unicodedata
from collections import Counter
import logging
import pandas as pd
import argparse
import sys
from itertools import tee, groupby

from pdf_reader import PDFReader
from output_writer import OutputWriter
from document_analysis import DocumentAnalysis
from styled_line import StyledLine
from heuristics import Bounds, Heuristics

os.environ["TESSDATA_PREFIX"] = "./training"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Log to console
        logging.FileHandler("pdf2text.log", mode='w', encoding='utf-8')  # Log to file
    ]
)

class Iterator:

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


class FilterText:

    BROKEN_WORD_PATTERN = re.compile(r'\w-\s*$')
    HYPHEN_END_PATTERN = re.compile(r'-\s*$')
    PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')

    def __init__(self, page):
        self.page = page

    def clean_page_numbers(self, filtered_lines) -> list:

        logging.debug(f"Cleaning page numbers")

        return [
            line for line in filtered_lines if not self.PAGE_NUMBER_PATTERN.fullmatch(line.text)
        ]


    def join_broken_sentences(self, filtered_lines) -> str:

        logging.debug(f"Joining broken sentences.")

        def merge_broken_lines(lines):

            line_iter = iter(lines)

            for line in line_iter:
                text = line.text

                while self.BROKEN_WORD_PATTERN.search(text):
                    try:
                        next_line = next(line_iter)
                        text = self.HYPHEN_END_PATTERN.sub('', text) + next_line.text.lstrip()
                    except StopIteration:
                        break

                yield text

        return " ".join(merge_broken_lines(filtered_lines))

    def normalize_unicode(self, text):
        compatability_mapped = unicodedata.normalize('NFKC', text)
        decomposed = unicodedata.normalize('NFD', compatability_mapped)

        # Step 2: Remove combining marks
        return ''.join(c for c in decomposed if not unicodedata.combining(c))

    def prioritized_pairs(self, hanging_open=None):

        pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}

        if hanging_open:
            yield hanging_open, pairs[hanging_open]
        for open_bracket, close_bracket in pairs.items():
            if open_bracket != hanging_open:
                yield open_bracket, close_bracket

    def partition_by_brackets(self, text, open_bracket, close_bracket):

        before_open, _, _ = text.partition(open_bracket)
        _, _, after_close = text.partition(close_bracket)

        return before_open, after_close


    def handle_hanging_bracket(self, text, open_bracket, close_bracket):

        before_open, after_close = self.partition_by_brackets(text, open_bracket, close_bracket)

        cleaned_text = after_close.lstrip()
        hanging_open = None

        logging.debug(f"Resolved hanging bracket: text={cleaned_text}")
        return cleaned_text, hanging_open

    def handle_hanging_close(self, before_open, after_close, close_bracket):

        before_typo, _, after_typo = before_open.partition(close_bracket)
        before_open = before_typo + after_typo
        _, _, after_close = after_close.partition(close_bracket)

        return ''.join([before_open.rstrip(), after_close])

    def handle_opening_bracket(self, text, open_b, close_b, lines_iter):

        hanging_open = None

        if close_b in text:
            logging.debug(f"Found open and close brackets in line: {text}")
            cleaned_text = self.clean_bracket(text, open_b, close_b)

        elif lines_iter.peek() and close_b in lines_iter.peek().text:
            next_line = next(lines_iter)
            combined = text + " " + next_line.text
            logging.debug(f"Found open and close brackets across consecutive lines: {text}, {next_line}")
            cleaned_text = self.clean_bracket(combined, open_b, close_b)

        else:
            cleaned_text, hanging_open = self.handle_multiline_bracket(text, lines_iter, open_b, close_b)

        return cleaned_text, hanging_open

    def handle_multiline_bracket(self, text, lines_iter, open_b, close_b):
        buffer_lines = [text]
        found_close = False

        for lookahead in lines_iter:
            buffer_lines.append(lookahead.text)
            if close_b in lookahead.text:
                found_close = True
                break

        if found_close:
            logging.debug(f"Found open and close brackets across multiple lines: {text} ... {buffer_lines[-1]}")
            block_text = "\n".join(buffer_lines)
            cleaned_text = self.clean_bracket(block_text, open_b, close_b)
            hanging_open = None
        else:
            logging.debug(f"Found hanging open bracket: {text}")
            hanging_open = open_b
            cleaned_text = text.partition(open_b)[0].rstrip()

        return cleaned_text, hanging_open

    def clean_bracket(self, text, open_bracket, close_bracket):

        before_open, after_close = self.partition_by_brackets(text, open_bracket, close_bracket)

        if close_bracket in before_open:  # Author typo: hanging close
            logging.warning(f"Cleaning [CASE: Author typo - Hanging Close]: line={text}")
            cleaned_text = self.handle_hanging_close(before_open, after_close, close_bracket)

        else:
            logging.debug(f"Cleaning [CASE: Brackets Closed on Same Line]: line={text}")
            cleaned_text = ''.join([before_open.rstrip(), after_close])

        return cleaned_text

    def clean_brackets(self, filtered_lines, hanging_open: str | None = None) -> tuple[list[StyledLine], str | None]:

        result = []
        lines_iter = Iterator(filtered_lines)

        for line in lines_iter:

            text = line.text
            for open_b, close_b in self.prioritized_pairs(hanging_open):
                line_cleaned = False
                while not line_cleaned:
                    if hanging_open and close_b in text:
                        logging.debug(f"Found closing bracket of hanging open: {line}")
                        cleaned_text, hanging_open = self.handle_hanging_bracket(text, open_b, close_b)

                    elif open_b in text:
                        cleaned_text, hanging_open = self.handle_opening_bracket(text, open_b, close_b, lines_iter)

                    else:
                        cleaned_text = text

                    if open_b not in cleaned_text:
                        line_cleaned = True
                    else:
                        text = cleaned_text

                text = cleaned_text

            cleaned_line = line.with_text(cleaned_text)
            result.append(cleaned_line)

        return result, hanging_open

    def add_paragraph_breaks(self, filtered_lines):

        result = []
        lines_iter = Iterator(filtered_lines)

        for line in lines_iter:
            text = line.text
            if not self.page.is_body_paragraph(line, lines_iter):
                new_line = line.with_text(text + "\n")
                result.append(new_line)
            else:
                result.append(line)

        return result

    @staticmethod
    def merge_line(line_group):

        return StyledLine(text=' '.join(line.text for line in line_group if line.text.strip()),
                          font_size=pd.Series([line.font_size for line in line_group]).mean(),
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

    def filter_title_font(self, line_group, result):
        current_line = []
        if self.page.ocr:
            if self.page.ocr_is_title_font(line_group):
                FilterText.skip_group(line_group, case="Title Font")
            else:
                FilterText.collect_group(line_group, result, case="OCR - Misrecognized Title Font")
        else:
            FilterText.skip_group(line_group, case="Title Font")


    def filter_by_font(self, line_group, result):

        if self.page.is_dominant_font(line_group):
            FilterText.collect_group(line_group, result, case=f"Outside Indent Bounds - Indented Line is Dominant Font")
        else:
            FilterText.skip_group(line_group, case="Unhandled Uncommon Font", unhandled=True)


    def filter_indented_lines(self, line_group, groups_iter, result):


        if self.page.is_continued_indented_paragraph(line_group, result):

            if self.page.is_last_line(line_group):
                FilterText.collect_group(line_group, result, case="Last Line is Continued Indented Paragraph")
            elif self.page.is_body_paragraph(line_group, groups_iter):
                FilterText.collect_group(line_group, result, case="Indented Body Paragraph")
            elif self.page.is_body_paragraph(result[-1], line_group):
                FilterText.collect_group(line_group, result, case="Last line of Indented Body Paragraph")
            else:
                FilterText.skip_group(line_group, case="Continued Indent - Unhandled Indented Line", unhandled=True)

        elif self.page.is_indented_paragraph(line_group):
            if self.page.is_title_font(line_group):
                self.filter_title_font(line_group, result)
            else:
                FilterText.collect_group(line_group, result, case="Indented Paragraph")

        elif self.page.ocr:
            if self.page.is_footer_region(line_group):
                FilterText.skip_group(line_group, case="Indented Line @ Footer")
            elif self.page.is_continuous_line(line_group):
                FilterText.collect_group(line_group, result, case="OCR - Indented Line Following Dominant Word Gap")
            else:
                FilterText.skip_group(line_group, case="OCR - Unhandled Indented Line", unhandled=True)

        else:
            if self.page.is_indented_paragraph(line_group, whole_document=True):
                FilterText.collect_group(line_group, result, case="Whole Document - Indented Paragraph")
            else:
                FilterText.skip_group(line_group, case="Unhandled Indented Line", unhandled=True)

    def filter_by_boundaries(self):

        result = []
        groups_iter = Iterator(self.page.line_groups)

        for line_group in groups_iter:

            if self.page.is_header_region():

                if self.page.is_before_left_margin(line_group):  # Header
                    if self.page.is_within_body_boundaries(line_group):  # OCR inaccuracy
                        FilterText.collect_group(line_group, result, case="OCR - Misrecognized Body Paragraph as Indented")
                    else:
                        FilterText.skip_group(line_group, case="Non-aligned Header")

                elif self.page.is_at_left_margin(line_group):  # Body start

                    if self.page.is_body_paragraph(line_group, groups_iter):
                        self.page.top_boundary = line_group[0].start_y
                        FilterText.collect_group(line_group, result, case="First Body Paragraph")

                    else: # Aligned header
                        FilterText.skip_group(line_group, case="Aligned Header")

                elif self.page.is_after_left_margin(line_group):  # Edge case: Indented main body

                    if self.page.is_within_body_boundaries(line_group, whole_document=True):
                        if self.page.is_title_font(line_group):
                            self.filter_title_font(line_group, result)
                        else:
                            FilterText.collect_group(line_group, result, case="Indented Main Body")
                    else:
                        FilterText.skip_group(line_group, case="Right-side Header")

                else:
                    if self.page.is_at_left_margin(line_group, whole_document=True):  # Body start
                        if self.page.is_body_paragraph(line_group, groups_iter):
                            self.page.top_boundary = line_group[0].start_y
                            FilterText.collect_group(line_group, result, case="First Body Paragraph")
                    else:
                        FilterText.skip_group(line_group, case="Unhandled Header", unhandled=True)

            elif self.page.is_footer_region(line_group):  # Very bottom

                if self.page.is_at_left_margin(line_group):  # Main body
                    if self.page.is_body_paragraph(line_group, groups_iter):
                        FilterText.collect_group(line_group, result, case="Body Paragraph @ Footer")
                    elif self.page.is_body_paragraph(result[-1], line_group):
                        FilterText.collect_group(line_group, result, case="Last line of Body Paragraph @ Footer")
                    elif self.page.is_last_line(line_group): # No real footer
                        self.filter_by_font(line_group, result)
                    else:
                        FilterText.skip_group(line_group, case="Unhandled Footer", unhandled=True)
                elif self.page.is_before_left_margin(line_group):
                    if self.page.is_within_body_boundaries(line_group):  # OCR inaccuracy
                        FilterText.collect_group(line_group, result, case="OCR - Misrecognized Body Paragraph as Outdented")
                    else:
                        FilterText.skip_group(line_group, case="Left-side footer")

                elif self.page.is_after_left_margin(line_group):
                    self.filter_indented_lines(line_group, groups_iter, result)
                else:
                    FilterText.skip_group(line_group, case="Unhandled Footer", unhandled=True)

            elif self.page.is_at_left_margin(line_group):  # Main body

                if self.page.is_title_font(line_group):
                    self.filter_title_font(line_group, result)
                else:
                    if self.page.is_dominant_font(line_group):
                        FilterText.collect_group(line_group, result, case="Main Body")
                    else:
                        FilterText.skip_group(line_group, case="Aligned title")

            elif self.page.is_in_order(line_group, result) is False:

                FilterText.skip_group(line_group, case="Text outside regular read-order")

            elif self.page.is_after_left_margin(line_group):  # Indented block

                if self.page.is_last_line(line_group):
                    FilterText.collect_group(line_group, result, case="Last Line is Continued Indent")
                else:
                    self.filter_indented_lines(line_group, groups_iter, result)

            elif self.page.is_before_left_margin(line_group):  # Left-side footer
                if self.page.is_within_body_boundaries(line_group): # OCR inaccuracy
                    FilterText.collect_group(line_group, result, case="OCR - Misrecognized Body Paragraph as Outdented")
                else:
                    FilterText.skip_group(line_group, case="Left-side footer")

            else:
                FilterText.skip_group(line_group, case="Entirely Unhandled", unhandled=True)

        return result


class Page:
    def __init__(self, document_heuristics):
        self.page_heuristics = None
        self.document_heuristics = document_heuristics
        self.ocr = None
        self.lines = None
        self.line_groups = None
        self.bottom_boundary = None
        self.top_boundary = None
        self.left_boundary = None

    def set_lines(self, lines):
        self.lines = lines

    def set_ocr(self):
        self.ocr = self.check_ocr()

    def check_ocr(self):
        if len(self.lines) == 0:
            return False

        words = 1
        phrases = 1

        for i, line in enumerate(self.lines):

            if line.text.strip() is None:
                continue
            elif " " not in line.text.strip():
                words += 1
            else:
                phrases += 1

        if words / phrases > 0.95:
            return True
        else:
            return False

    def group_lines_by_y_position(self) -> None:
        """Group consecutive lines that share the same Y position."""
        self.line_groups = [
            list(group)
            for _, group in groupby(self.lines, key=lambda line: line.start_y)
        ]

    def is_at_left_margin(self, line_group, whole_document: bool | None = None) -> bool:
        if whole_document:
            for page in self.document_heuristics.all_pages:
                if line_group[0].start_x == page.start_x.most_common:
                    return True
        return line_group[0].start_x == self.left_boundary

    def is_after_left_margin(self, line_group) -> bool:
        return line_group[0].start_x > self.left_boundary

    def is_before_left_margin(self, line_group) -> bool:
        return line_group[0].start_x < self.left_boundary

    def is_footer_region(self, line_group) -> bool:
        return line_group[0].start_y >= self.bottom_boundary - self.page_heuristics.start_y.lower_bound

    def is_header_region(self) -> bool:
        return self.top_boundary is None

    def is_continuous_line(self, line_group, groups_iter) -> bool:
        vertical_gap = groups_iter.peek()[0].start_y - line_group[0].start_y
        return self.page_heuristics.word_gaps.lower_bound <= vertical_gap <= self.page_heuristics.word_gaps.upper_bound

    def is_within_body_boundaries(self, line_group, whole_document: bool | None = None) -> bool:
        if whole_document:
            for page in self.document_heuristics.all_pages:
                if page.start_x.most_common < line_group[0].start_x <= page.start_x.upper_bound:
                    return True
        return self.page_heuristics.start_x.lower_bound <= line_group[0].start_x <= self.page_heuristics.start_x.upper_bound

    def is_indented_paragraph(self, line_group, whole_document: bool | None = None) -> bool:
        if whole_document:
            for page in self.document_heuristics.all_pages:
                if page.start_x.most_common < line_group[0].start_x <= page.start_x.upper_bound:
                    return True
        return self.page_heuristics.start_x.most_common < line_group[0].start_x <= self.page_heuristics.start_x.upper_bound

    def is_continued_indented_paragraph(self, line_group, filtered_lines):
        return line_group[0].start_x == filtered_lines[-1].start_x

    def get_vertical_gap(self, current: StyledLine | list[StyledLine],
                         next_item: StyledLine | list[StyledLine]) -> float:
        current_y = current.start_y if isinstance(current, StyledLine) else current[0].start_y
        next_y = next_item.start_y if isinstance(next_item, StyledLine) else next_item[0].start_y
        return next_y - current_y

    def is_body_paragraph(self, line_group, next_group):
        if isinstance(next_group, Iterator):
            next_group = next_group.peek()

        if next_group is None:
            return False

        gap = self.get_vertical_gap(line_group, next_group)
        return gap <= self.page_heuristics.start_y.upper_bound

    def is_dominant_font(self, line_group) -> bool:
        return self.page_heuristics.font_size.lower_bound <= line_group[0].font_size <= self.page_heuristics.font_size.upper_bound

    def is_title_font(self, line_group) -> bool:
        return line_group[0].font_size > self.page_heuristics.font_size.upper_bound

    def is_last_line(self, line_group) -> bool:
        return line_group is self.line_groups[-1]

    def is_in_order(self, line_group, filtered_lines):
        return line_group[0].start_y > filtered_lines[-1].start_y

    def ocr_is_title_font(self, line_group) -> bool:

        font_size = pd.Series([line.font_size for line in line_group]).mean()

        return font_size > self.page_heuristics.font_size.upper_bound

    def set_page_boundaries(self) -> None:

        self.left_boundary = self.page_heuristics.start_x.most_common
        self.bottom_boundary = self.page_heuristics.start_y.maximum

    def setup(self) -> None:

        self.set_ocr()
        page_heuristics = TextHeuristics(ocr=self.ocr)

        self.page_heuristics = page_heuristics.analyze(lines=self.lines)

        if self.ocr and self.page_heuristics.font_name.most_common != 'GlyphLessFont':
            self.ocr = False
            self.page_heuristics = page_heuristics.analyze(lines=self.lines)

        self.document_heuristics.add_page(self.page_heuristics)
        self.set_page_boundaries()
        self.group_lines_by_y_position()


class TextHeuristics:
    def __init__(self, ocr) -> None:
        self.threshold = None
        self.ocr = ocr

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

    def compute_bounds(self, data, threshold = None) -> tuple[float, float]:

        if threshold is None:
            threshold = self.threshold

        series = pd.Series(data)
        mean = series.mean()
        std = series.std()

        if std == 0 or pd.isna(std):
            return series.min(), series.max()

        z_scores = (series - mean) / std
        inlier_series = series[z_scores.abs() <= threshold]

        if inlier_series.empty:
            return series.min(), series.max()

        return inlier_series.min(), inlier_series.max()

    def compute_word_gaps(self, lines):

        gaps = []

        for _, group in groupby(lines, key=lambda line: line.start_y):
            group_lines = sorted(group, key=lambda line: line.start_x)

            for i in range(len(group_lines) - 1):
                gap = group_lines[i + 1].start_x - group_lines[i].end_x
                if gap > 0:
                    gaps.append(gap)

        return self.compute_bounds(gaps) if gaps else (0, 0)

    def compute_line_gaps(self, start_y_counter: Counter) -> tuple[Any, Any]:
        values = sorted(start_y_counter)
        differences = (
            abs(y2 - y1)
            for y1, y2 in zip(values, values[1:])
            for _ in range(start_y_counter[y1])
        )
        return self.compute_bounds(differences)

    def compute_indent_gaps(self, lines: list) -> tuple[Any, Any]:

        indents = [
            group["start_x"].min()
            for _, group in pd.DataFrame(lines).groupby("start_y")
        ]

        return self.compute_bounds(indents, threshold=2)


    def set_threshold(self) -> None:

        if self.ocr:
            self.threshold = 3.0
        else:
            self.threshold = 1.0

    def analyze(self, lines: list) -> Heuristics:

        counters = {
            attr: self.get_styling_counter(lines, attr)
            for attr in ['font_size', 'font_name', 'start_x', 'start_y', 'end_x']
        }

        most_common = {k: self.most_common_value(v) for k, v in counters.items()}

        self.set_threshold()

        font_sizes = [size for size, freq in counters['font_size'].items() for _ in range(freq)]
        font_bounds = self.compute_bounds(font_sizes)

        line_gaps = self.compute_line_gaps(counters['start_y'])

        indent_bounds = self.compute_indent_gaps(lines=lines)

        edge_gaps = [edge for edge, freq in counters['end_x'].items() for _ in range(freq)]
        edge_bounds = self.compute_bounds(edge_gaps)

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


class DocumentHeuristics:
    def __init__(self):
        self.document = None
        self.all_pages = []

    def add_page(self, page_heuristics):
        self.all_pages.append(page_heuristics)

    def compute_document_heuristics(self):
        all_keys = set().union(*(page.keys() for page in self.all_pages))

        self.document = {
            key: {
                subkey: list({
                    page[key][subkey]
                    for page in self.all_pages
                    if key in page and subkey in page[key]
                })
                for subkey in next(page[key].keys() for page in self.all_pages if key in page)
            }
            for key in all_keys
        }

def main():

    parser = argparse.ArgumentParser(description="Process a PDF file.")

    default_path = "./docs/butler.pdf"
    parser.add_argument("--input-path", nargs="?", default=default_path, help="Path to the PDF file")
    parser.add_argument("--page-start", type=int, nargs="?", help="Page to start reading")
    parser.add_argument("--page-end", type=int, nargs="?", help="Page to end reading")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")


    args = parser.parse_args()

    pdf_path = args.input_path
    page_start = args.page_start
    page_end = args.page_end
    logging.getLogger().setLevel(args.log_level.upper())

    if os.path.exists(pdf_path) and os.path.isfile(pdf_path):
        with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

            output_writer = OutputWriter()
            output_writer.set_output_path(pdf=pdf_reader.pdf, pdf_path=pdf_path)

            output_writer.write(mode="w")
            hanging_open = None

            document_heuristics = DocumentHeuristics()
            for page_blocks in pdf_reader.iter_pages(sort=False):

                page = Page(document_heuristics)

                lines = list(DocumentAnalysis.iter_pdf_styling_from_blocks(page_blocks=page_blocks))
                page.set_lines(lines)

                page.setup()
                filter_text = FilterText(page)

                page.filtered_lines = filter_text.filter_by_boundaries()
                page.filtered_lines = filter_text.clean_page_numbers(page.filtered_lines)
                page.filtered_lines, hanging_open = filter_text.clean_brackets(hanging_open=hanging_open, filtered_lines=page.filtered_lines)
                page.filtered_lines = filter_text.add_paragraph_breaks(filtered_lines=page.filtered_lines)
                page_text = filter_text.join_broken_sentences(filtered_lines=page.filtered_lines)

                output_writer.write(mode="a", text=f'{page_text}\n\n')

if __name__ == '__main__':
    main()