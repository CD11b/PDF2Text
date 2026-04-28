import logging
from src.pdf2text.models.layout.span import Span


from dataclasses import dataclass

@dataclass(slots=True)
class BracketCleanerContext:
    multipage_open_b: str | None = None

logger = logging.getLogger(__name__)

class BracketCleaner:

    def __init__(self, context: BracketCleanerContext):
        self.context = context

    @staticmethod
    def select_pairs(spans):
        pairs = {'(': ')', '[': ']', '{': '}', '<': '>'}
        found = {}

        chars = set(''.join(span.text.lower() for span in spans))

        for open_b, close_b in pairs.items():
            if open_b in chars or close_b in chars:
                found[open_b] = close_b

        return found

    @staticmethod
    def partition_by_brackets(text, open_b, close_b):

        before_open, _, _ = text.partition(open_b)
        _, _, after_close = text.partition(close_b)

        return before_open, after_close

    def prioritized_pairs(self, pairs):

        if self.context.multipage_open_b:
            yield self.context.multipage_open_b, pairs[self.context.multipage_open_b]

        for open_b, close_b in pairs.items():
            if open_b != self.context.multipage_open_b:
                yield open_b, close_b

    def clean_and_join(self, text, open_b, close_b):

        before_open, after_close = self.partition_by_brackets(text, open_b, close_b)

        if close_b in before_open:  # Author typo: hanging close
            before_typo, _, after_typo = before_open.partition(close_b)
            before_open = before_typo + after_typo
            _, _, after_close = after_close.partition(close_b)

        return before_open.rstrip() + after_close

    def close_multipage_bracket(self, text, open_b, close_b):

        _, after_close = self.partition_by_brackets(text, open_b, close_b)
        self.context.multipage_open_b = None
        return after_close.lstrip()

    def handle_multiline_bracket(self, text, spans, open_b, close_b):
        buffer_lines = [text]
        found_close = False
        consumed = 0

        for span in spans[1:]:
            buffer_lines.append(span.text)
            consumed += 1
            if close_b in span.text:
                found_close = True
                break

        if found_close:
            logger.debug(f"Found open and close brackets across multiple lines: {text} ... {buffer_lines[-1]}")
            block_text = "\n".join(buffer_lines)
            cleaned_text = self.clean_and_join(block_text, open_b, close_b)
            if self.context.multipage_open_b and open_b == self.context.multipage_open_b:
                self.context.multipage_open_b = None
        else:
            logger.debug(f"Found hanging open bracket: {text}")
            self.context.multipage_open_b = open_b
            cleaned_text = text.partition(open_b)[0].rstrip()

        return cleaned_text, consumed

    def clean_brackets(self, spans: list[Span]) -> list[Span]:

        pairs = self.select_pairs(spans)

        result = []
        i = 0
        total_consumed = 0

        while i < len(spans):
            text_buffer = spans[i].text
            for open_b, close_b in self.prioritized_pairs(pairs):
                while True:
                    if self.context.multipage_open_b and close_b in text_buffer:
                        text_buffer = self.close_multipage_bracket(text_buffer, open_b, close_b)

                    elif open_b in text_buffer and close_b in text_buffer:
                        text_buffer = self.clean_and_join(text_buffer, open_b, close_b)

                    elif open_b in text_buffer:
                        text_buffer, consumed = self.handle_multiline_bracket(text_buffer, spans[i:], open_b, close_b)
                        total_consumed += consumed

                    else:
                        break

            if spans[i].text == text_buffer:
                result.append(spans[i])
            else:
                result.append(spans[i].with_text(text_buffer))

            i += 1 + total_consumed
            total_consumed = 0

        return result
