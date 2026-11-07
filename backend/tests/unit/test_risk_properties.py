"""Property-based tests for the risk engine invariants."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.risk_engine import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    RiskConfigError,
    classify,
    compute_risk,
    recency_signal,
    validate_weights,
)

SIGNAL_NAMES = list(DEFAULT_WEIGHTS)



def signal_strategy():
    return st.dictionaries(
        keys=st.sampled_from(SIGNAL_NAMES),
        values=st.one_of(st.none(), st.floats(min_value=0, max_value=100, allow_nan=False)),
        max_size=len(SIGNAL_NAMES),
    )


@settings(max_examples=120, deadline=None)
@given(signal_strategy())
def test_score_is_always_bounded(signals):
    result = compute_risk(signals)
    assert 0.0 <= result.score <= 100.0
    assert result.severity in {"low", "moderate", "high", "critical", "unknown"}


@settings(max_examples=80, deadline=None)
@given(signal_strategy())
def test_score_is_deterministic(signals):
    assert compute_risk(signals).score == compute_risk(dict(signals)).score


@settings(max_examples=80, deadline=None)
@given(signal_strategy())
def test_missing_signals_are_reported_not_fabricated(signals):
    result = compute_risk(signals)
    provided = {name for name, value in signals.items() if value is not None}
    assert set(result.used_signals) == provided
    # Every configured signal is either used or reported as missing, never silently invented.
    assert set(result.used_signals) | set(result.missing_signals) == set(DEFAULT_WEIGHTS)
    assert not (set(result.used_signals) & set(result.missing_signals))


@settings(max_examples=120, deadline=None)
@given(
    signal_strategy(),
    st.sampled_from(SIGNAL_NAMES),
    st.floats(min_value=0, max_value=100, allow_nan=False),
)
def test_increasing_a_signal_never_lowers_the_score(signals, name, increment):
    baseline = compute_risk(signals)
    current = signals.get(name)
    if current is None:
        return
    raised = {**signals, name: min(100.0, current + increment)}
    assert compute_risk(raised).score >= baseline.score - 1e-9


def test_weights_must_be_valid():
    with pytest.raises(RiskConfigError):
        validate_weights({**DEFAULT_WEIGHTS, "dependency_centrality": -0.1})
    with pytest.raises(RiskConfigError):
        validate_weights({"not_a_signal": 1.0})
    with pytest.raises(RiskConfigError):
        validate_weights({name: 0.0 for name in SIGNAL_NAMES})


@settings(max_examples=100, deadline=None)
@given(st.floats(min_value=0, max_value=100, allow_nan=False))
def test_classification_thresholds_are_monotonic(score):
    severity = classify(score)
    order = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
    assert 0 <= order[severity] <= 3
    if score < DEFAULT_THRESHOLDS[0]:
        assert severity == "low"
    elif score >= DEFAULT_THRESHOLDS[2]:
        assert severity == "critical"


@given(st.one_of(st.none(), st.floats(min_value=0, max_value=1000, allow_nan=False)))
def test_recency_signal_is_bounded_or_unavailable(days):
    value = recency_signal(days)
    if days is None:
        assert value is None
    else:
        assert 0 <= value <= 100


def test_all_signals_missing_yields_unknown_not_zero_risk():
    result = compute_risk(dict.fromkeys(SIGNAL_NAMES, None))
    assert result.severity == "unknown"
    assert result.confidence == 0.0
