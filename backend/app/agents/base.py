"""Agent interface shared by every specialised agent."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.agents.context import AgentContext


class Agent(ABC):
    name: str = "agent"
    title: str = "Agent"
    responsibility: str = ""
    uses_llm_when_available: bool = False
    output_model: type[BaseModel]

    @abstractmethod
    def run(self, context: AgentContext) -> BaseModel:
        """Produce a validated output. Raise only on genuine failure."""
