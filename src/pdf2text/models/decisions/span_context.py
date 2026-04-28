from dataclasses import dataclass
from src.pdf2text.models.decisions.context_types import *

@dataclass(slots=True, frozen=True)
class SpanContext:
    text_content: TextContent
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
        line_end_x = line_group[-1].end_x
        next_group = groups_iter.peek()
        previous_group = result[-1] if len(result) > 0 else None

        return cls(
            text_content=layout.line_text_content.classify(context=(line_group, previous_group, next_group)),
            position_in_paragraph=layout.line_position.classify(context=(line_start_y, previous_group, next_group)),
            indentation=layout.line_indentation.classify(context=(line_start_x, previous_group, next_group)),
            region=layout.line_region.classify(line_group),
            margin_position=layout.margin_position.classify(line_group),
            character_count=layout.line_character_count.classify(line_group),
            font_name=layout.line_font_name.classify(line_group),
            font_size=layout.line_font_size.classify(line_group),
            split_span=layout.line_split_span.classify(context=(line_start_y, line_end_x, next_group)),
            last_line=line_group is layout.column.spans[-1]
        )

    def __repr__(self):
        return (f"{self.text_content}, "
                f"{self.position_in_paragraph},"
                f" {self.indentation},"
                f" {self.region},"
                f" {self.margin_position},"
                f" {self.character_count},"
                f" {self.font_name}/{self.font_size},"
                f" split_span={self.split_span},"
                f" last_line={self.last_line}")