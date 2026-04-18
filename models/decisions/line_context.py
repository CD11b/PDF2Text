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

        line_start_x = line_group[0].start_x
        line_start_y = line_group[0].start_y
        next_group = groups_iter.peek()
        previous_start_x = result[-1].start_x if len(result) > 1 else None
        next_start_x = next_group[0].start_x if next_group else None
        next_start_y = next_group[0].start_y if next_group else None

        return cls(
            line_group=line_group,
            position_in_paragraph=layout.paragraph_type.classify_position(line_start_y, previous_start_x, next_start_y),
            indentation=layout.paragraph_type.classify_indentation(line_start_x, previous_start_x, next_start_x),
            region=layout.get_line_region(line_group),
            margin_position=layout.get_line_position(line_group),
            density=layout.get_line_density(line_group),
            font_name=layout.get_font_name(line_group),
            font_size=layout.get_font_size(line_group),
            is_continuous=layout.is_split_span(line_group, groups_iter),
            is_last_line=layout.is_last_line(line_group)
        )
