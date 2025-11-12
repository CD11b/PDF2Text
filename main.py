import os
import re
import unicodedata
import logging
import argparse
from itertools import tee, groupby
from statistics import mean

from IO import PDFReader, OutputWriter
from models import StyledLine, PageData, Heuristics
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


class CleanText:

    BROKEN_WORD_PATTERN = re.compile(r'\w-\s*$')
    HYPHEN_END_PATTERN = re.compile(r'-\s*$')
    PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')

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
    def prioritized_pairs(hanging_open=None):

        pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}

        if hanging_open:
            yield hanging_open, pairs[hanging_open]
        for open_bracket, close_bracket in pairs.items():
            if open_bracket != hanging_open:
                yield open_bracket, close_bracket

    @staticmethod
    def partition_by_brackets(text, open_bracket, close_bracket):

        before_open, _, _ = text.partition(open_bracket)
        _, _, after_close = text.partition(close_bracket)

        return before_open, after_close

    @staticmethod
    def handle_hanging_bracket(text, open_bracket, close_bracket):

        before_open, after_close = CleanText.partition_by_brackets(text, open_bracket, close_bracket)

        cleaned_text = after_close.lstrip()
        hanging_open = None

        logging.debug(f"Resolved hanging bracket: text={cleaned_text}")
        return cleaned_text, hanging_open

    @staticmethod
    def handle_hanging_close(before_open, after_close, close_bracket):

        before_typo, _, after_typo = before_open.partition(close_bracket)
        before_open = before_typo + after_typo
        _, _, after_close = after_close.partition(close_bracket)

        return ''.join([before_open.rstrip(), after_close])

    @staticmethod
    def handle_opening_bracket(text, open_b, close_b, lines_iter):

        hanging_open = None

        if close_b in text:
            logging.debug(f"Found open and close brackets in line: {text}")
            cleaned_text = CleanText.clean_bracket(text, open_b, close_b)

        elif lines_iter.peek() and close_b in lines_iter.peek().text:
            next_line = next(lines_iter)
            combined = text + " " + next_line.text
            logging.debug(f"Found open and close brackets across consecutive lines: {text}, {next_line}")
            cleaned_text = CleanText.clean_bracket(combined, open_b, close_b)

        else:
            cleaned_text, hanging_open = CleanText.handle_multiline_bracket(text, lines_iter, open_b, close_b)

        return cleaned_text, hanging_open

    @staticmethod
    def handle_multiline_bracket(text, lines_iter, open_b, close_b):
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
            cleaned_text = CleanText.clean_bracket(block_text, open_b, close_b)
            hanging_open = None
        else:
            logging.debug(f"Found hanging open bracket: {text}")
            hanging_open = open_b
            cleaned_text = text.partition(open_b)[0].rstrip()

        return cleaned_text, hanging_open

    @staticmethod
    def clean_bracket(text, open_bracket, close_bracket):

        before_open, after_close = CleanText.partition_by_brackets(text, open_bracket, close_bracket)

        if close_bracket in before_open:  # Author typo: hanging close
            logging.warning(f"Cleaning [CASE: Author typo - Hanging Close]: line={text}")
            cleaned_text = CleanText.handle_hanging_close(before_open, after_close, close_bracket)

        else:
            logging.debug(f"Cleaning [CASE: Brackets Closed on Same Line]: line={text}")
            cleaned_text = ''.join([before_open.rstrip(), after_close])

        return cleaned_text

    @staticmethod
    def clean_brackets(filtered_lines, hanging_open: str | None = None) -> tuple[list[StyledLine], str | None]:

        result = []
        lines_iter = PeekableIterator(filtered_lines)

        for line in lines_iter:

            text = line.text
            for open_b, close_b in CleanText.prioritized_pairs(hanging_open):
                line_cleaned = False
                while not line_cleaned:
                    if hanging_open and close_b in text:
                        logging.debug(f"Found closing bracket of hanging open: {line}")
                        cleaned_text, hanging_open = CleanText.handle_hanging_bracket(text, open_b, close_b)

                    elif open_b in text:
                        cleaned_text, hanging_open = CleanText.handle_opening_bracket(text, open_b, close_b, lines_iter)

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

class FilterText:

    def __init__(self, page, document):
        self.page = page
        self.layout = PageLayout(page, document)

    def add_paragraph_breaks(self, filtered_lines):

        result = []

        for i, line in enumerate(filtered_lines):
            text = line.text
            if self.layout.is_new_paragraph([line], filtered_list=filtered_lines[:i]):
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
                x = self.layout.is_paragraph_block(line_group, groups_iter, result)
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
            FilterText.collect_group(line_group, result, case="New Paragraph")
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
            self._handle_before_left_margin(line_group, result)

        elif self.layout.is_at_left_margin(line_group):

            self._handle_at_left_margin(line_group, groups_iter, result)

        elif self.layout.is_after_left_margin(line_group):  # Edge case: Indented main body
            self._handle_after_left_margin(line_group, groups_iter, result)

        else:
            if self.layout.is_at_left_margin(line_group, whole_document=True):  # Body start
                self._handle_at_left_margin(line_group, groups_iter, result)

            else:
                FilterText.skip_group(line_group, case="Unhandled Header", unhandled=True)
                FilterText.skip_group(line_group, case="Unhandled Footer", unhandled=True)

    def filter_by_boundaries(self):

        result = []
        groups_iter = PeekableIterator(self.page.line_groups)

        logging.debug(f"{self.page.heuristics}")

        for line_group in groups_iter:

            if len(result) > 0 and not self.layout.is_in_order(line_group, result):
                FilterText.skip_group(line_group, case="Text outside regular read-order")

            else:
                self._handle_left_margins(line_group, groups_iter, result)

        return result

class PageLayout:

    def __init__(self, page, document):
        self.page = page
        self.document = document
        self.bottom_boundary = page.heuristics.start_y.maximum
        self.left_boundary = page.heuristics.start_x.most_common
        self.top_boundary = page.heuristics.start_y.minimum

    def set_top_boundary(self, top_boundary):
        self.top_boundary = top_boundary

    def set_bottom_boundary(self, bottom_boundary):
        self.bottom_boundary = bottom_boundary

    def is_at_left_margin(self, line_group, whole_document: bool | None = None) -> bool:
        line_start = line_group[0].start_x
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
        vertical_gap = groups_iter.peek()[0].start_y - line_group[0].start_y
        return self.page.heuristics.word_gaps[0] <= vertical_gap <= self.page.heuristics.word_gaps[1]

    def is_within_body_boundaries(self, line_group, whole_document: bool | None = None) -> bool:

        line_start = line_group[0].start_x
        if whole_document:
            for lower_bound, upper_bound in self.document.get_all_body_boundaries():
                if lower_bound <= line_start <= upper_bound:
                    return True

        return self.page.heuristics.start_x.lower_bound <= line_start <= self.page.heuristics.start_x.upper_bound

    def is_indented_paragraph(self, line_group, whole_document: bool | None = None) -> bool:

        line_start = line_group[0].start_x
        if whole_document:
            for most_common, upper_bound in self.document.get_all_indents():
                if most_common < line_start <= upper_bound:
                    return True

        return self.page.heuristics.start_x.most_common < line_start <= self.page.heuristics.start_x.upper_bound

    def is_continued_indented_paragraph(self, line_group, filtered_lines):
        return line_group[0].start_x == filtered_lines[-1].start_x

    def is_paragraph_block(self, line_group, next_group = None, filtered_list = None):

        indent_size = self.page.heuristics.start_x.upper_bound - self.page.heuristics.start_x.most_common
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
                gap = line_group[0].start_y - next_group[0].start_y
                if gap <= self.page.heuristics.start_y.upper_bound:
                    return True

        if filtered_list:
            if len(filtered_list) > 0:
                gap = line_group[0].start_y - filtered_list[-1].start_y
                return gap <= self.page.heuristics.start_y.upper_bound
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

    def is_title_font(self, line_group) -> bool:
        return line_group[0].font_size > self.page.heuristics.font_size.upper_bound

    def is_last_line(self, line_group) -> bool:
        return line_group is self.page.line_groups[-1]

    def is_in_order(self, line_group, filtered_lines):
        return line_group[0].start_y > filtered_lines[-1].start_y

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
    def group_lines_by_y(lines):
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

        line_groups = self.group_lines_by_y(lines)
        return PageData(lines, line_groups, heuristics, ocr)

class DocumentHeuristics:
    def __init__(self):
        self.document = None
        self.all_pages = []

        self._document_left_margins = None
        self._document_body_boundaries = None
        self._document_indents = None
        self._document_font_sizes = None
        self._document_bottom_boundary = None
        self._document_top_boundary = None

    def invalidate_cache(self):
        self._document_left_margins = None
        self._document_body_boundaries = None
        self._document_indents = None
        self._document_font_sizes = None
        self._document_bottom_boundary = None
        self._document_top_boundary = None

    def add_page(self, heuristics: Heuristics):
        self.all_pages.append(heuristics)
        self.invalidate_cache()

    def get_all_left_margins(self) -> set[float]:
        if self._document_left_margins is None:
            self._document_left_margins = {
                page.start_x.most_common
                for page in self.all_pages
            }
        return self._document_left_margins

    def get_all_bottom_boundaries(self) -> set[float]:
        if self._document_bottom_boundary is None:
            self._document_bottom_boundary = {
                (page.start_y.maximum, page.start_y.lower_bound)
                for page in self.all_pages
            }
        return self._document_bottom_boundary

    def get_all_top_boundaries(self) -> set[float]:
        if self._document_top_boundary is None:
            self._document_top_boundary = {
                (page.start_y.minimum, page.start_y.lower_bound)
                for page in self.all_pages
            }
        return self._document_top_boundary

    def get_all_indents(self) -> set[float]:
        if self._document_indents is None:
            self._document_indents = {
                (page.start_x.most_common, page.start_x.upper_bound)
                for page in self.all_pages
            }
        return self._document_indents

    def get_all_body_boundaries(self) -> set[float]:
        if self._document_body_boundaries is None:
            self._document_body_boundaries = {
                (page.start_x.lower_bound, page.start_x.upper_bound)
                for page in self.all_pages
            }
        return self._document_body_boundaries

    def get_all_font_sizes(self) -> set[float]:
        if self._document_font_sizes is None:
            self._document_font_sizes = {
                (page.font_size.most_common, page.font_size.lower_bound, page.font_size.upper_bound)
                for page in self.all_pages
            }
        return self._document_font_sizes

def main():

    parser = argparse.ArgumentParser(description="Process a PDF file.")

    default_path = "./docs/test_OCR.pdf"
    parser.add_argument("--input-path", nargs="?", default=default_path, help="Path to the PDF file")
    parser.add_argument("--page-start", type=int, nargs="?", help="Page to start reading")
    parser.add_argument("--page-end", type=int, nargs="?", help="Page to end reading")
    parser.add_argument("--log-level", default="DEBUG", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")


    args = parser.parse_args()

    pdf_path = args.input_path
    page_start = args.page_start
    page_end = args.page_end

    setup_logging(log_level=args.log_level)
    # logger = logging.getLogger(__name__)

    if os.path.exists(pdf_path) and os.path.isfile(pdf_path):
        with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

            output_writer = OutputWriter()
            output_writer.set_output_path(pdf=pdf_reader.pdf, pdf_path=pdf_path)

            output_writer.write(mode="w")
            hanging_open = None

            document_heuristics = DocumentHeuristics()
            for page_blocks in pdf_reader.iter_pages(sort=True):

                lines = list(DocumentAnalysis.iter_pdf_styling_from_blocks(page_blocks=page_blocks))
                x = PageAnalyzer().analyze(lines)
                document_heuristics.add_page(x.heuristics)
                filter_text = FilterText(page=x, document=document_heuristics)

                filtered_lines = filter_text.filter_by_boundaries()
                filtered_lines = CleanText.clean_page_numbers(filtered_lines)
                filtered_lines, hanging_open = CleanText.clean_brackets(hanging_open=hanging_open, filtered_lines=filtered_lines)
                filtered_lines = filter_text.add_paragraph_breaks(filtered_lines=filtered_lines)
                page_text = CleanText.join_broken_sentences(filtered_lines=filtered_lines)

                page_text = CleanText.normalize_unicode(page_text)
                output_writer.write(mode="a", text=f'{page_text}\n\n')

if __name__ == '__main__':
    main()