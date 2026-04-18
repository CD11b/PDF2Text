from dataclasses import dataclass
from .context_types import *

@dataclass
class LineContext:
    line_group: list
    position_in_paragraph: PositionInParagraph
    indentation: LineIndentation
    region: VerticalRegion
    margin_position: MarginPosition
    density: Density
    font_name: FontName
    font_size: FontSize
    is_continuous: bool
    is_last_line: bool

    @classmethod
    def create(cls, layout, line_group, groups_iter, result):
        return cls(
            line_group=line_group,
            position_in_paragraph=layout.get_position_in_paragraph(line_group, groups_iter, result),
            indentation=layout.get_line_indentation(line_group, groups_iter, result),
            region=layout.get_line_region(line_group),
            margin_position=layout.get_line_position(line_group),
            density=layout.get_line_density(line_group),
            font_name=layout.get_font_name(line_group),
            font_size=layout.get_font_size(line_group),
            is_continuous=layout.is_continuous_line(line_group, groups_iter),
            is_last_line=layout.is_last_line(line_group)
        )
