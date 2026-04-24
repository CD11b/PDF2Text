from src.pdf2text.models import *
from src.pdf2text.rule_engine import Rule

class IndentedLineRule(Rule):
    pass

class IndentedBlockLastLineRule(IndentedLineRule):
    priority = 10

    def matches(self, ctx):
        return ctx.indentation is LineIndentation.INDENTED_BLOCK and ctx.last_line is True

    def decide(self, ctx):
        return Decision.collect("Last Line is Continued Indented Paragraph", self.name)

class IndentedBlockParagraphRule(IndentedLineRule):
    priority = 20

    def matches(self, ctx):
        return ctx.indentation is LineIndentation.INDENTED_BLOCK and ctx.position_in_paragraph is not PositionInParagraph.SINGLE_LINE

    def decide(self, ctx):
        return Decision.collect("Indented Block", self.name)

class IndentedMainFontRule(IndentedLineRule):
    priority = 30

    def matches(self, ctx):
        return ctx.indentation is LineIndentation.INDENTED and ctx.font_name is FontName.MAIN

    def decide(self, ctx):
        return Decision.collect("Indented Paragraph", self.name)

class SplitSpanIndentationLineRule(IndentedLineRule):
    priority = 40

    def matches(self, ctx):
        return ctx.split_span is True

    def decide(self, ctx):
        return Decision.collect("Span mistakenly split into two lines due to OCR fuzziness", self.name)

class ParagraphStartIndentedRule(IndentedLineRule):
    priority = 50

    def matches(self, ctx):
        return (ctx.indentation is LineIndentation.LARGE_INDENTATION and
                ctx.position_in_paragraph in (PositionInParagraph.START, PositionInParagraph.MIDDLE) and
                ctx.character_count is CharacterCount.HIGH)

    def decide(self, ctx):
        return Decision.collect("Start of paragraph is indented", self.name)

class EpigraphAuthorRule(IndentedLineRule):
    priority = 60

    def matches(self, ctx):
        return (ctx.indentation is LineIndentation.LARGE_INDENTATION and
                ctx.position_in_paragraph is PositionInParagraph.END and
                ctx.character_count is CharacterCount.LOW)

    def decide(self, ctx):
        return Decision.skip("Source/author of epigraph", self.name)

class TitlePageRule(IndentedLineRule):
    priority = 60

    def matches(self, ctx):
        return (ctx.indentation in (LineIndentation.LARGE_INDENTATION, LineIndentation.INDENTED_BLOCK) and
                ctx.font_size is FontSize.LARGE and
                ctx.character_count is CharacterCount.LOW)

    def decide(self, ctx):
        return Decision.skip("Title/sub-title", self.name)

class ItalicWordMidLineRule(IndentedLineRule):
    priority = 70

    def matches(self, ctx):
        return (ctx.indentation is LineIndentation.LARGE_INDENTATION and
                ctx.font_size is FontSize.MAIN and
                ctx.font_name is FontName.MAIN_ITALIC)

    def decide(self, ctx):
        return Decision.collect("Italic word with main font found within sentence", self.name)

class BoldWordMidLineRule(IndentedLineRule):
    priority = 80

    def matches(self, ctx):
        return (ctx.indentation is LineIndentation.LARGE_INDENTATION and
                ctx.font_size is FontSize.MAIN and
                ctx.font_name is FontName.MAIN_BOLD)

    def decide(self, ctx):
        return Decision.collect("Bold word with main font found within sentence", self.name)

class FallbackIndentedRule(IndentedLineRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Unhandled Indented Line", self.name)
