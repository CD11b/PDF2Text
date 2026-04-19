import logging, unicodedata, re

logger = logging.getLogger(__name__)

class CleanText:

    BROKEN_WORD_PATTERN = re.compile(r'\w-\s*$')
    HYPHEN_END_PATTERN = re.compile(r'-\s*$')
    PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')
    COMMON_OCR_ERRORS = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "“": "\"",
        "”": "\"",
        "‘": "'",
        "’": "'",
        "|": "I"
    }

    @staticmethod
    def clean_page_numbers(filtered_lines) -> list:

        logger.debug(f"Cleaning page numbers")

        return [line for line in filtered_lines if not CleanText.PAGE_NUMBER_PATTERN.fullmatch(line.text)]

    @staticmethod
    def join_broken_sentences(filtered_lines) -> str:

        logger.debug(f"Joining broken sentences.")

        def merge_broken_lines(lines):

            line_iter = iter(lines)

            for line in line_iter:
                text = line.text

                while CleanText.BROKEN_WORD_PATTERN.search(text):
                    try:
                        next_line = next(line_iter)
                        text = CleanText.HYPHEN_END_PATTERN.sub('', text) + next_line.text.lstrip()
                    except StopIteration:
                        break

                yield text

        return " ".join(merge_broken_lines(filtered_lines))

    @staticmethod
    def normalize_unicode(text):
        compatibility_mapped = unicodedata.normalize('NFKC', text)
        decomposed = unicodedata.normalize('NFD', compatibility_mapped)

        return ''.join(c for c in decomposed if not unicodedata.combining(c))

    @staticmethod
    def correct_ocr_errors(text):
        for bad, good in CleanText.COMMON_OCR_ERRORS.items():
            text = text.replace(bad, good)

        return text