from src.pdf2text.models.decisions.context_types import TextContent, FontSize

class PageFilter:

    def __init__(self, collected_lines):
        self.collected_lines = collected_lines

    def filter_references(self):
        first_idx = None
        last_idx = None

        for i, collected_line in enumerate(self.collected_lines):
            if collected_line.context.text_content in (TextContent.URL_DOI, TextContent.REFERENCE_BLOCK):
                if first_idx is None:
                    first_idx = i
                last_idx = i

        if first_idx is not None:
            cleaned_lines = [*self.collected_lines[:first_idx], *self.collected_lines[last_idx + 1:]]

            first_idx = last_idx = None
            for i, collected_line in enumerate(self.collected_lines):
                if collected_line.context.font_size in (FontSize.MAIN_PAGE, FontSize.MAIN_ELSEWHERE):
                    if first_idx is None:
                        first_idx = i
                    last_idx = i
            if first_idx is not None:
                cleaned_lines = [*self.collected_lines[:first_idx], *self.collected_lines[last_idx + 1:]]

            return cleaned_lines

        return self.collected_lines
