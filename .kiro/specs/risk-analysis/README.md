# Risk analysis spec

Status: IMPLEMENTED · TESTED (unit, property and integration).

## Requirements

1. Score files using five transparent signals: dependency centrality, complexity, change frequency,
   test presence, recent change activity.
2. Normalise available signals to 0–100 and renormalise weights over available signals only.
3. Never substitute fabricated values for missing signals.
4. Classify scores: low 0–24, moderate 25–49, high 50–74, critical 75–100.
5. Every finding answers what, where, why, evidence, confidence and next step.
6. Label heuristic scores as prioritisation aids, not probabilities of failure.
7. Produce reproducible output for identical inputs and persist findings per analysis run.
8. Expose summary, findings and analysis triggering; UI shows signals and raw evidence.

## Acceptance criteria

- [x] Scores stay within 0–100 for arbitrary valid inputs (Hypothesis).
- [x] Identical inputs produce identical scores.
- [x] Missing signals are excluded and listed as unavailable.
- [x] Increasing one measured signal never lowers the score with others fixed (property test).
- [x] Weights are validated and sum to 1.0.
- [x] Findings persist evidence including normalised signals and weights.
- [x] UI shows score, severity, confidence, signals, recommendations and raw evidence.
- [x] Report includes the "not a probability" disclaimer.

## Design

`app/services/risk_engine.py`: pure scoring functions, no I/O.
`app/services/risk_service.py`: gathers graph metrics, commit history and test edges; persists
`AnalysisRun` and `Finding`; builds the summary. `app/api/v1/risk.py` exposes the endpoints.

## Data model

`analysis_runs` (type, status, progress), `findings` (severity, score, confidence, evidence JSON,
recommendations, origin), `github_activity_cache` for commit-derived signals.

## API

`GET /repositories/{id}/risks`, `/risks/summary`, `/risks/{finding_id}`,
`POST /repositories/{id}/risks/analyze`.

## Tasks

- [x] Signal extraction and normalisation.
- [x] Missing-data handling.
- [x] Weighted scoring and thresholds.
- [x] Evidence-backed findings.
- [x] Recommendations.
- [x] Endpoints and job.
- [x] Risk center UI.
- [x] Unit and property tests.
- [ ] Calibration against real incident data (weights remain documented assumptions).

## Tests

Unit: normalisation bounds, renormalisation, determinism, monotonicity, threshold classification.
Integration: analysis job produces findings with evidence and a summary with confidence.
