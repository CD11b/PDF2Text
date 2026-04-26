from src.pdf2text.rule_engine.indented import *
from src.pdf2text.rule_engine.footer import *
from src.pdf2text.rule_engine.header import *
from src.pdf2text.rule_engine.continuous_paragraph import *
from src.pdf2text.rule_engine.at_left_margin import *
from src.pdf2text.rule_engine.before_left_margin import *

RULE_ENGINES = {
    "indented": [
        IndentedBlockLastLineRule(),
        IndentedBlockParagraphRule(),
        IndentedMainFontRule(),
        SplitSpanIndentationLineRule(),
        ParagraphStartIndentedRule(),
        EpigraphAuthorRule(),
        TitlePageRule(),
        ItalicWordMidLineRule(),
        BoldWordMidLineRule(),
        FallbackIndentedRule(),
    ],
    "header": [
        BodyParagraphAtHeaderRegionRule(),
        HighCharacterCountLineAtHeaderRegionRule(),
        SingleLineJournalNameAtHeaderRule(),
        StartJournalNameAtHeaderRule(),
        FallbackHeaderRegionRule(),
    ],
    "footer": [
        FooterRegionBodyParagraphRule(),
        FooterRegionLoneIndentedTextRule(),
        FooterRegionHighCharacterCountLineRule(),
        FallbackFooterRegionRule(),
    ],
    "continuous_paragraph": [
        ContinuousParagraphMainFontRule(),
        ContinuousParagraphMultiLineTitleRule(),
        FallbackContinuousParagraphRule(),
    ],
    "at_left_margin": [
        SingleEmphasizedLineRule(),
        BoldSectionHeaderAtLeftMarginRule(),
        FallbackAtLeftMarginRule(),
    ],
    "before_left_margin": [
        FooterBeforeLeftMarginRule(),
        HeadingBeforeLeftMarginRule(),
        FallbackBeforeLeftMarginRule(),
    ],
}
