import os
import re
import pymupdf
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class OutputWriter:
    output_path: Optional[str]

    def __init__(self) -> None:
        self.output_path = None

    def set_output_path(self, pdf: pymupdf.Document, pdf_path: str, output_path: str | None, output_dir: str) -> str:
        """
        Determines output file path.

        Priority:
        1. Explicit output_path (file path)
        2. output_dir + derived filename
        """

        def sanitize(name: str) -> str:
            return re.sub(r'[<>:"/\\|?*\n\r\t;]', '_', name).strip()

        # Case 1: user provided full output file path
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            self.output_path = output_path
            return self.output_path

        # Case 2: derive filename from PDF metadata or file name
        os.makedirs(output_dir, exist_ok=True)

        title = (pdf.metadata or {}).get("title", "")
        if title and len(title.strip()) > 1:
            filename = sanitize(title) + ".txt"
        else:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            filename = sanitize(base_name) + ".txt"

        self.output_path = os.path.join(output_dir, filename)
        return self.output_path

    def write(self, mode: str, text: Optional[str] = None) -> None:
        """
        Writes text to the output file. If text is None, opens the file but writes nothing.
        """
        if self.output_path is None:
            raise ValueError("Output path is not set. Call set_output_path() first.")

        logger.debug(f"Writing to: {self.output_path}")
        with open(self.output_path, mode, encoding='utf-8') as f:
            if text is not None:
                f.write(text)
