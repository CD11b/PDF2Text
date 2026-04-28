from dataclasses import dataclass
from src.pdf2text.models.layout.feature_stats import FeatureStats, GapData

from src.pdf2text.core.text_heuristics import IndentHeuristic, StartYHeuristic, EndXHeuristic, CharacterCountHeuristic, \
    FontNameHeuristic, FontSizeHeuristic, GapWithinRowsHeuristic, GapBetweenRowsHeuristic

@dataclass(frozen=True, slots=True)
class LayoutProfile:
    """Statistical analysis of page layout."""
    start_x: FeatureStats
    start_y: FeatureStats
    end_x: FeatureStats
    gaps: GapData
    character_count: FeatureStats
    font_size: FeatureStats
    font_name: str

    @property
    def row_separation(self) -> float:
        return self.gaps.between_rows.upper

    @classmethod
    def create(cls, spans):
        start_x = IndentHeuristic(spans.is_ocr).compute_feature_stats(spans)
        start_y = StartYHeuristic(spans.is_ocr).compute_feature_stats(spans)
        end_x = EndXHeuristic(spans.is_ocr).compute_feature_stats(spans)
        character_count = CharacterCountHeuristic(spans.is_ocr).compute_feature_stats(spans)
        font_size = FontSizeHeuristic(spans.is_ocr).compute_feature_stats(spans)
        font_name = FontNameHeuristic(spans.is_ocr).compute_feature_stats(spans)

        gap_within_rows = GapWithinRowsHeuristic(spans.is_ocr).compute_bounds(spans)
        gap_between_rows = GapBetweenRowsHeuristic(spans.is_ocr).compute_bounds(spans)
        gap_data = GapData(gap_within_rows, gap_between_rows)

        return cls(start_x, start_y, end_x, gap_data, character_count, font_size, font_name)