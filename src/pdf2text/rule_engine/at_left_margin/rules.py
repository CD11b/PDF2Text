from src.pdf2text.models import *
from src.pdf2text.rule_engine import Rule

class SingleEmphasizedLineRule(Rule):
    priority = 10

    def matches(self, ctx):
        return (ctx.position_in_paragraph is PositionInParagraph.SINGLE_LINE and
                ctx.character_count is CharacterCount.HIGH and
                ctx.font_size in (FontSize.MAIN_DOCUMENT, FontSize.MAIN_PAGE, FontSize.MAIN_ELSEWHERE, FontSize.IN_RANGE_ELSEWHERE))

    def decide(self, ctx):
        return Decision.collect("Single line that's part of main body", self.name)

class BoldSectionHeaderAtLeftMarginRule(Rule):
    priority = 20

    def matches(self, ctx):
        return (ctx.position_in_paragraph is PositionInParagraph.SINGLE_LINE and
                ctx.character_count is CharacterCount.LOW and
                ctx.font_size is FontSize.LARGE and
                ctx.font_name is FontName.MAIN_BOLD)

    def decide(self, ctx):
        return Decision.skip("Bold section header", self.name)


class FallbackAtLeftMarginRule(Rule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Text at left margin", self.name)


