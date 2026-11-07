# Code intelligence spec

Status: IMPLEMENTED · TESTED. Python uses the standard AST. JavaScript, TypeScript and Java use a
documented lexer because `tree-sitter` has no Python 3.15 wheel and its source build fails here.

## Requirements

1. Detect language from file extension and ignore unsupported files safely.
2. Extract imports, functions, classes, modules and supported calls with source locations.
3. Record parser mode and warnings per snapshot; never crash the job on one bad file.
4. Persist files, symbols and relationships for the graph builder.
5. Report language distribution, file/symbol counts, top modules, entry points and coverage.
6. Never claim full semantic understanding for lexer-based languages.
7. Bound symbols per file and total indexed files.

## Acceptance criteria

- [x] Python imports, classes, functions, async functions and calls are extracted with line ranges.
- [x] JS/TS imports and declarations are extracted with a lexer and labelled as such.
- [x] Java classes/methods/imports are extracted with the same lexer.
- [x] A deliberately broken Python file yields a warning, not a failed snapshot.
- [x] Language counts and symbol counts come from persisted data.
- [x] Coverage metadata distinguishes `ast` from `lexer` and lists skip reasons.
- [x] Search supports path, symbol and content matching.

## Design

`app/analyzers/base.py` defines the analyzer contract; `python.py` uses `ast`; `lexer.py` implements
the shared declaration lexer for JS/TS/Java; `registry.py` selects by language.
`app/services/indexing_service.py` orchestrates fetch → parse → persist → graph.

## Data model

`code_nodes` (file, module, class, function, test, workflow) with `metadata_json` for line counts,
parse mode and warnings; `dependency_edges` for IMPORTS/CALLS/DEFINES/TESTS/CONTAINS.

## API

`GET /repositories/{id}/overview`, `/files`, `/symbols?q=`, `/search?q=`.

## Tasks

- [x] Python AST analyzer.
- [x] JS/TS/Java lexer analyzer with documented limits.
- [x] Symbol and import extraction.
- [x] Source locations.
- [x] Parser warnings.
- [x] Persistence and coverage reporting.
- [x] Unit tests for each language.
- [ ] Optional tree-sitter integration (blocked on wheels/build for the available interpreter).

## Tests

Analyzer unit tests: Python imports/classes/functions/calls, malformed syntax, JS/TS/Java
declarations. Integration: snapshot counts, language distribution, warnings.
