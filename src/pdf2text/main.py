import os
import argparse
from itertools import tee
from collections import defaultdict

from src.pdf2text.IO import PDFReader, OutputWriter
from src.pdf2text.models import *

from src.pdf2text.rule_engine import RuleEngine
from src.pdf2text.rule_engine.indented import *
from src.pdf2text.rule_engine.footer import *
from src.pdf2text.rule_engine.header import *
from src.pdf2text.rule_engine.continuous_paragraph import *
from src.pdf2text.rule_engine.at_left_margin import *
from src.pdf2text.rule_engine.before_left_margin import *

from src.pdf2text.utils.logger_config import setup_logging
from src.pdf2text.core.text_heuristics import *
from src.pdf2text.core.line_collector import LineCollector
from src.pdf2text.core.classifier import IndentationClassifier, PositionClassifier, MarginClassifier, RegionClassifier, CharacterCountClassifier, FontNameClassifier, FontSizeClassifier, SplitSpanClassifier
from src.pdf2text.utils.text_cleaning import remove_page_number_lines, join_lines, normalize_text

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

class FilterText:

    def __init__(self, page, document_cache):
        self.page = page
        self.document_cache = document_cache
        self.layout = None
        self.collector = LineCollector()

        self.indented_rule_engine = RuleEngine([
            IndentedBlockLastLineRule(),
            IndentedBlockParagraphRule(),
            IndentedMainFontRule(),
            SplitSpanIndentationLineRule(),
            ParagraphStartIndentedRule(),
            EpigraphAuthorRule(),
            TitlePageRule(),
            ItalicWordMidLineRule(),
            BoldWordMidLineRule(),
            FallbackIndentedRule()
        ])

        self.header_rule_engine = RuleEngine([
            BodyParagraphAtHeaderRegionRule(),
            HighCharacterCountLineAtHeaderRegionRule(),
            SingleLineJournalNameAtHeaderRule(),
            StartJournalNameAtHeaderRule(),
            FallbackHeaderRegionRule()
        ])

        self.footer_rule_engine = RuleEngine([
            FooterRegionBodyParagraphRule(),
            FooterRegionLoneIndentedTextRule(),
            FooterRegionHighCharacterCountLineRule(),
            FallbackFooterRegionRule()
        ])

        self.continuous_paragraph_engine = RuleEngine([
            ContinuousParagraphMainFontRule(),
            ContinuousParagraphMultiLineTitleRule(),
            FallbackContinuousParagraphRule()
        ])

        self.at_left_margin_engine = RuleEngine([
            SingleEmphasizedLineRule(),
            BoldSectionHeaderAtLeftMarginRule(),
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

    def _select_engine(self, ctx):

        if ctx.region is VerticalRegion.HEADER:
            return self.header_rule_engine

        if ctx.region is VerticalRegion.FOOTER:
            return self.footer_rule_engine

        if ctx.margin_position is MarginPosition.BEFORE:
            return self.before_left_margin_engine

        if ctx.margin_position is MarginPosition.AT:
            if ctx.position_in_paragraph is not PositionInParagraph.SINGLE_LINE:
                return self.continuous_paragraph_engine

            return self.at_left_margin_engine

        if ctx.margin_position is MarginPosition.AFTER:
            return self.indented_rule_engine

        return None

    def _filter_line(self, ctx, result):
        engine = self._select_engine(ctx)

        if engine is None:
            decision = Decision.unhandled("Router could not find a suitable rule engine", "_select_engine")
        else:
            decision = engine.decide(ctx)

        result.extend(self.collector.process(ctx, decision))

    @staticmethod
    def _add_page_break(buffer):
        if not buffer:
            return []

        last_line = buffer[-1].with_text(buffer[-1].text + "\n\n")
        return [*buffer[:-1], last_line]

    def _process_column(self, column):
        buffer = []
        self.layout = PageLayout(self.page, column, self.document_cache)
        logging.debug(f"Column: {column.heuristics}")
        groups_iter = PeekableIterator(column.lines)

        for group in groups_iter:
            ctx = LineContext.create(self.layout, group, groups_iter, buffer)
            self._filter_line(ctx, buffer)

        return self._add_page_break(buffer)

    def filter_by_boundaries(self):
        result = []

        for column in self.page.columns:
            result.extend(self._process_column(column))

        return result

class PageLayout:

    def __init__(self, page, column, document_cache):
        self.column = column
        self.line_position = PositionClassifier(page, column, document_cache)
        self.line_indentation = IndentationClassifier(page, column, document_cache)
        self.line_region = RegionClassifier(page, column, document_cache)
        self.margin_position = MarginClassifier(page, column, document_cache)
        self.line_character_count = CharacterCountClassifier(page, column, document_cache)
        self.line_font_name = FontNameClassifier(page, column, document_cache)
        self.line_font_size = FontSizeClassifier(page, column, document_cache)
        self.line_split_span = SplitSpanClassifier(page, column, document_cache)

class PageAnalyzer:

    def __init__(self, lines: PageLines):
        self.lines = lines
        self._ocr = None

    @property
    def ocr(self):
        if self._ocr is None:
            if len(self.lines) == 0:
                return False

            words = 1
            phrases = 1

            for line in self.lines:
                text = line.text.strip()
                if not text:
                    continue
                elif " " not in text:
                    words += 1
                else:
                    phrases += 1

            self._ocr = (words / (words + phrases)) > 0.95

        return self._ocr

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
    def create_line_groups(line_rows, coordinate_tolerance):
        result = []
        for row in line_rows:
            buffer = [row[0]]
            for previous, current in zip(row, row[1:]):
                if current.start_x - previous.end_x <= coordinate_tolerance:
                    buffer.append(current)
                else:
                    result.append(buffer)
                    buffer = [current]
            result.append(buffer)
        return result

    def compute_layout_profile(self, page_lines):
        start_x = IndentHeuristic(self.ocr).compute_feature_stats(page_lines)
        start_y = StartYHeuristic(self.ocr).compute_feature_stats(page_lines)
        end_x = EndXHeuristic(self.ocr).compute_feature_stats(page_lines)
        character_count = CharacterCountHeuristic(self.ocr).compute_feature_stats(page_lines)
        font_size = FontSizeHeuristic(self.ocr).compute_feature_stats(page_lines)
        font_name = FontNameHeuristic(self.ocr).compute_feature_stats(page_lines)

        gap_within_rows = GapWithinRowsHeuristic(self.ocr).compute_bounds(page_lines)
        gap_between_rows = GapBetweenRowsHeuristic(self.ocr).compute_bounds(page_lines)
        gap_data = GapData(gap_within_rows, gap_between_rows)

        return LayoutProfile(start_x, start_y, end_x, gap_data, character_count, font_size, font_name)

    def analyze(self):

        columns = []
        page_heuristics = self.compute_layout_profile(self.lines)
        coordinate_tolerance = page_heuristics.gaps.within_rows.upper if self.ocr else 0.0
        line_groups = self.create_line_groups(self.lines.rows, coordinate_tolerance)

        column_count = ColumnCountHeuristic(self.ocr)
        column_count.build_counter(self.lines, coordinate_tolerance)
        column_count_stats = column_count.compute_feature_stats(self.lines)
        logging.debug(f"Detected {column_count_stats.upper_bound} column(s)")

        if column_count_stats.upper_bound > 1:
            start_x_columns = column_count.compute_column_starts(self.lines, int(column_count_stats.upper_bound))
            columned_groups = self.sort_line_columns(line_groups, start_x_columns)

            for start_x in sorted(columned_groups.keys()):
                column_lines = PageLines(columned_groups[start_x])
                column_heuristics = self.compute_layout_profile(column_lines)
                column_line_groups = self.create_line_groups(column_lines.rows, coordinate_tolerance)
                columns.append(ColumnData(column_line_groups, column_heuristics))
        else:
            columns.append(ColumnData(line_groups, page_heuristics))

        return PageData(page_heuristics, columns, self.ocr)

class DocumentCache:
    def __init__(self):
        self._left_margins = set()
        self._font_size_bounds = set()
        self._font_names = set()
        self._start_y_ranges = set()
        self._row_separations = set()

    def update_cache(self, page_data):
        for column in page_data.columns:
            self._left_margins.add(column.heuristics.start_x.most_common)

        self._start_y_ranges.add(page_data.heuristics.start_y.distribution.range)
        self._row_separations.add(page_data.heuristics.row_separation)
        self._font_size_bounds.add(page_data.heuristics.font_size.bounds)
        self._font_names.add(page_data.heuristics.font_name.most_common)

    def left_margins(self) -> set[float]:
        return self._left_margins

    def start_y_ranges(self):
        return self._start_y_ranges

    def row_separations(self) -> set[float]:
        return self._row_separations

    def font_size_bounds(self) -> set[tuple[float, Bounds]]:
        return self._font_size_bounds

    def font_names(self) -> set[str]:
        return self._font_names

def main():

    parser = argparse.ArgumentParser(description="Process a PDF file.")
    parser.add_argument("--input-path", required=True, nargs="?", help="Path to the PDF file")
    parser.add_argument("--page-start", type=int, nargs="?", help="Page to start reading")
    parser.add_argument("--page-end", type=int, nargs="?", help="Page to end reading")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")

    path_group = parser.add_mutually_exclusive_group()
    path_group.add_argument("--output-path", nargs="?", help="Path to write output to")
    path_group.add_argument("--output-dir", default="generated", nargs="?", help="Path to write output to")

    args = parser.parse_args()
    pdf_path = args.input_path
    output_path = args.output_path
    output_dir = args.output_dir
    page_start = args.page_start
    page_end = args.page_end

    setup_logging(log_level=args.log_level)

    if os.path.exists(pdf_path) and os.path.isfile(pdf_path):
        with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

            output_writer = OutputWriter()
            output_writer.set_output_path(pdf_reader.pdf, pdf_path, output_path, output_dir)

            output_writer.write(mode="w")
            hanging_open = None

            document_cache = DocumentCache()
            for page_blocks in pdf_reader.iter_pages(sort=True):

                page_lines = PageLines(list(PDFReader.iter_pdf_styling_from_blocks(page_blocks)))
                if len(page_lines) == 0:
                    continue

                page_data = PageAnalyzer(page_lines).analyze()
                document_cache.update_cache(page_data)
                filter_text = FilterText(page_data, document_cache)

                filtered_lines = filter_text.filter_by_boundaries()
                filtered_lines = remove_page_number_lines(filtered_lines)

                cleaned_brackets = BracketCleaner(hanging_open)
                filtered_lines = cleaned_brackets.clean_brackets(filtered_lines)
                hanging_open = cleaned_brackets.get_hanging_open()

                # filtered_lines = filter_text.add_paragraph_breaks(filtered_lines=filtered_lines)
                page_text = join_lines(filtered_lines)
                page_text = normalize_text(page_text, page_data.ocr)

                output_writer.write(mode="a", text=f'{page_text}\n\n')

if __name__ == '__main__':
    main()