from dataclasses import dataclass
import numpy as np
from collections import Counter

@dataclass(frozen=True, slots=True)
class Range:
    minimum: float | None
    maximum: float | None

@dataclass(frozen=True, slots=True)
class Distribution:
    most_common: float
    range: Range

    @classmethod
    def create(cls, counter, discrete = False):
        most_common = counter.most_common(1)[0][0]

        minimum, maximum = ((None, None) if discrete else (min(counter), max(counter)))

        return cls(most_common, Range(minimum, maximum))


@dataclass(frozen=True, slots=True)
class Bounds:
    """Lower and upper bounds for a metric."""
    lower: float | None
    upper: float | None

    @classmethod
    def create(cls, data: Counter[float], threshold: float):
        """Compute statistical bounds for a numeric counter using MAD."""
        if not data:
            return cls(None, None)

        values = np.array(list(data.keys()))
        weights = np.array(list(data.values()))

        # Weighted median
        sorted_idx = np.argsort(values)
        sorted_values = values[sorted_idx]
        sorted_weights = weights[sorted_idx]
        cumulative_sum = np.cumsum(sorted_weights)
        median = sorted_values[np.searchsorted(cumulative_sum, cumulative_sum[-1] / 2)]

        # Median Absolute Deviation
        deviations = np.abs(values - median)
        mad = np.average(deviations, weights=weights)

        if mad == 0 or np.isnan(mad):
            return cls(float(values.min()), float(values.max()))

        # MAD filtering
        mad_scores = np.abs((values - median) / (1.4826 * mad))
        inliers = values[mad_scores <= threshold]

        if len(inliers) == 0:
            return cls(float(values.min()), float(values.max()))

        return cls(float(inliers.min()), float(inliers.max()))


@dataclass(frozen=True, slots=True)
class GapData:
    within_rows: Bounds
    between_rows: Bounds


@dataclass(frozen=True, slots=True)
class FeatureStats:
    distribution: Distribution
    bounds: Bounds

    @property
    def lower_bound(self) -> float | None:
        return self.bounds.lower

    @property
    def upper_bound(self) -> float | None:
        return self.bounds.upper

    @property
    def most_common(self) -> float:
        return self.distribution.most_common

    @property
    def minimum(self) -> float:
        return self.distribution.range.minimum

    @property
    def maximum(self) -> float:
        return self.distribution.range.maximum


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