from typing import Any, Generator
import os
import re
import unicodedata
from collections import Counter
import logging
import pandas as pd
import argparse
import sys

from pdf_reader import PDFReader
from output_writer import OutputWriter
from document_analysis import DocumentAnalysis
from styled_line import StyledLine

os.environ["TESSDATA_PREFIX"] = "./training"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Log to console
        logging.FileHandler("pdf2text.log", mode='w', encoding='utf-8')  # Log to file
    ]
)

class FilterText:
    def __init__(self, page):
        self.page = page

    def clean_page_numbers(self) -> list:

        logging.debug(f"Cleaning page numbers")

        try:
            PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')

            return [
                line for line in self.page.filtered_lines if not PAGE_NUMBER_PATTERN.fullmatch(line.text)
            ]

        except Exception as e:
            logging.exception(f"Error cleaning page numbers: {e}")
            raise

    def join_broken_sentences(self) -> str:

        logging.debug(f"Joining broken sentences.")

        try:
            BROKEN_WORD_PATTERN = re.compile(r'\w-\s*$')
            HYPHEN_END_PATTERN = re.compile(r'-\s*$')

            page_line_text = []
            skip_until = -1  # highest index of merged lines

            for i, current_line in enumerate(self.page.filtered_lines):
                # Skip lines already merged into previous text
                if i <= skip_until:
                    continue

                current_text = current_line.text

                # If current line ends with a broken word, merge forward
                if BROKEN_WORD_PATTERN.search(current_text):
                    j = i + 1
                    # Keep merging as long as there are more broken lines
                    while j < len(self.page.filtered_lines):
                        current_text = HYPHEN_END_PATTERN.sub('', current_text) + self.page.filtered_lines[j].text.lstrip()
                        if BROKEN_WORD_PATTERN.search(current_text) and j + 1 < len(self.page.filtered_lines):
                            j += 1
                            continue
                        else:
                            break

                    skip_until = j  # mark lines up to j as consumed
                    page_line_text.append(current_text)
                else:
                    page_line_text.append(current_text)

            return " ".join(page_line_text)

        except Exception as e:
            logging.exception(f"Error joining broken sentences: {e}")
            raise

    def normalize_unicode(self, text):
        compatability_mapped = unicodedata.normalize('NFKC', text)
        decomposed = unicodedata.normalize('NFD', compatability_mapped)

        # Step 2: Remove combining marks
        return ''.join(c for c in decomposed if not unicodedata.combining(c))

    def prioritized_pairs(self, hanging_open=None):

        pairs = {'(': ')', '[': ']', '{': '}'}

        if hanging_open:
            yield hanging_open, pairs[hanging_open]
        for k, v in pairs.items():
            if k != hanging_open:
                yield k, v

    def has_parentheses(self, i: int, key: str) -> int:

        return self.page.filtered_lines[i].text.count(key)

    def clean_parentheses(self, hanging_open: str | None=None) -> tuple[list[StyledLine], str | None]:

        lines = self.page.filtered_lines
        i = 0
        while i < len(lines):

            line_cleaned = False
            while True:

                for key, value in self.prioritized_pairs(hanging_open):

                    if hanging_open or key in lines[i].text:
                        opens_in = i
                        closes_in = None
                        j = i

                        while j < len(lines):
                            if value in lines[j].text:
                                closes_in = j
                                break
                            j += 1

                        if closes_in is not None:
                            diff = closes_in - opens_in
                            before_open, _, _ = lines[opens_in].text.partition(key)
                            _, _, after_close = lines[closes_in].text.partition(value)

                            if diff == 0:
                                if hanging_open:
                                    logging.debug(f"Cleaning i={opens_in}, [CASE: Hanging Open Bracket Closed on First Line]: line={lines[opens_in]}")
                                    lines[opens_in].text = after_close.lstrip()
                                    hanging_open = None
                                else:

                                    if value in before_open: # Author typo: hanging close
                                        before_typo, _, after_typo = before_open.partition(value)
                                        before_open = before_typo + after_typo
                                        _, _, after_close = after_close.partition(value)
                                        logging.warning(f"Cleaning i={opens_in}, [CASE: Author typo - Hanging Close]: line={lines[opens_in]}")
                                        lines[opens_in].text = ''.join([before_open.rstrip(), after_close])
                                    else:
                                        logging.debug(f"Cleaning i={opens_in}, [CASE: Parentheses Closed on Same Line]: line={lines[opens_in]}")
                                        lines[opens_in].text = ''.join([before_open.rstrip(), after_close])
                            elif diff > 0:

                                if hanging_open:
                                    logging.debug(f"Cleaning i={closes_in}, [CASE: Hanging Open Bracket Closed After Multiple Lines]: line={lines[closes_in]}")
                                    lines[closes_in].text = after_close.lstrip()
                                    hanging_open = None
                                    opens_in -= 1
                                else:
                                    logging.debug(f"Cleaning i={opens_in}, [CASE: Parentheses Closed After Multiple Lines]: line={lines[opens_in]}")
                                    lines[opens_in].text = ''.join([before_open.rstrip(), after_close])
                                    logging.debug(f"Cleaned: line={lines[opens_in]}")
                                    logging.debug(f"Removing i={closes_in}, [CASE: Removing Multi-Line Parentheses]: line={lines[closes_in]}")
                                    lines.pop(closes_in)

                            for k in range(closes_in - 1, opens_in, -1):
                                logging.debug(f"Removing i={k}, [CASE: Removing Multi-Line Parentheses]: line={lines[k]}")
                                lines.pop(k)

                            if self.has_parentheses(i, key):
                                line_cleaned = True
                                break
                            else:
                                line_cleaned = False

                        else:
                            if self.page.ocr and j - i > 2:
                                logging.warning("OCR - Likely recognized 'C' as open parentheses")
                                break

                            hanging_open = key
                            before_open, _, _ = lines[opens_in].text.partition(key)
                            lines[opens_in].text = before_open.rstrip()
                            for k in range(j - 1, opens_in, -1):
                                lines.pop(k)
                            line_cleaned = False
                            break

                if not line_cleaned:
                    break
            i += 1
        return lines, hanging_open

    def add_paragraph_breaks(self):

        for i, line in enumerate(self.page.filtered_lines):
            if self.page.is_body_paragraph(i):
                pass
            else:
                self.page.filtered_lines[i].text += "\n"
        return self.page.filtered_lines

    @staticmethod
    def skip_line(i: int, lines: list[StyledLine], case: str, unhandled: bool | None=None) -> int:
        starting_boundary = lines[i].start_y
        while i < len(lines) and lines[i].start_y == starting_boundary:
            if unhandled:
                logging.error(f"Skipped i={i}, [CASE: {case}]: line={lines[i]}")
            else:
                logging.info(f"Skipped i={i}, [CASE: {case}]: line={lines[i]}")
            i += 1
        return i

    @staticmethod
    def collect_line(i: int, lines: list[StyledLine], case: str) -> tuple[list[StyledLine], int]:
        current_line = []
        starting_boundary = lines[i].start_y
        while i <= len(lines) - 1 and lines[i].start_y == starting_boundary:
            logging.debug(f"Collected i={i}, [CASE: {case}]: line={lines[i]}")
            current_line.append(lines[i])
            i += 1
        return current_line, i

    @staticmethod
    def collect_once(i: int, lines: list[StyledLine], case: str) -> tuple[list[StyledLine], int]:
        logging.debug(f"Collected Once i={i}, [CASE: {case}]: line={lines[i]}")
        current_line = [lines[i]]
        return current_line, i + 1

    def filter_title_font(self, i):
        current_line = []
        if self.page.ocr:
            if self.page.ocr_is_title_font(i):
                i = FilterText.skip_line(i, self.page.lines, case="Title Font")
            else:
                current_line, i = FilterText.collect_line(i, self.page.lines, case="OCR - Misrecognized Title Font")
        else:
            i = FilterText.skip_line(i, self.page.lines, case="Title Font")

        return current_line, i


    def filter_by_font(self, i):

        current_line = []
        if self.page.is_dominant_font(i):
            # if self.is_header_region():
            #     i = FilterText.skip_line(i, lines, case=f"Outside Indent Bounds {self.page_heuristics['start x']} - Dominant Font Indented Line @ Header", unhandled=True)
            # elif self.is_footer_region(line=current_word):
            #     i = FilterText.skip_line(i, lines, case=f"Outside Indent Bounds ({self.page_heuristics['start x']['lower bound']}-{self.page_heuristics['start x']['lower bound']})  - Dominant Font Indented Line @ Footer", unhandled=True)
            # else:
            current_line, i = FilterText.collect_once(i, self.page.lines, case=f"Outside Indent Bounds - Indented Line is Dominant Font")
        else:
            i = FilterText.skip_line(i, self.page.lines, case="Unhandled Uncommon Font", unhandled=True)

        return current_line, i

    def filter_indented_lines(self, i):
        current_line = []
        starting_boundary = self.page.lines[i].start_y

        while self.page.lines[i].start_y <= starting_boundary:

            if self.page.is_continued_indented_paragraph(i):

                if self.page.is_last_line(i):
                    current_line, i = FilterText.collect_once(i, self.page.lines, case="Last Line is Continued Indented Paragraph")
                elif self.page.is_body_paragraph(i):
                    current_line, i = FilterText.collect_line(i, self.page.lines, case="Indented Body Paragraph")
                else:
                    i = FilterText.skip_line(i, self.page.lines, case="Unhandled Indented Line", unhandled=True)

            elif self.page.is_indented_paragraph(i):
                if self.page.is_title_font(i):
                    current_line, i = self.filter_title_font(i)
                else:
                    current_line, i = FilterText.collect_line(i, self.page.lines, case="Indented Paragraph")

            elif self.page.ocr:
                if self.page.is_footer_region(i):
                    i = FilterText.skip_line(i, self.page.lines, case="Indented Line @ Footer")
                elif self.page.is_dominant_word_gap(i):
                    current_line, i = FilterText.collect_line(i, self.page.lines, case="OCR - Indented Line Following Dominant Word Gap")
                else:
                    i = FilterText.skip_line(i, self.page.lines, case="Unhandled Indented Line", unhandled=True)

            else:
                if self.page.is_indented_paragraph(i, whole_document=True):
                    current_line, i = FilterText.collect_line(i, self.page.lines, case="Whole Document - Indented Paragraph")
                else:
                    i = FilterText.skip_line(i, self.page.lines, case="Unhandled Indented Line", unhandled=True)
                # current_line, i = FilterText.collect_once(i, lines)
            break

        return current_line, i

    def filter_by_boundaries(self):

        filtered_lines: list[StyledLine] = []
        current_line: list[StyledLine] = []

        i = 0
        while i < len(self.page.lines):

            current_word: StyledLine = self.page.lines[i]
            line_y_boundary = current_word.start_y

            if self.page.is_header_region():

                if self.page.is_before_left_margin(i):  # Header
                    if self.page.within_body_boundaries(i):  # OCR inaccuracy
                        current_line, i = FilterText.collect_line(i, self.page.lines, case="OCR - Misrecognized Body Paragraph as Indented")
                    else:
                        i = FilterText.skip_line(i, self.page.lines, case="Non-aligned Header")

                if self.page.is_at_left_margin(i):  # Body start

                    if self.page.is_body_paragraph(i):
                        self.page.top_boundary = current_word.start_y
                        current_line, i = FilterText.collect_line(i, self.page.lines, case="First Body Paragraph")

                    else: # Aligned header
                        i = FilterText.skip_line(i, self.page.lines, case="Aligned Header")

                elif self.page.is_after_left_margin(i):  # Edge case: Indented main body

                    if self.page.within_body_boundaries(i, whole_document=True):
                        if self.page.is_title_font(i):
                            current_line, i = self.filter_title_font(i)
                        else:
                            current_line, i = FilterText.collect_line(i, self.page.lines, case="Indented Main Body")
                    else:
                        i = FilterText.skip_line(i, self.page.lines, case="Right-side Header")

                else:
                    if self.page.is_at_left_margin(i, whole_document=True):  # Body start
                        if self.page.is_body_paragraph(i):
                            self.page.top_boundary = current_word.start_y
                            current_line, i = FilterText.collect_line(i, self.page.lines, case="First Body Paragraph")
                    else:
                        i = FilterText.skip_line(i, self.page.lines, case="Unhandled Header", unhandled=True)

            elif self.page.is_footer_region(i):  # Very bottom

                if self.page.is_at_left_margin(i):  # Main body
                    if self.page.is_last_line(i): # No real footer
                        current_line, i = self.filter_by_font(i)
                    elif self.page.is_body_paragraph(i):
                        current_line, i = FilterText.collect_line(i, self.page.lines, case="Body Paragraph @ Footer")
                    else:
                        i = FilterText.skip_line(i, self.page.lines, case="Unhandled Footer", unhandled=True)
                elif self.page.is_before_left_margin(i):
                    if self.page.within_body_boundaries(i):  # OCR inaccuracy
                        current_line, i = FilterText.collect_line(i, self.page.lines, case="OCR - Misrecognized Body Paragraph as Outdented")
                    else:
                        i = FilterText.skip_line(i, self.page.lines, case="Left-side footer")

                elif self.page.is_after_left_margin(i):
                    current_line, i = self.filter_indented_lines(i)
                else:
                    i = FilterText.skip_line(i, self.page.lines, case="Unhandled Footer", unhandled=True)

            elif self.page.is_at_left_margin(i):  # Main body

                if self.page.is_title_font(i):
                    current_line, i = self.filter_title_font(i)
                else:
                    if self.page.is_dominant_font(i):
                        current_line, i = FilterText.collect_line(i, self.page.lines, case="Main Body")
                    else:
                        i = FilterText.skip_line(i, self.page.lines, case="Aligned title")

            elif self.page.is_in_order(i) is False:

                i = FilterText.skip_line(i, self.page.lines, case="Text outside regular read-order")

            elif self.page.is_after_left_margin(i):  # Indented block

                if self.page.is_last_line(i) and self.page.lines[i].start_y == line_y_boundary:
                    current_line, i = FilterText.collect_once(i, self.page.lines, case="Last Line is Continued Indent")

                elif i < len(self.page.lines) - 1:

                    current_line, i = self.filter_indented_lines(i)

            elif self.page.is_before_left_margin(i):  # Left-side footer
                if self.page.within_body_boundaries(i): # OCR inaccuracy
                    current_line, i = FilterText.collect_line(i, self.page.lines, case="OCR - Misrecognized Body Paragraph as Outdented")
                else:
                    i = FilterText.skip_line(i, self.page.lines, case="Left-side footer")

            else:
                i += 1


            if len(current_line) > 0:

                self.page.filtered_lines.append(StyledLine(text=' '.join(line.text for line in current_line if line.text.strip()),
                                                 font_size=pd.Series([line.font_size for line in current_line]).mean(),
                                                 font_name=current_word.font_name,
                                                 start_x=current_word.start_x,
                                                 start_y=current_word.start_y,
                                                 end_x=current_word.end_x))
                current_line = []

        return filtered_lines


class Page:
    def __init__(self, document_heuristics):
        self.page_heuristics = None
        self.document_heuristics = document_heuristics
        self.ocr = None
        self.lines = None
        self.filtered_lines = []
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

    def is_at_left_margin(self, i, whole_document: bool | None = None) -> bool:
        if whole_document:
            for page in self.document_heuristics.all_pages:
                if self.lines[i].start_x == page['start x']['most common']:
                    return True
        return self.lines[i].start_x == self.left_boundary

    def is_after_left_margin(self, i) -> bool:
        return self.lines[i].start_x > self.left_boundary

    def is_before_left_margin(self, i) -> bool:
        return self.lines[i].start_x < self.left_boundary

    def is_footer_region(self, i) -> bool:
        return self.lines[i].start_y >= self.bottom_boundary - self.page_heuristics['start y']['lower bound']

    def is_header_region(self) -> bool:
        return self.top_boundary is None

    def is_dominant_word_gap(self, i) -> bool:
        word_separation = self.lines[i + 1].start_x - self.lines[i].end_x
        return self.page_heuristics['word gaps']['lower bound'] <= word_separation <= self.page_heuristics['word gaps'][
            'upper bound']

    def within_body_boundaries(self, i, whole_document: bool | None = None) -> bool:
        if whole_document:
            for page in self.document_heuristics.all_pages:
                if page['start x']['most common'] < self.lines[i].start_x <= page['start x']['upper bound']:
                    return True
        return self.page_heuristics['start x']['lower bound'] <= self.lines[i].start_x <= self.page_heuristics['start x'][
            'upper bound']

    def is_indented_paragraph(self, i, whole_document: bool | None = None) -> bool:
        if whole_document:
            for page in self.document_heuristics.all_pages:
                if page['start x']['most common'] < self.lines[i].start_x <= page['start x']['upper bound']:
                    return True
        return self.page_heuristics['start x']['most common'] < self.lines[i].start_x <= self.page_heuristics['start x'][
            'upper bound']

    def is_continued_indented_paragraph(self, i):
        return self.lines[i].start_x == self.filtered_lines[-1].start_x

    def is_body_paragraph(self, i):

        gap_to_next_line = 0
        while gap_to_next_line == 0 and i < len(self.lines) - 1:  # For OCR or varying font compatibility
            gap_to_next_line = self.lines[i + 1].start_y - self.lines[i].start_y
            i += 1

        return gap_to_next_line <= self.page_heuristics['start y']['upper bound']  # Aligned header

    def is_dominant_font(self, i) -> bool:
        return self.page_heuristics['font size']['lower bound'] <= self.lines[i].font_size <= self.page_heuristics['font size'][
            'upper bound']

    def is_title_font(self, i) -> bool:
        return self.lines[i].font_size > self.page_heuristics['font size']['upper bound']

    def is_last_line(self, i):
        return i == len(self.lines) - 1

    def is_in_order(self, i):
        return self.lines[i].start_y > self.filtered_lines[-1].start_y

    def ocr_is_title_font(self, i) -> bool:

        # Current line isn't being collected
        whole_line, _ = FilterText.collect_line(i, self.lines, case="OCR Checking Title Font - Not Collected Yet")
        font_size = pd.Series([line.font_size for line in whole_line]).mean()

        return font_size > self.page_heuristics['font size']['upper bound']

    def set_page_boundaries(self) -> None:

        self.left_boundary = self.page_heuristics['start x']['most common']
        self.bottom_boundary = self.page_heuristics['start y']['maximum']

    def setup(self) -> None:

        self.set_ocr()
        page_heuristics = TextHeuristics(ocr=self.ocr)

        self.page_heuristics = page_heuristics.analyze(lines=self.lines)

        if self.ocr and self.page_heuristics['font name']['most common'] != 'GlyphLessFont':
            self.ocr = False
            self.page_heuristics = page_heuristics.analyze(lines=self.lines)

        self.document_heuristics.add_page(self.page_heuristics)
        self.set_page_boundaries()


class TextHeuristics:
    def __init__(self, ocr) -> None:
        self.threshold = None
        self.ocr = ocr

    @staticmethod
    def get_styling_counter(lines: list, attribute: str) -> Counter:

        try:
            counter = Counter()
            for line in lines:
                attr_value = getattr(line, attribute)
                counter[attr_value] += len(line.text)
            return counter

        except AttributeError:
            logging.exception(f"Invalid styling attribute: {attribute}")
            raise
        except Exception as e:
            logging.exception(f"Error getting style counter for {attribute}: {e}")
            raise

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

        gaps = (
            next_start - prev_end
            for _, group in pd.DataFrame(lines).groupby("start_y")
            for prev_end, next_start in zip(group["end_x"], group["start_x"][1:])
            if next_start - prev_end > 0
        )

        return self.compute_bounds(data=sorted(gaps))

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

    def analyze(self, lines: list) -> dict:

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



        return {'start x': {'most common': most_common['start_x'], 'minimum': min(counters['start_x']), 'maximum': max(counters['start_x']), 'lower bound': indent_bounds[0], 'upper bound': indent_bounds[1]},
                'start y': {'most common': most_common['start_y'], 'minimum': min(counters['start_y']), 'maximum': max(counters['start_y']), 'lower bound': line_gaps[0], 'upper bound': line_gaps[1]},
                'end x': {'most common': most_common['end_x'], 'minimum': min(counters['end_x']), 'maximum': max(counters['end_x']), 'lower bound': edge_bounds[0], 'upper bound': edge_bounds[1]},
                'word gaps': {'lower bound': word_gaps[0], 'upper bound': word_gaps[1]},
                'font size': {'most common': most_common['font_size'], 'lower bound': font_bounds[0], 'upper bound': font_bounds[1]},
                'font name': {'most common': most_common['font_name']}}

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

    default_path = "./docs/test_OCR.pdf"
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
                page.filtered_lines = filter_text.clean_page_numbers()
                page.filtered_lines, hanging_open = filter_text.clean_parentheses(hanging_open=hanging_open)
                page.filtered_lines = filter_text.add_paragraph_breaks()
                page_text = filter_text.join_broken_sentences()

                output_writer.write(mode="a", text=f'{page_text}\n\n')

if __name__ == '__main__':
    main()