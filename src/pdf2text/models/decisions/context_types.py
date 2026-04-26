from enum import Enum, auto

class LineIndentation(Enum):
    INDENTED = auto()
    NONE = auto()
    INDENTED_BLOCK = auto()
    LARGE_INDENTATION = auto()

class PositionInParagraph(Enum):
    START = auto()
    MIDDLE = auto()
    END = auto()
    SINGLE_LINE = auto()

class MarginPosition(Enum):
    BEFORE = auto()
    AT = auto()
    AFTER = auto()

class VerticalRegion(Enum):
    HEADER = auto()
    BODY = auto()
    FOOTER = auto()

class CharacterCount(Enum):
    HIGH = auto()
    LOW = auto()

class FontName(Enum):
    MAIN = auto()
    MAIN_ITALIC = auto()
    MAIN_BOLD = auto()
    OTHER = auto()

class FontSize(Enum):
    MAIN = auto()
    LARGE = auto()
    SMALL = auto()

class TextContent(Enum):
    BODY_TEXT = auto()
    URL = auto()