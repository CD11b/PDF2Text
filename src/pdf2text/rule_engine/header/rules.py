from src.pdf2text.models import *
from src.pdf2text.rule_engine import Rule

class BodyParagraphAtHeaderRegionRule(Rule):
    priority = 10

    def matches(self, ctx):
        return ctx.position_in_paragraph in (PositionInParagraph.MIDDLE, PositionInParagraph.END)

    def decide(self, ctx):
        return Decision.collect("Body paragraph at header", self.name)

class HighCharacterCountLineAtHeaderRegionRule(Rule):
    priority = 20

    def matches(self, ctx):
        return ctx.character_count is CharacterCount.HIGH

    def decide(self, ctx):
        return Decision.collect("High character count line at header", self.name)

class SingleLineJournalNameAtHeaderRule(Rule):
    priority = 30

    def matches(self, ctx):
        return (ctx.character_count is CharacterCount.LOW and
                ctx.position_in_paragraph is PositionInParagraph.SINGLE_LINE)

    def decide(self, ctx):
        return Decision.skip("Single line journal name at header", self.name)

class StartJournalNameAtHeaderRule(Rule):
    priority = 40

    def matches(self, ctx):
        return (ctx.character_count is CharacterCount.LOW and
                ctx.position_in_paragraph is PositionInParagraph.START and
                ctx.font_name is not FontName.MAIN)

    def decide(self, ctx):
        return Decision.skip("Journal name of non-main font at header, start of paragraph", self.name)


class FallbackHeaderRegionRule(Rule):
    priority = 999

    def matches(self, ctx):
        return True

    def decide(self, ctx):
        return Decision.unhandled("Header Region Text", self.name)