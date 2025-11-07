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

    def __post_init__(self):
        object.__setattr__(self, "font_size", round(self.font_size))
        object.__setattr__(self, "start_x", round(self.start_x))
        object.__setattr__(self, "start_y", round(self.start_y))
        object.__setattr__(self, "end_x", round(self.end_x))

    def with_text(self, new_text: str) -> "StyledLine":
        """Return a new StyledLine with updated text but identical styling and geometry."""
        return replace(self, text=new_text)
