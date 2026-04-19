from models import *
from rule_engine import Rule

class ContinuousParagraphRule(Rule):
    pass

class ContinuousParagraphMainFontRule(ContinuousParagraphRule):
    priority = 10

    def matches(self, ctx):
        return ctx.font_size is FontSize.MAIN

    def decide(self, ctx):
        return Decision.collect("Continued Paragraph", self.name)

class ContinuousParagraphMultiLineTitleRule(ContinuousParagraphRule):
    priority = 20

    def matches(self, ctx):
        return ctx.font_size is FontSize.LARGE

    def decide(self, ctx):
        return Decision.skip("Multi-line Title", self.name)

class FallbackContinuousParagraphRule(ContinuousParagraphRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Continuous Paragraph Text", self.name)
