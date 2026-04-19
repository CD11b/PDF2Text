import logging
from statistics import mean
from models import StyledLine, Decision

logger = logging.getLogger(__name__)

class LineCollector:
    """Collects or skips lines based on decisions."""

    def process(self, line_group: list[StyledLine], decision: Decision) -> list[StyledLine]:

        merged = self._aggregate_line_group(line_group)
        self._log(merged, decision)
        return [merged] if decision.action.should_collect else []

    @staticmethod
    def _log(merged, decision):
        logger.log(decision.action.log_level, "%s [%s - CASE: %s]: %s", decision.action.action_label, decision.handler_name, decision.reason, merged)

    @staticmethod
    def _aggregate_line_group(line_group: list[StyledLine]) -> StyledLine:
        """Merge lines of a line group into a single StyledLine."""

        first_group, last_group = line_group[0], line_group[-1]

        return StyledLine(
            text=' '.join(line.text for line in line_group if line.text.strip()),
            character_density=sum(line.character_density for line in line_group),
            font_size=mean(line.font_size for line in line_group),
            font_name=first_group.font_name,
            start_x=first_group.start_x,
            start_y=first_group.start_y,
            end_x=last_group.end_x
        )