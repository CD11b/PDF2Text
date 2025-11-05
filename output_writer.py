import os
import re
import pymupdf

class OutputWriter:
    def __init__(self):
        self.output_path = None

    def set_output_path(self, pdf: pymupdf.Document, pdf_path: str) -> str:

        os.makedirs("./generated", exist_ok=True)
        if len(pdf.metadata['title']) > 1:
            sanitized_title = re.sub(r'[<>:"/\\|?*\n\r\t;]', '_', pdf.metadata['title']).strip()
            self.output_path = f"./generated/{sanitized_title}.txt"

        else:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            self.output_path = f"./generated/{base_name}.txt"

        return self.output_path

    def write(self, mode: str, text: str | None = None):
        with open(self.output_path, mode, encoding='utf-8') as f:
            if text is not None:
                f.write(text)
