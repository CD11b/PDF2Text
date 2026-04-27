import logging
from statistics import mean
from src.pdf2text.models import StyledLine, Decision, LineContext, CollectedLine

logger = logging.getLogger(__name__)

class LineCollector:
    """Collects or skips lines based on decisions."""

    def process(self, group: list[StyledLine], ctx: LineContext, decision: Decision) -> list[StyledLine]:

        merged = self._aggregate_line_group(group, ctx)
        self._log(decision, merged, ctx)
        return [merged] if decision.action.should_collect else []

    @staticmethod
    def _log(decision: Decision, merged: StyledLine, ctx: LineContext) -> None:
        logger.log(decision.action.log_level,
                   "%s [%s - CASE: %s]: %s, %s",
                   decision.action.action_label,
                   decision.handler_name, decision.reason,
                   merged if decision.action.log_verbose else merged.line.text,
                   ctx if decision.action.log_verbose else "")

    @staticmethod
    def _aggregate_line_group(line_group: list[StyledLine], ctx: LineContext) -> StyledLine:
        """Merge lines of a line group into a single StyledLine."""

        first_group, last_group = line_group[0], line_group[-1]

        line = StyledLine.create(text=' '.join(line.text for line in line_group if line.text.strip()),
                                 font_size=mean(line.font_size for line in line_group),
                                 font_name=first_group.font_name,
                                 start_x=first_group.start_x,
                                 start_y=first_group.start_y,
                                 end_x=last_group.end_x)
        return CollectedLine.create(line, ctx)