from dataclasses import dataclass
from .context_types import *

@dataclass
class LineContext:
    line_group: list
    position_in_paragraph: PositionInParagraph
    indentation: LineIndentation
    region: VerticalRegion
    margin_position: MarginPosition
    character_count: CharacterCount
    font_name: FontName
    font_size: FontSize
    split_span: bool
    last_line: bool

    @classmethod
    def create(cls, layout, line_group, groups_iter, result):

        line_start_x = line_group[0].start_x
        line_start_y = line_group[0].start_y
        next_group = groups_iter.peek()
        previous_start_x = result[-1].start_x if len(result) >= 1 else None
        previous_start_y = result[-1].start_y if len(result) >= 1 else None
        next_start_x = next_group[0].start_x if next_group else None
        next_start_y = next_group[0].start_y if next_group else None

        return cls(
            line_group=line_group,
            position_in_paragraph=layout.line_position.classify(context=(line_start_y, previous_start_y, next_start_y)),
            indentation=layout.line_indentation.classify(context=(line_start_x, previous_start_x, next_start_x)),
            region=layout.line_region.classify(line_group),
            margin_position=layout.margin_position.classify(line_group),
            character_count=layout.line_character_count.classify(line_group),
            font_name=layout.line_font_name.classify(line_group),
            font_size=layout.line_font_size.classify(line_group),
            split_span=layout.is_split_span(line_group, next_group),
            last_line=layout.is_last_line(line_group)
        )

    def __repr__(self):
        return (f"{self.position_in_paragraph},"
                f" {self.indentation},"
                f" {self.region},"
                f" {self.margin_position},"
                f" {self.character_count},"
                f" {self.font_name}/{self.font_size},"
                f" split_span={self.split_span},"
                f" last_line={self.last_line})")