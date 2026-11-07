"""Small lexing helpers for languages without an available parser.

This is deliberately modest: it blanks comments and string literals so declaration regexes do
not match inside them, while keeping a second view with string literals intact so import
paths can still be read. It is not a parser and does not claim to be one; analyzers built on
it report ``parse_mode="lexer"``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


@dataclass
class ScanResult:
    """Two aligned views of the same source plus the spans occupied by string literals."""

    code: str  # comments and strings replaced by spaces
    no_comments: str  # comments replaced by spaces, string literals intact
    string_spans: list[tuple[int, int]] = field(default_factory=list)

    def in_string(self, offset: int) -> bool:
        return any(start <= offset < end for start, end in self.string_spans)


def count_lines(text: str) -> int:
    """Line count that treats a single trailing newline as a terminator, not a new line."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_source(text: str, *, language: str) -> ScanResult:
    """Separate comments and string literals from code in one pass.

    Template literals and regex literals are treated as strings, which can only hide a
    declaration, never invent one.
    """
    code: list[str] = []
    plain: list[str] = []
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    in_line_comment = False
    in_block_comment = False
    quote: str | None = None
    quote_start = 0
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                code.append(ch)
                plain.append(ch)
            else:
                code.append(" ")
                plain.append(" ")
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                code.extend("  ")
                plain.extend("  ")
                i += 2
                continue
            code.append("\n" if ch == "\n" else " ")
            plain.append("\n" if ch == "\n" else " ")
            i += 1
            continue
        if quote:
            if ch == "\\" and i + 1 < n:
                code.extend("  ")
                plain.append(text[i : i + 2])
                i += 2
                continue
            if language == "Java" and text.startswith('"""', i):
                quote = None
                spans.append((quote_start, i + 3))
                code.extend("   ")
                plain.extend('"""')
                i += 3
                continue
            if ch == quote:
                code.append(" ")
                plain.append(ch)
                spans.append((quote_start, i + 1))
                quote = None
                i += 1
                continue
            code.append("\n" if ch == "\n" and quote == "`" else " ")
            plain.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            code.extend("  ")
            plain.extend("  ")
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            code.extend("  ")
            plain.extend("  ")
            i += 2
            continue
        if ch in {"'", '"', "`"}:
            if language == "Java" and text.startswith('"""', i):
                quote = '"'
                quote_start = i
                code.extend("   ")
                plain.extend('"""')
                i += 3
                continue
            quote = ch
            quote_start = i
            code.append(" ")
            plain.append(ch)
            i += 1
            continue
        code.append(ch)
        plain.append(ch)
        i += 1
    return ScanResult(code="".join(code), no_comments="".join(plain), string_spans=spans)


def block_end_line(masked: str, search_from: int) -> int:
    """Given an offset, find the line where the enclosing brace block closes.

    Falls back to the starting line when no brace block is found nearby.
    """
    start_line = line_of(masked, search_from)
    brace = masked.find("{", search_from)
    if brace == -1:
        return start_line
    if masked.count("\n", search_from, brace) > 4:
        return start_line
    depth = 0
    for index in range(brace, len(masked)):
        ch = masked[index]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return line_of(masked, index)
    return start_line


def count_matches(masked: str, patterns: list[str]) -> int:
    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, masked))
    return total
