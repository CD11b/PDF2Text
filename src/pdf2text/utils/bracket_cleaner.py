import logging
from src.pdf2text.models.layout.span import Span


from dataclasses import dataclass

@dataclass
class BracketCleanerContext:
    multipage_open: str | None = None
    open: str | None = None
    close: str | None = None

logger = logging.getLogger(__name__)

class BracketCleaner:

    def __init__(self, context: BracketCleanerContext):
        self.context = context

    def prioritized_pairs(self):

        pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}

        if self.context.multipage_open:
            yield self.context.multipage_open, pairs[self.context.multipage_open]

        for open, close in pairs.items():
            if open != self.context.multipage_open:
                yield open, close

    def partition_by_brackets(self, text):

        before_open, _, _ = text.partition(self.context.open)
        _, _, after_close = text.partition(self.context.close)

        return before_open, after_close

    def clean_and_join(self, text):

        before_open, after_close = self.partition_by_brackets(text)

        if self.context.close in before_open:  # Author typo: hanging close
            before_typo, _, after_typo = before_open.partition(self.context.close)
            before_open = before_typo + after_typo
            _, _, after_close = after_close.partition(self.context.close)

        return before_open.rstrip() + after_close

    def close_multipage_bracket(self, text):

        _, after_close = self.partition_by_brackets(text)
        self.context.multipage_open = None
        return after_close.lstrip()

    def handle_multiline_bracket(self, text, spans):
        buffer_lines = [text]
        found_close = False
        consumed = 0

        for span in spans[1:]:
            buffer_lines.append(span.text)
            consumed += 1
            if self.context.close in span.text:
                found_close = True
                break

        if found_close:
            logger.debug(f"Found open and close brackets across multiple lines: {text} ... {buffer_lines[-1]}")
            block_text = "\n".join(buffer_lines)
            cleaned_text = self.clean_and_join(block_text)
            if self.context.multipage_open and self.context.open == self.context.multipage_open:
                self.context.multipage_open = None
        else:
            logger.debug(f"Found hanging open bracket: {text}")
            self.context.multipage_open = self.context.open
            cleaned_text = text.partition(self.context.open)[0].rstrip()

        return cleaned_text, consumed


    def clean_brackets(self, spans: list[Span]) -> list[Span]:

        result = []
        i = 0
        j = 0

        while i < len(spans):
            text_buffer = spans[i].text
            for self.context.open, self.context.close in self.prioritized_pairs():
                while True:
                    if self.context.multipage_open and self.context.close in text_buffer:
                        text_buffer = self.close_multipage_bracket(text_buffer)

                    elif self.context.open in text_buffer and self.context.close in text_buffer:
                        text_buffer = self.clean_and_join(text_buffer)

                    elif self.context.open in text_buffer:
                        text_buffer, consumed = self.handle_multiline_bracket(text_buffer, spans[i:])
                        j += consumed

                    else:
                        break

            if spans[i].text == text_buffer:
                result.append(spans[i])
            else:
                result.append(spans[i].with_text(text_buffer))

            i += 1 + j
            j = 0

        return result
