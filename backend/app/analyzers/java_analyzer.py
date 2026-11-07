"""Java analysis using a brace-aware lexer (``parse_mode="lexer"``)."""

from __future__ import annotations

import re

from app.analyzers.base import ParsedCall, ParsedFile, ParsedImport, ParsedSymbol
from app.analyzers.lexer import (
    block_end_line,
    count_lines,
    count_matches,
    line_of,
    scan_source,
)

IMPORT_RE = re.compile(r"(?m)^\s*import\s+(static\s+)?([\w.]+)\s*;")
PACKAGE_RE = re.compile(r"(?m)^\s*package\s+([\w.]+)\s*;")
TYPE_RE = re.compile(r"\b(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
METHOD_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|static|final|synchronized|abstract|"
    r"native|default)\s+)*"
    r"[\w<>\[\],.?\s]+\s+([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:throws[^{]+)?\{"
)
CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "new",
    "return",
    "super",
    "this",
    "throw",
    "try",
    "do",
    "else",
    "synchronized",
    "assert",
}
COMPLEXITY_PATTERNS = [
    r"\bif\b",
    r"\bfor\b",
    r"\bwhile\b",
    r"\bcase\b",
    r"\bcatch\b",
    r"&&",
    r"\|\|",
]
MAX_SYMBOLS = 400
MAX_CALLS = 200


def analyze_java(path: str, source: str) -> ParsedFile:
    scan = scan_source(source, language="Java")
    masked = scan.code
    warnings: list[str] = []
    package_match = PACKAGE_RE.search(masked)
    package = package_match.group(1) if package_match else None

    imports = [
        ParsedImport(
            module=match.group(2),
            line=line_of(masked, match.start()),
            confidence=0.95,
        )
        for match in IMPORT_RE.finditer(masked)
    ]

    symbols: list[ParsedSymbol] = []
    for match in TYPE_RE.finditer(masked):
        suffix = re.match(r"\s*(?:extends|implements)?", masked[match.end() :])
        line = line_of(masked, match.start())
        symbols.append(
            ParsedSymbol(
                name=match.group(2),
                kind="class",
                start_line=line,
                end_line=block_end_line(masked, match.end() + (suffix.end() if suffix else 0)),
                qualified_name=f"{package}.{match.group(2)}" if package else match.group(2),
            )
        )
    for match in METHOD_RE.finditer(masked):
        name = match.group(1)
        if name in KEYWORDS or name == "return":
            continue
        symbols.append(
            ParsedSymbol(
                name=name,
                kind="method",
                start_line=line_of(masked, match.start()),
                end_line=block_end_line(masked, match.end()),
                qualified_name=name,
            )
        )
    symbols.sort(key=lambda s: s.start_line)
    if len(symbols) > MAX_SYMBOLS:
        warnings.append(f"Symbol limit reached: kept {MAX_SYMBOLS} of {len(symbols)}")
        symbols = symbols[:MAX_SYMBOLS]
    if not symbols:
        warnings.append("No classes or methods matched the lexer patterns")

    calls: list[ParsedCall] = []
    for match in CALL_RE.finditer(masked):
        name = match.group(1)
        if name in KEYWORDS:
            continue
        line = line_of(masked, match.start())
        caller = next(
            (
                s.qualified_name or s.name
                for s in symbols
                if s.start_line <= line <= s.end_line and s.start_line != line
            ),
            None,
        )
        calls.append(ParsedCall(caller=caller, callee=name, line=line, confidence=0.4))
        if len(calls) >= MAX_CALLS:
            break

    return ParsedFile(
        path=path,
        language="Java",
        line_count=count_lines(source),
        parse_mode="lexer",
        imports=imports,
        symbols=symbols,
        calls=calls,
        warnings=warnings,
        complexity=1 + count_matches(masked, COMPLEXITY_PATTERNS),
        metadata={"analyzer": "lexer", "package": package, "lexer_confidence": 0.6},
    )
