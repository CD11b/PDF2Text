import logging, unicodedata, re
from src.pdf2text.models.layout.span import Span, ClassifiedSpan

logger = logging.getLogger(__name__)

PAGE_NUMBER_PATTERN = re.compile(r'\s*\d+\s*')
COMMON_OCR_ERRORS = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "“": "\"", "”": "\"", "‘": "'", "’": "'", "|": "I"})

def remove_page_number_lines(collected_lines: list[ClassifiedSpan]) -> list[Span]:
    """
    Remove lines that appear to be standalone page numbers.

    A line is considered a page number if it consists only of digits
    (optionally surrounded by whitespace).

    Args:
        lines: List of StyledLines (extracted from page).

    Returns:
        A filtered list of StyledLine objects with page number lines removed.
    """
    logger.debug("Cleaning page numbers from %d lines", len(collected_lines))

    lines = [collected_line.span for collected_line in collected_lines]
    return [line for line in lines if not PAGE_NUMBER_PATTERN.fullmatch(line.text)]

def join_lines(lines: list[Span], clean_hyphens: bool = True) -> str:
    """
    Join extracted lines into a single text string.

    Optionally (default = True) merges words split across lines using trailing hyphens.

    Args:
        lines: List of StyledLine objects.
        clean_hyphens: If True, merges words broken by hyphenation at line ends.

    Returns:
        A single string representing the joined and reconstructed text.
    """
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
    """
    Correct common OCR character misrecognitions using a translation table.

    Examples include:
        - Ligatures like 'ﬁ' → 'fi'
        - Misread quotation marks
        - Pipe characters interpreted as capital 'I'

    Args:
        text: Raw OCR text.

    Returns:
        Text with common OCR errors corrected.
    """
    return text.translate(COMMON_OCR_ERRORS)

def normalize_unicode(text: str) -> str:
    """
    Normalize text using Unicode NFKC normalization.

    This resolves compatibility issues such as:
        - Full-width characters → standard width
        - Ligature normalization (when not already handled elsewhere)

    Args:
        text: Input string.

    Returns:
        Unicode-normalized string.
    """
    return unicodedata.normalize("NFKC", text)

def strip_accents(text: str) -> str:
    """
    Remove diacritical marks (accents) from characters.

    This converts characters like:
        - 'é' → 'e'
        - 'ñ' → 'n'

    Args:
        text: Unicode string.

    Returns:
        Accent-free version of the input string.
    """
    decomposed = unicodedata.normalize("NFD", text)
    return ''.join(c for c in decomposed if not unicodedata.combining(c))

def normalize_text(text: str, correct_ocr: bool = False) -> str:
    """
    Normalize text through Unicode normalization and optional OCR cleanup.

    Processing steps:
        1. Optionally (predetermined) apply OCR error corrections
        2. Normalize Unicode (NFKC)
        3. Strip accents

    Args:
        text: Input text.
        correct_ocr: Whether to apply OCR-specific character corrections.

    Returns:
        Fully normalized text string.
    """
    if correct_ocr:
        text = correct_ocr_errors(text)
    text = normalize_unicode(text)
    text = strip_accents(text)
    return text