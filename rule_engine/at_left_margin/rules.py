from models import *
from rule_engine import Rule

class AtLeftMarginRule(Rule):
    pass

class SingleLineHeaderAtLeftMarginRule(AtLeftMarginRule):
    priority = 10

    def matches(self, ctx):
        return ctx.position_in_paragraph is PositionInParagraph.SINGLE_LINE

    def decide(self, ctx):
        return Decision.skip("Lone header text", self.name)

class EndParagraphAtLeftMarginRule(Rule):
    priority = 20


class FallbackAtLeftMarginRule(AtLeftMarginRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Text at left margin", self.name)


