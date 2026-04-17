from enum import Enum, auto

class LineIndentation(Enum):
    INDENTED = auto()
    NONE = auto()
    INDENTED_BLOCK = auto()
    LARGE_INDENTATION = auto()

class PositionInParagraph(Enum):
    START = auto()
    BODY = auto()
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

class Density(Enum):
    DENSE = auto()
    SPARSE = auto()

class FontName(Enum):
    MAIN = auto()
    OTHER = auto()

class FontSize(Enum):
    MAIN = auto()
    LARGE = auto()
    SMALL = auto()