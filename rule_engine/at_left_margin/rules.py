from models import *
from rule_engine import Rule

class AtLeftMarginRule(Rule):
    pass

class SingleLineHeaderAtLeftMarginRule(AtLeftMarginRule):
    priority = 10

    def matches(self, ctx):
        return ctx.position_in_paragraph is PositionInParagraph.SINGLE_LINE

    def decide(self, ctx):
        return Decision(Action.SKIP, "Lone header text", self.name)

class EndParagraphAtLeftMarginRule(Rule):
    priority = 20

    def matches(self, ctx):
        return (ctx.margin_position is MarginPosition.AT and
                ctx.region is not VerticalRegion.FOOTER and
                ctx.position_in_paragraph not in (
                    PositionInParagraph.START,
                    PositionInParagraph.SINGLE_LINE,
                    PositionInParagraph.MIDDLE))

    def decide(self, ctx):
        return Decision(Action.COLLECT, "End of paragraph", self.name)

class FallbackAtLeftMarginRule(AtLeftMarginRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision(Action.UNHANDLED, "Text at left margin", self.name)


