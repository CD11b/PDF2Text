from __future__ import annotations
from typing import Generator, Optional, Tuple
import pymupdf
import logging

from document_analysis import DocumentAnalysis


class PDFReader:
    def __init__(self, pdf_path: str, page_start: Optional[int] = None, page_end: Optional[int] = None) -> None:
        self.pdf_path: str = pdf_path
        self.page_start: Optional[int] = page_start
        self.page_end: Optional[int] = page_end
        self.pdf: Optional[pymupdf.Document] = None

    def __enter__(self) -> PDFReader:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.pdf:
            self.close()

        if exc_type:
            logging.error(f"An exception occurred: {exc_val}")

        # re-raise exceptions if they occurred
        return False

    def iter_pages(self, sort: bool = False) -> Generator[list[dict], None, None]:
        """Iterate through pages and yield raw text block dictionaries."""
        page_info = self.get_page_count()

        # Handle tuple (start, end)
        if isinstance(page_info, tuple):
            start, end = page_info
        else:
            start, end = 0, page_info  # Default range from 0 to page_count

        for i in range(start, end):
            logging.info(f"[---- Reading page {i} ----]")
            yield DocumentAnalysis.get_page_blocks_from_dict(
                pdf=self.pdf, page_number=i, sort=sort
            )

    def get_page_count(self) -> int | Tuple[int, int]:
        """Return either the total page count or (start, end) range."""
        if self.page_start is not None and self.page_end is not None:
            return self.page_start, self.page_end
        assert self.pdf is not None
        return self.pdf.page_count

    def open(self) -> Optional[pymupdf.Document]:
        """Open the PDF file and return a pymupdf.Document."""
        if self.pdf is None:
            self.pdf = pymupdf.open(str(self.pdf_path))
            logging.debug(f"Opened PDF: {self.pdf_path}")
            return self.pdf
        return None

    def close(self) -> None:
        """Close the PDF file if open."""
        if self.pdf:
            try:
                self.pdf.close()
                logging.debug(f"Closed PDF: {self.pdf_path}")
            except Exception as e:
                logging.error(f"Error closing PDF: {e}")
            finally:
                self.pdf = None
