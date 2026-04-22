from __future__ import annotations
from typing import Generator, List, Dict, Any
import logging
import pymupdf

from models import StyledLine

logger = logging.getLogger(__name__)

class DocumentAnalysis:
    """Utility class for extracting and iterating over styled PDF text blocks."""

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
    def iter_pdf_styling_from_blocks(page_blocks: List[Dict[str, Any]]) -> Generator[StyledLine, None, None]:
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
                            yield StyledLine(text=text,
                                             font_size=float(span["size"]),
                                             font_name=str(span["font"]),
                                             start_x=float(span["origin"][0]),
                                             start_y=float(span["origin"][1]),
                                             end_x=float(span["bbox"][2]))

        except Exception as e:
            logger.exception(f"Error reading styles from PDF blocks: {e}")
            raise
