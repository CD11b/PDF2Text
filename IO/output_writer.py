import os
import re
import pymupdf
from typing import Optional

class OutputWriter:
    output_path: Optional[str]

    def __init__(self) -> None:
        self.output_path = None

    def set_output_path(self, pdf: pymupdf.Document, pdf_path: str) -> str:
        """
        Sets the output path for the text file based on PDF metadata or filename.
        """
        os.makedirs("../generated", exist_ok=True)

        title = pdf.metadata.get('title', '')
        if len(title) > 1:
            sanitized_title = re.sub(r'[<>:"/\\|?*\n\r\t;]', '_', title).strip()
            self.output_path = f"./generated/{sanitized_title}.txt"
        else:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            self.output_path = f"./generated/{base_name}.txt"

        return self.output_path

    def write(self, mode: str, text: Optional[str] = None) -> None:
        """
        Writes text to the output file. If text is None, opens the file but writes nothing.
        """
        if self.output_path is None:
            raise ValueError("Output path is not set. Call set_output_path() first.")

        with open(self.output_path, mode, encoding='utf-8') as f:
            if text is not None:
                f.write(text)
