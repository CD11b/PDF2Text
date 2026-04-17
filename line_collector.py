import logging
from statistics import mean

from models import StyledLine, LineContext, Action, Decision

logger = logging.getLogger(__name__)

class LineCollector:
    """Collects or skips lines based on decisions."""

    # def __init__(self):
    #     # self.result = []

    def process(self, line_group, decision: Decision):

        if decision.action == Action.COLLECT:
            return self._collect_group(line_group, decision.reason, decision.handler_name)
        elif decision.action == Action.SKIP:
            return self._skip_group(line_group, decision.reason, decision.handler_name)
        elif decision.action == Action.UNHANDLED:
            return self._unhandled_group(line_group, decision.reason, decision.handler_name)

        # return result

    def _collect_group(self, line_group, reason: str, handler: str):
        """Merge and collect a line group."""
        merged = self._merge_line_group(line_group)
        logging.debug(f"Collected [{handler} - CASE: {reason}]: {merged}")
        return [merged]

    def _skip_group(self, line_group, reason: str, handler: str):
        """Skip a line group."""
        merged = self._merge_line_group(line_group)
        logging.info(f"Skipped [{handler} - CASE: {reason}]: {merged}")
        return []

    def _unhandled_group(self, line_group, reason: str, handler: str):
        """Skip an unhandled line group."""
        merged = self._merge_line_group(line_group)
        logging.info(f"Skipped [{handler} - CASE: {reason}]: {merged}")
        return []

    @staticmethod
    def _merge_line_group(line_group):
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

    def get_result(self) -> list:
        """Return collected lines."""
        return self.result