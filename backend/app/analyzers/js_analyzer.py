"""JavaScript / TypeScript analysis using a brace-aware lexer.

Limits (reported as ``parse_mode="lexer"``): imports and top-level declarations are reliable;
nested methods, end lines and call edges are inferred. Dynamic requires with computed strings
cannot be resolved and are reported as unresolved.
"""

from __future__ import annotations

import re

from app.analyzers.base import ParsedCall, ParsedFile, ParsedImport, ParsedSymbol
from app.analyzers.lexer import (
    ScanResult,
    block_end_line,
    count_lines,
    count_matches,
    line_of,
    scan_source,
)

IMPORT_FROM_RE = re.compile(
    r"""(?:^|\n)\s*(?:import|export)\s+(?:type\s+)?(?:[^'";\n]*?\s+from\s+)?['"]([^'"]+)['"]"""
)
REQUIRE_RE = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""")
CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")
FUNCTION_RE = re.compile(r"\b(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(")
ARROW_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=\s*(?:async\s*)?"
    r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
)
METHOD_RE = re.compile(
    r"(?m)^[ \t]+(?:public\s+|private\s+|protected\s+|static\s+|async\s+|"
    r"readonly\s+|get\s+|set\s+)*"
    r"([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?::[^={]+)?\{"
)
CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "function",
    "return",
    "new",
    "typeof",
    "instanceof",
    "await",
    "async",
    "super",
    "this",
    "constructor",
    "do",
    "else",
    "try",
    "throw",
    "delete",
    "void",
    "yield",
    "in",
    "of",
    "case",
}
COMPLEXITY_PATTERNS = [
    r"\bif\b",
    r"\bfor\b",
    r"\bwhile\b",
    r"\bcase\b",
    r"\bcatch\b",
    r"&&",
    r"\|\|",
    r"\?\?",
]
MAX_CALLS = 200


def _collect_imports(scan: ScanResult) -> list[ParsedImport]:
    found: dict[tuple[str, int], ParsedImport] = {}
    for regex, confidence in ((IMPORT_FROM_RE, 0.9), (REQUIRE_RE, 0.85), (DYNAMIC_IMPORT_RE, 0.8)):
        for match in regex.finditer(scan.no_comments):
            # A match starting inside a string literal is quoted text, not an import.
            if scan.in_string(match.start()):
                continue
            module = match.group(1)
            line = line_of(scan.code, match.start())
            found[(module, line)] = ParsedImport(module=module, line=line, confidence=confidence)
    return sorted(found.values(), key=lambda i: i.line)


def _declarations(masked: str, language: str) -> list[ParsedSymbol]:
    symbols: list[ParsedSymbol] = []
    seen: set[tuple[str, int]] = set()
    for match in CLASS_RE.finditer(masked):
        line = line_of(masked, match.start())
        symbols.append(
            ParsedSymbol(
                name=match.group(1),
                kind="class",
                start_line=line,
                end_line=block_end_line(masked, match.end()),
                qualified_name=match.group(1),
            )
        )
        seen.add((match.group(1), line))
    for match in FUNCTION_RE.finditer(masked):
        line = line_of(masked, match.start())
        if (match.group(1), line) in seen:
            continue
        symbols.append(
            ParsedSymbol(
                name=match.group(1),
                kind="function",
                start_line=line,
                end_line=block_end_line(masked, match.end()),
                qualified_name=match.group(1),
            )
        )
        seen.add((match.group(1), line))
    for match in ARROW_RE.finditer(masked):
        line = line_of(masked, match.start())
        if (match.group(1), line) in seen:
            continue
        symbols.append(
            ParsedSymbol(
                name=match.group(1),
                kind="function",
                start_line=line,
                end_line=block_end_line(masked, match.end()),
                qualified_name=match.group(1),
            )
        )
        seen.add((match.group(1), line))
    if language == "TypeScript":
        for match in METHOD_RE.finditer(masked):
            name = match.group(1)
            line = line_of(masked, match.start())
            if name in KEYWORDS or (name, line) in seen:
                continue
            symbols.append(
                ParsedSymbol(
                    name=name,
                    kind="method",
                    start_line=line,
                    end_line=block_end_line(masked, match.end()),
                    qualified_name=name,
                )
            )
            seen.add((name, line))
    symbols.sort(key=lambda s: s.start_line)
    return symbols


def _calls(masked: str, symbols: list[ParsedSymbol]) -> list[ParsedCall]:
    calls: list[ParsedCall] = []
    for match in CALL_RE.finditer(masked):
        name = match.group(1)
        if name in KEYWORDS:
            continue
        line = line_of(masked, match.start())
        caller = None
        for symbol in symbols:
            if symbol.start_line <= line <= symbol.end_line:
                if symbol.start_line != line:
                    caller = symbol.qualified_name or symbol.name
                break
        calls.append(ParsedCall(caller=caller, callee=name, line=line, confidence=0.4))
        if len(calls) >= MAX_CALLS:
            break
    return calls


def _analyze_with_lexer(path: str, source: str, language: str) -> ParsedFile:
    scan = scan_source(
        source, language="TypeScript" if language == "TypeScript" else "JavaScript"
    )
    warnings: list[str] = []
    imports = _collect_imports(scan)
    symbols = _declarations(scan.code, language)
    calls = _calls(scan.code, symbols)
    if not symbols:
        warnings.append("No declarations matched the lexer patterns")
    complexity = 1 + count_matches(scan.code, COMPLEXITY_PATTERNS)
    if not imports and ("require(" in scan.no_comments or "import" in scan.no_comments):
        warnings.append("Possible unresolved dynamic imports")
    return ParsedFile(
        path=path,
        language=language,
        line_count=count_lines(source),
        parse_mode="lexer",
        imports=imports,
        symbols=symbols,
        calls=calls,
        warnings=warnings,
        complexity=complexity,
        metadata={"analyzer": "lexer", "lexer_confidence": 0.6},
    )


def analyze_javascript(path: str, source: str, *, language: str = "JavaScript") -> ParsedFile:
    return _analyze_with_lexer(path, source, language)
