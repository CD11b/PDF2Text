from src.pdf2text.models.decisions.context_types import VerticalRegion, MarginPosition, PositionInParagraph
from src.pdf2text.models.decisions.decision import Decision
from src.pdf2text.models.decisions.span_context import SpanContext
from src.pdf2text.models.layout.column_layout import ColumnLayout
from src.pdf2text.rule_engine import RuleEngine

from src.pdf2text.core.line_collector import LineCollector

import logging

logger = logging.getLogger(__name__)


class LineFilter:
    def __init__(self, page, document_cache, rule_engines):
        self.page = page
        self.document_cache = document_cache
        self.collector = LineCollector()
        self.engines = {key: RuleEngine(rules) for key, rules in rule_engines.items()}

    def add_paragraph_breaks(self, filtered_lines):

        result = []

        for line in filtered_lines:
            text = line.text
            if self.layout.is_new_paragraph([line], filtered_list=result):
                new_line = line.with_text("\n" + text)
                result.append(new_line)
            else:
                result.append(line)

        return result

    def _select_engine(self, ctx):

        if ctx.region is VerticalRegion.HEADER:
            return self.engines["header"]

        if ctx.region is VerticalRegion.FOOTER:
            return self.engines["footer"]

        if ctx.margin_position is MarginPosition.BEFORE:
            return self.engines["before_left_margin"]

        if ctx.margin_position is MarginPosition.AT:
            if ctx.position_in_paragraph is not PositionInParagraph.SINGLE_LINE:
                return self.engines["continuous_paragraph"]
            return self.engines["at_left_margin"]

        if ctx.margin_position is MarginPosition.AFTER:
            return self.engines["indented"]

        return None

    def _filter_line(self, group, ctx, result):
        engine = self._select_engine(ctx)

        if engine is None:
            decision = Decision.unhandled("Router could not find a suitable rule engine", "_select_engine")
        else:
            decision = engine.decide(ctx)

        result.extend(self.collector.process(group, ctx, decision))

    @staticmethod
    def _add_page_break(buffer):
        if not buffer:
            return []

        last_line = buffer[-1].span.with_text(buffer[-1].span.text + "\n\n")
        last_collected_line = buffer[-1].with_line(last_line)
        return [*buffer[:-1], last_collected_line]

    def _process_column(self, column):
        buffer = []
        column_layout = ColumnLayout(self.page, column, self.document_cache)
        logging.debug(f"Column: {column.heuristics}")

        i = 0
        while i < len(column.spans):
            span = column.spans[i]
            next_span = column.spans[i + 1] if i + 1 < len(column.spans) else None

            ctx = SpanContext.create(column_layout, span, next_span, buffer)
            self._filter_line(span, ctx, buffer)

            i += 1

        return self._add_page_break(buffer)

    def filter_lines_individually(self):
        result = []

        for column in self.page.column_layouts:
            result.extend(self._process_column(column))

        return result
