from models import *
from rule_engine import Rule

class HeaderRegionRule(Rule):
    pass

class BodyParagraphAtHeaderRegionRule(HeaderRegionRule):
    priority = 10

    def matches(self, ctx, layout, groups_iter):
        return ctx.position_in_paragraph in (PositionInParagraph.MIDDLE, PositionInParagraph.END)

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Body paragraph at header", self.name)

class DenseLineAtHeaderRegionRule(HeaderRegionRule):
    priority = 20

    def matches(self, ctx, layout, groups_iter):
        return ctx.density is Density.DENSE

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Dense line at header", self.name)

class FallbackHeaderRegionRule(HeaderRegionRule):
    priority = 999

    def matches(self, ctx, layout, groups_iter):
        return True

    def decide(self, ctx):
        return Decision(Action.UNHANDLED, "Header Region Text", self.name)