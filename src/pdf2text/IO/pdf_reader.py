from __future__ import annotations
from typing import Generator, Optional, Tuple, List, Dict, Any
from src.pdf2text.models import Span
import pymupdf
import logging

logger = logging.getLogger(__name__)

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
            logger.error(f"An exception occurred: {exc_val}")

        # re-raise exceptions if they occurred
        return False

    @staticmethod
    def get_page_blocks_from_dict(pdf: pymupdf.Document,
                                  page_number: int,
                                  sort: bool) -> List[Dict[str, Any]]:
        """
        Extract all text blocks from a PDF page as dictionaries.

        Args:
            pdf: The open PyMuPDF document.
            page_number: Page index (0-based).
            sort: Whether to sort text blocks spatially.

        Returns:
            A list of text block dictionaries from the page.
        """
        try:
            page = pdf[page_number]
            page_text = page.get_textpage()
            page_dict = page_text.extractDICT(sort=sort)
            return page_dict["blocks"]
        except Exception as e:
            logger.exception(f"Error reading PDF blocks: {e}")
            raise

    @staticmethod
    def iter_pdf_styling_from_blocks(page_blocks: List[Dict[str, Any]]) -> Generator[Span, None, None]:
        """
        Iterate over styled text lines extracted from block dictionaries.

        Args:
            page_blocks: List of text block dictionaries from a PDF page.

        Yields:
            StyledLine objects representing each text span.
        """
        try:
            for block in page_blocks:
                if block.get("type") != 0:  # skip non-text blocks
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            yield Span.create(text=text,
                                              font_size=float(span["size"]),
                                              font_name=str(span["font"]),
                                              start_x=float(span["origin"][0]),
                                              start_y=float(span["origin"][1]),
                                              end_x=float(span["bbox"][2]))

        except Exception as e:
            logger.exception(f"Error reading styles from PDF blocks: {e}")
            raise

    def iter_pages(self, sort: bool = False) -> Generator[list[dict], None, None]:
        """Iterate through pages and yield raw text block dictionaries."""
        page_info = self.get_page_count()

        # Handle tuple (start, end)
        if isinstance(page_info, tuple):
            start, end = page_info
        else:
            start, end = 0, page_info  # Default range from 0 to page_count

        for i in range(start, end):
            logger.info(f"[---- Reading page {i} ----]")
            yield self.get_page_blocks_from_dict(pdf=self.pdf, page_number=i, sort=sort)

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
            logger.debug(f"Opened PDF: {self.pdf_path}")
            return self.pdf
        return None

    def close(self) -> None:
        """Close the PDF file if open."""
        if self.pdf:
            try:
                self.pdf.close()
                logger.debug(f"Closed PDF: {self.pdf_path}")
            except Exception as e:
                logger.error(f"Error closing PDF: {e}")
            finally:
                self.pdf = None
