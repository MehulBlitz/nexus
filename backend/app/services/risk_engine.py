"""Transparent weighted risk scoring.

R = sum(w_i * s_i) / sum(w_i) over the signals that are actually available. Missing signals
are omitted and the remaining weights renormalised; they are never replaced with invented
values. The score is a heuristic indicator, not a probability of failure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_WEIGHTS: dict[str, float] = {
    "dependency_centrality": 0.25,
    "code_complexity": 0.20,
    "change_frequency": 0.20,
    "test_presence": 0.20,
    "recent_change_activity": 0.15,
}

DEFAULT_THRESHOLDS: tuple[float, float, float] = (25.0, 50.0, 75.0)

SIGNAL_LABELS = {
    "dependency_centrality": "Dependency centrality",
    "code_complexity": "Code complexity",
    "change_frequency": "Change frequency",
    "test_presence": "Test presence",
    "recent_change_activity": "Recent change activity",
}


class RiskConfigError(ValueError):
    """Raised when weights or thresholds are invalid."""


@dataclass
class RiskResult:
    score: float
    severity: str
    used_signals: list[str]
    missing_signals: list[str]
    confidence: float
    contributions: dict[str, float] = field(default_factory=dict)


def validate_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise RiskConfigError("At least one weight is required")
    for name, weight in weights.items():
        if name not in SIGNAL_LABELS:
            raise RiskConfigError(f"Unknown risk signal: {name}")
        if not isinstance(weight, (int, float)) or math.isnan(weight) or weight < 0:
            raise RiskConfigError(f"Weight for {name} must be a non-negative number")
    if sum(weights.values()) <= 0:
        raise RiskConfigError("Risk weights must sum to a positive value")


def validate_thresholds(thresholds: tuple[float, float, float]) -> None:
    low, moderate, high = thresholds
    if not (0 <= low < moderate < high <= 100):
        raise RiskConfigError("Thresholds must satisfy 0 <= low < moderate < high <= 100")


def clamp_signal(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def compute_risk(
    signals: dict[str, float | None],
    *,
    weights: dict[str, float] | None = None,
    thresholds: tuple[float, float, float] = DEFAULT_THRESHOLDS,
) -> RiskResult:
    """Weighted score over available signals, with explicit confidence."""
    active_weights = dict(weights or DEFAULT_WEIGHTS)
    validate_weights(active_weights)
    validate_thresholds(thresholds)

    usable: dict[str, float] = {}
    missing: list[str] = []
    for name in active_weights:
        value = signals.get(name)
        if value is None:
            missing.append(name)
        else:
            usable[name] = clamp_signal(value)
    for name in signals:
        if name not in active_weights:
            raise RiskConfigError(f"Signal {name} has no configured weight")

    if not usable:
        return RiskResult(
            score=0.0,
            severity="unknown",
            used_signals=[],
            missing_signals=missing,
            confidence=0.0,
        )

    total_weight = sum(active_weights[name] for name in usable)
    if total_weight <= 0:
        return RiskResult(0.0, "unknown", [], missing, 0.0)
    contributions = {
        name: active_weights[name] * value / total_weight for name, value in usable.items()
    }
    score = round(sum(contributions.values()), 2)
    return RiskResult(
        score=score,
        severity=classify(score, thresholds),
        used_signals=sorted(usable),
        missing_signals=missing,
        confidence=round(total_weight / sum(active_weights.values()), 3),
        contributions={k: round(v, 2) for k, v in contributions.items()},
    )


def classify(score: float, thresholds: tuple[float, float, float] = DEFAULT_THRESHOLDS) -> str:
    validate_thresholds(thresholds)
    if score < thresholds[0]:
        return "low"
    if score < thresholds[1]:
        return "moderate"
    if score < thresholds[2]:
        return "high"
    return "critical"


def normalise_relative(value: float, maximum: float) -> float:
    """Scale a non-negative measurement to 0-100 relative to the observed maximum."""
    if maximum <= 0:
        return 0.0
    return clamp_signal(100.0 * value / maximum)


def normalise_log(value: float, maximum: float) -> float:
    """Log-scale normalisation so one enormous module does not flatten everything else."""
    if maximum <= 0 or value <= 0:
        return 0.0
    return clamp_signal(100.0 * math.log1p(value) / math.log1p(maximum))


def recency_signal(days_since_change: float | None) -> float | None:
    if days_since_change is None:
        return None
    if days_since_change <= 7:
        return 100.0
    if days_since_change <= 30:
        return 60.0
    if days_since_change <= 90:
        return 30.0
    return 10.0


def test_presence_signal(*, is_test: bool, imported_by_test: bool) -> float:
    if is_test:
        return 100.0
    if imported_by_test:
        return 80.0
    return 0.0
