import logging, unicodedata, re
from models import StyledLine

logger = logging.getLogger(__name__)

PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')
COMMON_OCR_ERRORS = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "“": "\"", "”": "\"", "‘": "'", "’": "'", "|": "I"})

def remove_page_number_lines(lines: list[StyledLine]) -> list[StyledLine]:

    logger.debug("Cleaning page numbers from %d lines", len(lines))

    return [line for line in lines if not PAGE_NUMBER_PATTERN.fullmatch(line.text)]

def join_lines(lines: list[StyledLine], clean_hyphens: bool = True) -> str:

    result = []
    i = 0
    n = len(lines)

    while i < n:
        text = lines[i].text.rstrip()

        while clean_hyphens and text.endswith("-") and i + 1 < n:
            text = text[:-1] + lines[i + 1].text.lstrip()
            i += 1

        result.append(text.rstrip())
        i += 1

    logger.debug("Joined lines: %d to %d lines", len(lines), len(result))

    return " ".join(result)

def correct_ocr_errors(text: str) -> str:
    return text.translate(COMMON_OCR_ERRORS)

def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)

def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return ''.join(c for c in decomposed if not unicodedata.combining(c))

def normalize_text(text: str, correct_ocr: bool = False) -> str:
    if correct_ocr:
        text = correct_ocr_errors(text)
    text = normalize_unicode(text)
    text = strip_accents(text)
    return text