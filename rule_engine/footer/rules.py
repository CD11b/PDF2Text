from models import *
from rule_engine import Rule

class FooterRegionRule(Rule):
    pass

class FooterRegionBodyParagraphRule(FooterRegionRule):
    priority = 10

    def matches(self, ctx, layout, groups_iter):
        return (ctx.position_in_paragraph in [PositionInParagraph.BODY, PositionInParagraph.END]
        and ctx.indentation in [LineIndentation.INDENTED_BLOCK, LineIndentation.NONE])

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Body Paragraph at Footer Region", self.name)

class FooterRegionLoneIndentedTextRule(FooterRegionRule):
    priority = 20

    def matches(self, ctx, layout, groups_iter):
        return (ctx.position_in_paragraph in [PositionInParagraph.BODY, PositionInParagraph.END]
                and ctx.indentation in [LineIndentation.INDENTED, LineIndentation.LARGE_INDENTATION])

    def decide(self, ctx):
        return Decision(Action.SKIP, "Lone indented text at Footer Region", self.name)

class FooterRegionDenseLineRule(FooterRegionRule):
    priority = 30

    def matches(self, ctx, layout, groups_iter):
        return ctx.density is Density.DENSE

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Dense line at Footer", self.name) # Would also collect citations

class FallbackFooterRegionRule(FooterRegionRule):
    priority = 999

    def matches(self, ctx, layout, groups_iter):
        return True

    def decide(self, ctx):
        return Decision(Action.UNHANDLED, "Footer Region Text", self.name)
