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
    def create(cls, layout, span, next_span, result):

        line_start_x = span[0].start_x
        line_start_y = span[0].start_y
        line_end_x = span[-1].end_x
        previous_group = result[-1] if len(result) > 0 else None

        return cls(
            text_content=layout.line_text_content.classify(context=(span, previous_group, next_span)),
            position_in_paragraph=layout.line_position.classify(context=(line_start_y, previous_group, next_span)),
            indentation=layout.line_indentation.classify(context=(line_start_x, previous_group, next_span)),
            region=layout.line_region.classify(span),
            margin_position=layout.margin_position.classify(span),
            character_count=layout.line_character_count.classify(span),
            font_name=layout.line_font_name.classify(span),
            font_size=layout.line_font_size.classify(span),
            split_span=layout.line_split_span.classify(context=(line_start_y, line_end_x, next_span)),
            last_line=span is layout.column.spans[-1]
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