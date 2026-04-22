from models import *
from rule_engine import Rule

class AtLeftMarginRule(Rule):
    pass

class SingleEmphasizedLineRule(AtLeftMarginRule):
    priority = 10

    def matches(self, ctx):
        return (ctx.position_in_paragraph is PositionInParagraph.SINGLE_LINE and
                ctx.character_count is CharacterCount.HIGH and
                ctx.font_size is FontSize.MAIN)

    def decide(self, ctx):
        return Decision.collect("Single line that's part of main body", self.name)


class FallbackAtLeftMarginRule(AtLeftMarginRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Text at left margin", self.name)


