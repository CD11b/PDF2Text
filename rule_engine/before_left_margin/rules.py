from models import *
from rule_engine import Rule

class BeforeLeftMarginRule(Rule):
    pass

class FooterBeforeLeftMarginRule(BeforeLeftMarginRule):
    priority = 10

    def matches(self, ctx):
        return ctx.region is VerticalRegion.FOOTER

    def decide(self, ctx):
        return Decision.collect("Footer before left margin", self.name) # Shouldn't this be skipped?

class HeadingBeforeLeftMarginRule(Rule):
    priority = 20

    def matches(self, ctx):
        return (ctx.region is VerticalRegion.BODY and
                ctx.font_name is not FontName.MAIN)

    def decide(self, ctx):
        return Decision.skip("Heading before left margin", self.name)

class FallbackBeforeLeftMarginRule(BeforeLeftMarginRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Text before left margin", self.name)


