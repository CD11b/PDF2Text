from src.pdf2text.models import *
from src.pdf2text.rule_engine import Rule

class FooterRegionRule(Rule):
    pass

class FooterRegionBodyParagraphRule(FooterRegionRule):
    priority = 10

    def matches(self, ctx):
        return (ctx.position_in_paragraph in [PositionInParagraph.MIDDLE, PositionInParagraph.END]
        and ctx.indentation in [LineIndentation.INDENTED_BLOCK, LineIndentation.NONE])

    def decide(self, ctx):
        return Decision.collect("Body Paragraph at Footer Region", self.name)

class FooterRegionLoneIndentedTextRule(FooterRegionRule):
    priority = 40

    def matches(self, ctx):
        return (ctx.position_in_paragraph in [PositionInParagraph.MIDDLE, PositionInParagraph.END]
                and ctx.indentation in [LineIndentation.INDENTED, LineIndentation.LARGE_INDENTATION])

    def decide(self, ctx):
        return Decision.skip("Lone indented text at Footer Region", self.name)

class FooterRegionHighCharacterCountLineRule(FooterRegionRule):
    priority = 30

    def matches(self, ctx):
        return ctx.character_count is CharacterCount.HIGH

    def decide(self, ctx):
        return Decision.collect("High character count line at Footer", self.name) # Would also collect citations

class FallbackFooterRegionRule(FooterRegionRule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Footer Region Text", self.name)
