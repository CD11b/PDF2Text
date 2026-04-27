from dataclasses import dataclass, replace
from src.pdf2text.models.decisions import SpanContext

@dataclass(frozen=True)
class Span:
    """Represents a single span from a PDF."""
    text: str
    font_size: float
    font_name: str
    start_x: float
    start_y: float
    end_x: float

    @property
    def character_count(self):
        return len(self.text)

    @classmethod
    def create(cls, text, font_size, font_name, start_x, start_y, end_x):
        return cls(text, round(font_size), font_name, round(start_x), round(start_y), round(end_x))

    def with_text(self, new_text: str) -> "Span":
        """Return a new Span with updated text but identical styling information and geometry."""
        return replace(self, text=new_text)

@dataclass(frozen=True)
class ClassifiedSpan:
    span: Span
    context: SpanContext

    @classmethod
    def create(cls, line, ctx):
        return cls(line, ctx)

    def with_line(self, new_span: str) -> "ClassifiedSpan":
        """Return a new ClassifiedSpan with updated Span but identical context."""
        return replace(self, span=new_span)