from models import *
from rule_engine import Rule

class IndentedLineRule(Rule):
    pass

class IndentedBlockLastLineRule(IndentedLineRule):
    priority = 10

    def matches(self, ctx, layout, groups_iter):
        return ctx.indentation is LineIndentation.INDENTED_BLOCK and layout.is_last_line(ctx.line_group)

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Last Line is Continued Indented Paragraph", self.name)

class IndentedBlockParagraphRule(IndentedLineRule):
    priority = 20

    def matches(self, ctx, layout, groups_iter):
        return ctx.indentation is LineIndentation.INDENTED_BLOCK and ctx.position_in_paragraph is not PositionInParagraph.SINGLE_LINE

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Indented Block", self.name)

class IndentedMainFontRule(IndentedLineRule):
    priority = 30

    def matches(self, ctx, layout, groups_iter):
        return ctx.indentation is LineIndentation.INDENTED and ctx.font_name is FontName.MAIN

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Indented Paragraph", self.name)

class OCRFooterRule(IndentedLineRule):
    priority = 40

    def matches(self, ctx, layout, groups_iter):
        return layout.page.ocr and ctx.region is VerticalRegion.FOOTER

    def decide(self, ctx):
        return Decision(Action.SKIP, "Indented Line @ Footer", self.name,)

class OCRContinuousLineRule(IndentedLineRule):
    priority = 50

    def matches(self, ctx, layout, groups_iter):
        return layout.page.ocr and layout.is_continuous_line(ctx.line_group, groups_iter)

    def decide(self, ctx):
        return Decision(Action.COLLECT, "OCR - Indented Line Following Dominant Word Gap", self.name)

class FallbackIndentedRule(IndentedLineRule):
    priority = 999

    def matches(self, ctx, layout, groups_iter):
        return True

    def decide(self, ctx):
        return Decision(Action.UNHANDLED, "Unhandled Indented Line", self.name)
