import os
import argparse

from src.pdf2text.IO import PDFReader, OutputWriter
from src.pdf2text.core.page_analyzer import PageAnalyzer
from src.pdf2text.core.page_filter import PageFilter
from src.pdf2text.rule_engine.rule_engines import RULE_ENGINES
from src.pdf2text.utils.bracket_cleaner import BracketCleaner

from src.pdf2text.utils.logger_config import setup_logging
from src.pdf2text.core.line_filter import LineFilter
from src.pdf2text.core.text_heuristics import *
from src.pdf2text.utils.text_cleaning import remove_page_number_lines, join_lines, normalize_text

os.environ["TESSDATA_PREFIX"] = "./training"

logger = logging.getLogger(__name__)

class DocumentCache:

    def __init__(self):
        self._left_margins = set()
        self._font_size_bounds = set()
        self._font_names = set()
        self._start_y_ranges = set()
        self._row_separations = set()
        self._font_size_most_common = Counter()

    def update_cache(self, page_data):
        for column in page_data.columns:
            self._left_margins.add(column.heuristics.start_x.most_common)

        self._start_y_ranges.add(page_data.heuristics.start_y.distribution.range)
        self._row_separations.add(page_data.heuristics.row_separation)
        self._font_size_bounds.add(page_data.heuristics.font_size.bounds)
        self._font_size_most_common[page_data.heuristics.font_size.most_common] += 1
        self._font_names.add(page_data.heuristics.font_name.most_common)

    def left_margins(self) -> set[float]:
        return self._left_margins

    def start_y_ranges(self):
        return self._start_y_ranges

    def row_separations(self) -> set[float]:
        return self._row_separations

    def font_size_bounds(self) -> set[tuple[float, Bounds]]:
        return self._font_size_bounds

    def dominant_font_sizes(self) -> set[tuple[float, Bounds]]:
        return self._font_size_most_common

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

                filtered_lines = LineFilter(page_data, document_cache, RULE_ENGINES).filter_lines_individually()
                filtered_lines = PageFilter(filtered_lines).filter_references()



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