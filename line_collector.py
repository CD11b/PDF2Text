import logging
from statistics import mean
from models import StyledLine, Decision

logger = logging.getLogger(__name__)

class LineCollector:
    """Collects or skips lines based on decisions."""

    def process(self, line_group: list[StyledLine], decision: Decision) -> list[StyledLine]:

        merged = self._merge_line_group(line_group)
        self._log(merged, decision)
        return [merged] if decision.action.should_collect else []

    @staticmethod
    def _log(merged, decision):
        logger.log(decision.action.log_level, "%s [%s - CASE: %s]: %s", decision.action.action_label, decision.handler_name, decision.reason, merged)

    @staticmethod
    def _merge_line_group(line_group: list[StyledLine]) -> StyledLine:
        """Merge lines of a line group into a single StyledLine."""
        return StyledLine(
            text=' '.join(line.text for line in line_group if line.text.strip()),
            character_density=sum(line.character_density for line in line_group),
            font_size=mean(line.font_size for line in line_group),
            font_name=line_group[0].font_name,
            start_x=line_group[0].start_x,
            start_y=line_group[0].start_y,
            end_x=line_group[-1].end_x
        )