from src.pdf2text.core.classifier import IndentationClassifier, PositionClassifier, MarginClassifier, RegionClassifier, CharacterCountClassifier, FontNameClassifier, FontSizeClassifier, SplitSpanClassifier, TextContentClassifier

class ColumnLayout:

    def __init__(self, page, column, document_cache):
        self.column = column
        self.line_position = PositionClassifier(page, column, document_cache)
        self.line_indentation = IndentationClassifier(page, column, document_cache)
        self.line_region = RegionClassifier(page, column, document_cache)
        self.margin_position = MarginClassifier(page, column, document_cache)
        self.line_character_count = CharacterCountClassifier(page, column, document_cache)
        self.line_font_name = FontNameClassifier(page, column, document_cache)
        self.line_font_size = FontSizeClassifier(page, column, document_cache)
        self.line_split_span = SplitSpanClassifier(page, column, document_cache)
        self.line_text_content = TextContentClassifier(page, column, document_cache)