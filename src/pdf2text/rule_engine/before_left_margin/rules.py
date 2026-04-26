from src.pdf2text.models import *
from src.pdf2text.rule_engine import Rule

class FooterBeforeLeftMarginRule(Rule):
    priority = 10

    def matches(self, ctx):
        return ctx.region is VerticalRegion.FOOTER

    def decide(self, ctx):
        return Decision.skip("Footer before left margin", self.name)

class HeadingBeforeLeftMarginRule(Rule):
    priority = 20

    def matches(self, ctx):
        return (ctx.region is VerticalRegion.BODY and
                ctx.font_name is not FontName.MAIN)

    def decide(self, ctx):
        return Decision.skip("Heading before left margin", self.name)

class FallbackBeforeLeftMarginRule(Rule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Text before left margin", self.name)


