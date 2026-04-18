from models import *
from rule_engine import Rule

class ContinuousParagraphRule(Rule):
    pass

class ContinuousParagraphMainFontRule(ContinuousParagraphRule):
    priority = 10

    def matches(self, ctx, layout, groups_iter):
        return ctx.font_size is FontSize.MAIN

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Continued Paragraph", self.name)

class ContinuousParagraphMultiLineTitleRule(ContinuousParagraphRule):
    priority = 20

    def matches(self, ctx, layout, groups_iter):
        return ctx.font_size is FontSize.Large

    def decide(self, ctx):
        return Decision(Action.COLLECT, "Multi-line Title", self.name)

class FallbackContinuousParagraphRule(ContinuousParagraphRule):
    priority = 999

    def matches(self, ctx, layout, groups_iter):
        return True

    def decide(self, ctx):
        return Decision(Action.UNHANDLED, "Continuous Paragraph Text", self.name)
