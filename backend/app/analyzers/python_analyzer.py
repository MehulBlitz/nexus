"""Python analysis using the standard library AST (exact syntax tree, not regex)."""

from __future__ import annotations

import ast

from app.analyzers.base import ParsedCall, ParsedFile, ParsedImport, ParsedSymbol
from app.analyzers.lexer import count_lines

COMPLEXITY_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.And,
    ast.Or,
    ast.ExceptHandler,
    ast.IfExp,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.comprehension,
)
MAX_CALLS = 200


def _complexity(node: ast.AST) -> int:
    return 1 + sum(isinstance(child, COMPLEXITY_NODES) for child in ast.walk(node))


def _collect_imports(tree: ast.Module) -> list[ParsedImport]:
    imports: list[ParsedImport] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ParsedImport(module=alias.name, line=node.lineno, confidence=1.0)
                )
        elif isinstance(node, ast.ImportFrom):
            module = "." * (node.level or 0) + (node.module or "")
            imports.append(
                ParsedImport(
                    module=module or ".",
                    line=node.lineno,
                    confidence=1.0,
                    names=tuple(alias.name for alias in node.names),
                )
            )
    return imports


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: list[str] = []
        cursor: ast.AST = func
        while isinstance(cursor, ast.Attribute):
            parts.append(cursor.attr)
            cursor = cursor.value
        if isinstance(cursor, ast.Name):
            parts.append(cursor.id)
            return ".".join(reversed(parts))
    return None


def _symbols(tree: ast.Module, warnings: list[str]) -> tuple[list[ParsedSymbol], list[ParsedCall]]:
    symbols: list[ParsedSymbol] = []
    calls: list[ParsedCall] = []

    def visit_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef, parent: str | None
    ) -> ParsedSymbol:
        qualified = f"{parent}.{node.name}" if parent else node.name
        symbol = ParsedSymbol(
            name=node.name,
            kind="method" if parent else "function",
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
            qualified_name=qualified,
            parent=parent,
            complexity=_complexity(node),
            decorators=tuple(
                ast.unparse(d) if hasattr(ast, "unparse") else "" for d in node.decorator_list
            ),
        )
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = _call_name(child)
                if name and len(calls) < MAX_CALLS:
                    calls.append(
                        ParsedCall(
                            caller=qualified, callee=name, line=child.lineno, confidence=0.8
                        )
                    )
        return symbol

    def visit_class(node: ast.ClassDef, parent: str | None) -> None:
        qualified = f"{parent}.{node.name}" if parent else node.name
        symbols.append(
            ParsedSymbol(
                name=node.name,
                kind="class",
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
                qualified_name=qualified,
                parent=parent,
                complexity=_complexity(node),
                decorators=tuple(
                    ast.unparse(d) if hasattr(ast, "unparse") else "" for d in node.decorator_list
                ),
            )
        )
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(visit_function(child, qualified))
            elif isinstance(child, ast.ClassDef):
                visit_class(child, qualified)

    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(visit_function(statement, None))
        elif isinstance(statement, ast.ClassDef):
            visit_class(statement, None)

    if len(symbols) == 0:
        warnings.append("No top-level functions or classes found")
    return symbols, calls


def analyze_python(path: str, source: str, *, max_symbols: int = 400) -> ParsedFile:
    line_count = count_lines(source)
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as exc:
        error_line = getattr(exc, "lineno", "?") or "?"
        return ParsedFile(
            path=path,
            language="Python",
            line_count=line_count,
            parse_mode="failed",
            warnings=[f"Python syntax error: {type(exc).__name__} at line {error_line}"],
        )

    warnings: list[str] = []
    symbols, calls = _symbols(tree, warnings)
    if len(symbols) > max_symbols:
        warnings.append(f"Symbol limit reached: kept {max_symbols} of {len(symbols)}")
        symbols = symbols[:max_symbols]
    imports = _collect_imports(tree)
    total_complexity = sum(s.complexity for s in symbols) or 1
    return ParsedFile(
        path=path,
        language="Python",
        line_count=line_count,
        parse_mode="ast",
        imports=imports,
        symbols=symbols,
        calls=calls,
        warnings=warnings,
        complexity=total_complexity,
        metadata={"top_level_statements": len(tree.body)},
    )
