"""Specialised NEXUS agents. Each has a distinct responsibility and output contract."""

from app.agents.architecture_reviewer import ArchitectureReviewer
from app.agents.bug_investigator import BugInvestigator
from app.agents.repository_mapper import RepositoryMapper
from app.agents.review_planner import ReviewPlanner
from app.agents.risk_analyst import RiskAnalyst

AGENT_CLASSES = [RepositoryMapper, BugInvestigator, RiskAnalyst, ArchitectureReviewer]

__all__ = [
    "AGENT_CLASSES",
    "ArchitectureReviewer",
    "BugInvestigator",
    "RepositoryMapper",
    "ReviewPlanner",
    "RiskAnalyst",
]
