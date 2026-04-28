import os
import argparse
import logging

from src.pdf2text.IO.pdf_reader import PDFReader
from src.pdf2text.IO.output_writer import OutputWriter

from src.pdf2text.core.document_cache import DocumentCache
from src.pdf2text.core.page_analyzer import SpansAnalysis
from src.pdf2text.core.page_filter import PageFilter
from src.pdf2text.models.layout.spans import Spans
from src.pdf2text.rule_engine.rule_engines import RULE_ENGINES
from src.pdf2text.utils.bracket_cleaner import BracketCleaner, BracketCleanerContext

from src.pdf2text.utils.logger_config import setup_logging
from src.pdf2text.core.line_filter import LineFilter
from src.pdf2text.utils.text_cleaning import remove_page_number_lines, join_lines, normalize_text

os.environ["TESSDATA_PREFIX"] = "./training"

logger = logging.getLogger(__name__)

def analyze_page_step(page_lines):
    return SpansAnalysis(page_lines).analyze_page()

def update_cache_step(page_data, document_cache):
    document_cache.update_cache(page_data)
    return document_cache

def filter_lines_step(page_data, document_cache):
    return LineFilter(page_data, document_cache, RULE_ENGINES).filter_lines_individually()

def page_filter_step(classified_lines):
    return PageFilter(classified_lines).filter_references()

def clean_page_numbers_step(classified_lines):
    return remove_page_number_lines(classified_lines)

def clean_brackets_step(lines, bracket_cleaner_context):
    cleaned_brackets = BracketCleaner(bracket_cleaner_context)
    lines = cleaned_brackets.clean_brackets(lines)
    return lines, bracket_cleaner_context

def join_lines_step(lines):
    return join_lines(lines)

def normalize_text_step(text, ocr):
    return normalize_text(text, ocr)

def process_page(page_blocks, document_cache, bracket_cleaner_context):
    page_spans = Spans(list(PDFReader.iter_pdf_styling_from_blocks(page_blocks)))
    if len(page_spans) == 0:
        return None, bracket_cleaner_context

    page_data = analyze_page_step(page_spans)
    document_cache = update_cache_step(page_data, document_cache)
    classified_lines = filter_lines_step(page_data, document_cache)
    classified_lines = page_filter_step(classified_lines)
    lines = clean_page_numbers_step(classified_lines)
    lines, hanging_open = clean_brackets_step(lines, bracket_cleaner_context)
    text = join_lines_step(lines)
    text = normalize_text_step(text, page_data.is_ocr)

    return text, hanging_open

def process_pdf(pdf_path, page_start, page_end, output_path, output_dir):
    with PDFReader(pdf_path, page_start, page_end) as pdf_reader:

        output_writer = OutputWriter()
        output_writer.set_output_path(pdf_reader.pdf, pdf_path, output_path, output_dir)

        output_writer.write(mode="w")
        bracket_cleaner_context = BracketCleanerContext(multipage_open=None)

        document_cache = DocumentCache()
        for page_blocks in pdf_reader.iter_pages(sort=True):
            page_text, hanging_open = process_page(page_blocks, document_cache, bracket_cleaner_context)
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