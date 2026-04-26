import os
import argparse
import logging

from src.pdf2text.IO import PDFReader, OutputWriter
from src.pdf2text.core.document_cache import DocumentCache
from src.pdf2text.core.page_analyzer import PageAnalyzer
from src.pdf2text.core.page_filter import PageFilter
from src.pdf2text.models import PageLines
from src.pdf2text.rule_engine.rule_engines import RULE_ENGINES
from src.pdf2text.utils.bracket_cleaner import BracketCleaner

from src.pdf2text.utils.logger_config import setup_logging
from src.pdf2text.core.line_filter import LineFilter
from src.pdf2text.utils.text_cleaning import remove_page_number_lines, join_lines, normalize_text

os.environ["TESSDATA_PREFIX"] = "./training"

logger = logging.getLogger(__name__)

def process_page(page_blocks, document_cache, hanging_open):
    page_lines = PageLines(list(PDFReader.iter_pdf_styling_from_blocks(page_blocks)))
    if len(page_lines) == 0:
        return None, hanging_open

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

    return page_text, hanging_open


def process_pdf(pdf_path, page_start, page_end, output_path, output_dir):
    with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

        output_writer = OutputWriter()
        output_writer.set_output_path(pdf_reader.pdf, pdf_path, output_path, output_dir)

        output_writer.write(mode="w")
        hanging_open = None

        document_cache = DocumentCache()
        for page_blocks in pdf_reader.iter_pages(sort=True):
            page_text, hanging_open = process_page(page_blocks, document_cache, hanging_open)
            if page_text:
                output_writer.write(mode="a", text=f'{page_text}\n\n')

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
        process_pdf(pdf_path, page_start, page_end, output_path, output_dir)

if __name__ == '__main__':
    main()