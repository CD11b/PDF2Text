from collections import defaultdict

from src.pdf2text.core.text_heuristics import IndentHeuristic, StartYHeuristic, EndXHeuristic, CharacterCountHeuristic, \
    FontNameHeuristic, FontSizeHeuristic, GapWithinRowsHeuristic, GapBetweenRowsHeuristic, ColumnCountHeuristic
from src.pdf2text.models import PageLines, GapData, LayoutProfile, ColumnData, PageData

import logging

logger = logging.getLogger(__name__)

class PageAnalyzer:

    def __init__(self, lines: PageLines):
        self.lines = lines
        self._ocr = None

    @property
    def ocr(self):
        if self._ocr is None:
            if len(self.lines) == 0:
                return False

            words = 1
            phrases = 1

            for line in self.lines:
                text = line.text.strip()
                if not text:
                    continue
                elif " " not in text:
                    words += 1
                else:
                    phrases += 1

            self._ocr = (words / (words + phrases)) > 0.95

        return self._ocr

    @staticmethod
    def sort_line_columns(line_groups, start_x_columns):

        sorted_columns = sorted(start_x_columns)
        first_column = min(start_x_columns)
        columned_groups = defaultdict(list)
        for group in line_groups:
            for line in group:

                if line.start_x < first_column:
                    columned_groups[first_column].append(line)
                    continue

                for column_start_x in reversed(sorted_columns):
                    if line.start_x >= column_start_x:
                        columned_groups[column_start_x].append(line)
                        break


        return columned_groups

    @staticmethod
    def create_line_groups(line_rows, coordinate_tolerance):
        result = []
        for row in line_rows:
            buffer = [row[0]]
            for previous, current in zip(row, row[1:]):
                if current.start_x - previous.end_x <= coordinate_tolerance:
                    buffer.append(current)
                else:
                    result.append(buffer)
                    buffer = [current]
            result.append(buffer)
        return result

    def compute_layout_profile(self, page_lines):
        start_x = IndentHeuristic(self.ocr).compute_feature_stats(page_lines)
        start_y = StartYHeuristic(self.ocr).compute_feature_stats(page_lines)
        end_x = EndXHeuristic(self.ocr).compute_feature_stats(page_lines)
        character_count = CharacterCountHeuristic(self.ocr).compute_feature_stats(page_lines)
        font_size = FontSizeHeuristic(self.ocr).compute_feature_stats(page_lines)
        font_name = FontNameHeuristic(self.ocr).compute_feature_stats(page_lines)

        gap_within_rows = GapWithinRowsHeuristic(self.ocr).compute_bounds(page_lines)
        gap_between_rows = GapBetweenRowsHeuristic(self.ocr).compute_bounds(page_lines)
        gap_data = GapData(gap_within_rows, gap_between_rows)

        return LayoutProfile(start_x, start_y, end_x, gap_data, character_count, font_size, font_name)

    def analyze(self):

        columns = []
        page_heuristics = self.compute_layout_profile(self.lines)
        coordinate_tolerance = page_heuristics.gaps.within_rows.upper if self.ocr else 0.0
        line_groups = self.create_line_groups(self.lines.rows, coordinate_tolerance)

        column_count = ColumnCountHeuristic(self.ocr)
        column_count.build_counter(self.lines, coordinate_tolerance)
        column_count_stats = column_count.compute_feature_stats(self.lines)
        logger.debug(f"Detected {column_count_stats.upper_bound} column(s)")

        if column_count_stats.upper_bound > 1:
            start_x_columns = column_count.compute_column_starts(self.lines, int(column_count_stats.upper_bound))
            columned_groups = self.sort_line_columns(line_groups, start_x_columns)

            for start_x in sorted(columned_groups.keys()):
                column_lines = PageLines(columned_groups[start_x])
                column_heuristics = self.compute_layout_profile(column_lines)
                column_line_groups = self.create_line_groups(column_lines.rows, coordinate_tolerance)
                columns.append(ColumnData(column_line_groups, column_heuristics))
        else:
            columns.append(ColumnData(line_groups, page_heuristics))

        return PageData(page_heuristics, columns, self.ocr)
