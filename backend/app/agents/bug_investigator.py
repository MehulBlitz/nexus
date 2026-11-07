"""Bug Investigator: evidence-first hypotheses for a developer question."""

from __future__ import annotations

import re

from app.agents.base import Agent
from app.agents.context import AgentContext
from app.agents.llm import safe_user_prompt
from app.agents.schemas import EvidenceRef, Hypothesis, InvestigationResult
from app.core.errors import AppError

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "why",
    "how",
    "does",
    "did",
    "after",
    "before",
    "when",
    "what",
    "this",
    "that",
    "from",
    "into",
    "could",
    "would",
    "should",
    "might",
    "fail",
    "fails",
    "failing",
    "problem",
    "issue",
    "error",
    "page",
    "user",
    "code",
    "repository",
    "refresh",
    "refreshes",
    "refreshing",
}
MAX_EVIDENCE = 6


def _tokens(question: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_.\-]{2,}", question.lower())
    return [w for w in words if w not in STOPWORDS][:8]


class BugInvestigator(Agent):
    name = "bug_investigator"
    title = "Bug Investigator"
    responsibility = (
        "Searches indexed metadata and repository source for the terms in a developer "
        "question, then ranks evidence-backed hypotheses and states uncertainty."
    )
    uses_llm_when_available = True
    output_model = InvestigationResult

    def run(self, context: AgentContext) -> InvestigationResult:
        tokens = _tokens(context.question)
        limitations: list[str] = []
        if not context.snapshot:
            return InvestigationResult(
                summary="This repository has no indexed snapshot, so no evidence can be cited.",
                limitations=["Index the repository before investigating."],
            )
        if not tokens:
            return InvestigationResult(
                summary="The question did not contain searchable terms.",
                limitations=["Ask a question that names a component, behaviour or file."],
            )

        from app.services.search_service import search_code

        hits: list[dict] = []
        search_error: str | None = None
        try:
            hits = search_code(
                context.session,
                context.repository,
                context.snapshot,
                " ".join(tokens),
                settings=context.settings,
                directory=context.scope_path,
                limit=25,
            )
        except AppError as exc:
            search_error = exc.message
        except Exception:  # noqa: BLE001 - investigation must degrade, not crash
            search_error = "Source search failed"
        if search_error:
            limitations.append(f"Source search was incomplete: {search_error}")

        by_file: dict[str, list[dict]] = {}
        for hit in hits:
            by_file.setdefault(hit["path"], []).append(hit)
        ranked_files = sorted(
            by_file.items(),
            key=lambda item: (len(item[1]), any(h["match_type"] != "content" for h in item[1])),
            reverse=True,
        )

        hypotheses: list[Hypothesis] = []
        for path, file_hits in ranked_files[:3]:
            evidence = [
                EvidenceRef(
                    file=path,
                    start_line=hit["line"],
                    end_line=hit["line"],
                    note=hit["snippet"][:300],
                    origin="measured" if hit["match_type"] != "content" else "inferred",
                )
                for hit in file_hits[:MAX_EVIDENCE]
            ]
            confidence = round(min(0.8, 0.35 + 0.1 * len(file_hits)), 2)
            hypotheses.append(
                Hypothesis(
                    title=f"Question terms appear in {path}",
                    confidence=confidence,
                    reasoning=(
                        f"{len(file_hits)} match(es) for {', '.join(tokens)} were found in this "
                        "file. The file is therefore on a relevant execution path, but the "
                        "matches alone do not prove this is the root cause. Inspect the cited "
                        "lines and the flow that reaches them."
                    ),
                    evidence=evidence,
                    origin="inferred",
                    suggested_check=(
                        f"Reproduce the problem with logging around line {file_hits[0]['line']} "
                        f"of {path}."
                    ),
                )
            )

        if not hypotheses:
            summary = (
                f"No indexed file or source line mentioned {', '.join(tokens)}. "
                "NEXUS will not invent a cause: the question may use different wording, the "
                "relevant code may be outside the supported languages, or the repository may "
                "not be indexed at the current commit."
            )
            limitations.append(
                "Zero search hits. Try naming a file, module or function from the repository."
            )
        else:
            summary = (
                f"Investigated {context.repository.full_name} for "
                f"\"{context.question.strip()[:200]}\". Found evidence in "
                f"{len(by_file)} file(s); the top {len(hypotheses)} are ranked below. "
                "Confidence reflects the amount and kind of evidence, not a probability of a bug."
            )
        limitations.extend(context.snapshot_warnings()[:5])

        result = InvestigationResult(
            summary=summary,
            hypotheses=hypotheses,
            recommended_actions=_actions(hypotheses, tokens),
            limitations=limitations,
            ai_used=False,
        )
        result = self._try_llm(context, result, tokens)
        return result

    def _try_llm(
        self, context: AgentContext, deterministic: InvestigationResult, tokens: list[str]
    ) -> InvestigationResult:
        if context.llm is None or not deterministic.hypotheses:
            return deterministic
        evidence_lines = "\n".join(
            f"- {ev.file}:{ev.start_line} {ev.note or ''}"
            for hyp in deterministic.hypotheses
            for ev in hyp.evidence
        )
        prompt = safe_user_prompt(
            (
                "Task: refine bug hypotheses for the question below using ONLY the evidence.\n"
                f"Question: {context.question}\n"
                f"Terms: {', '.join(tokens)}\n"
                "Return JSON: {\"summary\": str, \"hypotheses\": [{\"title\": str, "
                "\"confidence\": 0-1, \"reasoning\": str, \"evidence\": [{\"file\": str, "
                "\"start_line\": int, \"end_line\": int}]}], \"recommended_actions\": [str], "
                "\"limitations\": [str]}. Only cite files and lines from the evidence list."
            ),
            evidence_lines,
        )
        payload = context.llm.complete_json(prompt)
        if not payload:
            return deterministic
        allowed = {
            (ev.file, ev.start_line)
            for hyp in deterministic.hypotheses
            for ev in hyp.evidence
        }
        try:
            candidate = InvestigationResult.model_validate(
                {**payload, "ai_used": True}
            )
        except Exception:  # noqa: BLE001 - invalid model output is discarded
            return deterministic
        # Evidence must already exist in the deterministic evidence set.
        for hypothesis in candidate.hypotheses:
            if any((ev.file, ev.start_line) not in allowed for ev in hypothesis.evidence):
                return deterministic
            hypothesis.origin = "ai_suggested"
        provider_name = getattr(context.llm, "name", "the configured provider")
        candidate.limitations = [
            *candidate.limitations,
            f"AI reasoning was produced by {provider_name} and is labelled as a suggestion; "
            "verify it against the cited lines.",
            "Repository content was sent to the configured local or self-hosted provider only.",
        ]
        return candidate


def _actions(hypotheses: list[Hypothesis], tokens: list[str]) -> list[str]:
    if not hypotheses:
        return [
            "Rephrase the question using a file, module or function name from the repository.",
            "Re-index if the repository changed since the last snapshot.",
        ]
    actions = [
        f"Inspect the cited lines in {hypotheses[0].evidence[0].file}.",
        "Add a failing test that reproduces the described behaviour before changing code.",
        f"Search the repository for {', '.join(tokens[:3])} to find related call sites.",
        "Use the dependency graph to check dependents of the implicated file.",
    ]
    return actions
