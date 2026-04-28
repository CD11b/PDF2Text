import logging
from src.pdf2text.models.layout.span import Span


from dataclasses import dataclass

@dataclass
class BracketCleanerContext:
    multipage_open: str | None = None
    open_b: str | None = None
    close_b: str | None = None

logger = logging.getLogger(__name__)

class BracketCleaner:

    def __init__(self, context: BracketCleanerContext):
        self.context = context

    def prioritized_pairs(self, pairs):

        if self.context.multipage_open:
            yield self.context.multipage_open, pairs[self.context.multipage_open]

        for open_b, close_b in pairs.items():
            if open_b != self.context.multipage_open:
                yield open_b, close_b

    def partition_by_brackets(self, text):

        before_open, _, _ = text.partition(self.context.open_b)
        _, _, after_close = text.partition(self.context.close_b)

        return before_open, after_close

    def clean_and_join(self, text):

        before_open, after_close = self.partition_by_brackets(text)

        if self.context.close_b in before_open:  # Author typo: hanging close
            before_typo, _, after_typo = before_open.partition(self.context.close_b)
            before_open = before_typo + after_typo
            _, _, after_close = after_close.partition(self.context.close_b)

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
            if self.context.close_b in span.text:
                found_close = True
                break

        if found_close:
            logger.debug(f"Found open and close brackets across multiple lines: {text} ... {buffer_lines[-1]}")
            block_text = "\n".join(buffer_lines)
            cleaned_text = self.clean_and_join(block_text)
            if self.context.multipage_open and self.context.open_b == self.context.multipage_open:
                self.context.multipage_open = None
        else:
            logger.debug(f"Found hanging open bracket: {text}")
            self.context.multipage_open = self.context.open_b
            cleaned_text = text.partition(self.context.open_b)[0].rstrip()

        return cleaned_text, consumed

    @staticmethod
    def identify_pairs(spans):
        pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}
        found = {}

        chars = set(''.join(span.text.lower() for span in spans))

        for open_b, close_b in pairs.items():
            if open_b in chars or close_b in chars:
                found[open_b] = close_b

        return found

    def clean_brackets(self, spans: list[Span]) -> list[Span]:

        pairs = self.identify_pairs(spans)

        result = []
        i = 0
        j = 0

        while i < len(spans):
            text_buffer = spans[i].text
            for self.context.open_b, self.context.close_b in self.prioritized_pairs(pairs):
                while True:
                    if self.context.multipage_open and self.context.close_b in text_buffer:
                        text_buffer = self.close_multipage_bracket(text_buffer)

                    elif self.context.open_b in text_buffer and self.context.close_b in text_buffer:
                        text_buffer = self.clean_and_join(text_buffer)

                    elif self.context.open_b in text_buffer:
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
            self.context.open_b = self.context.close_b = None

        return result
