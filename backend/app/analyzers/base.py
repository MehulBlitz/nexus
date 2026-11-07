"""Shared analyzer result types.

``parse_mode`` records how much the analyzer really understood:
- "ast": the language's own parser (Python, via the stdlib ``ast`` module).
- "lexer": token/brace aware scanning. Declarations and imports are reliable; calls and
  end lines are inferred and carry lower confidence.
- "failed": parsing failed; the file is recorded with a warning and no symbols.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedImport:
    module: str
    line: int
    # 1.0 when the import target is a path we can resolve directly; lower when inferred.
    confidence: float = 0.9
    names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedSymbol:
    name: str
    kind: str  # "function" | "class" | "method"
    start_line: int
    end_line: int
    qualified_name: str | None = None
    parent: str | None = None
    complexity: int = 1
    decorators: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedCall:
    caller: str | None
    callee: str
    line: int
    confidence: float = 0.5


@dataclass
class ParsedFile:
    path: str
    language: str
    line_count: int
    parse_mode: str
    imports: list[ParsedImport] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)
    calls: list[ParsedCall] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    complexity: int = 1
    metadata: dict = field(default_factory=dict)
