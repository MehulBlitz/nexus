"""Language dispatch and failure containment for file analysis."""

from __future__ import annotations

from app.analyzers.base import ParsedFile
from app.analyzers.java_analyzer import analyze_java
from app.analyzers.js_analyzer import analyze_javascript
from app.analyzers.lexer import count_lines
from app.analyzers.python_analyzer import analyze_python

SUPPORTED_LANGUAGES = ("Python", "JavaScript", "TypeScript", "Java")


def parse_file(path: str, source: str, language: str, *, max_symbols: int = 400) -> ParsedFile:
    """Analyze one file. A failure is recorded as a warning, never raised to the caller."""
    try:
        if language == "Python":
            return analyze_python(path, source, max_symbols=max_symbols)
        if language == "JavaScript":
            result = analyze_javascript(path, source, language="JavaScript")
            result.symbols = result.symbols[:max_symbols]
            return result
        if language == "TypeScript":
            result = analyze_javascript(path, source, language="TypeScript")
            result.symbols = result.symbols[:max_symbols]
            return result
        if language == "Java":
            return analyze_java(path, source)
    except Exception as exc:  # noqa: BLE001 - one bad file must not fail the whole index
        return ParsedFile(
            path=path,
            language=language,
            line_count=count_lines(source),
            parse_mode="failed",
            warnings=[f"Analyzer error: {type(exc).__name__}"],
        )
    return ParsedFile(
        path=path,
        language=language,
        line_count=count_lines(source),
        parse_mode="unsupported",
        warnings=[f"No analyzer for {language}"],
    )
