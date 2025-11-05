from dataclasses import dataclass

@dataclass
class StyledLine:
    text: str
    font_size: float
    font_name: str
    start_x: float
    start_y: float
    end_x: float

    def __post_init__(self):
        self.font_size = round(self.font_size)
        self.start_x = round(self.start_x)
        self.start_y = round(self.start_y)
        self.end_x = round(self.end_x)

