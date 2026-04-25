from dataclasses import dataclass, replace

@dataclass(frozen=True)
class StyledLine:
    """Represents a single styled line of text from a PDF."""
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

    def with_text(self, new_text: str) -> "StyledLine":
        """Return a new StyledLine with updated text but identical styling and geometry."""
        return replace(self, text=new_text)
