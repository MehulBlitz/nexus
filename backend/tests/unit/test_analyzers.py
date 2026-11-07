from app.analyzers.registry import parse_file

PYTHON_SOURCE = '''
"""Module docstring."""
import os
from app.core.config import get_settings
from .sibling import helper


class Service:
    def run(self):
        if self.ready:
            return helper()
        return get_settings()


def main():
    return Service().run()
'''


def test_python_uses_real_ast():
    result = parse_file("app/service.py", PYTHON_SOURCE, "Python")
    assert result.parse_mode == "ast"
    assert result.line_count == len(PYTHON_SOURCE.splitlines())
    modules = {imp.module for imp in result.imports}
    assert {"os", "app.core.config", ".sibling"} <= modules
    names = {s.qualified_name for s in result.symbols}
    assert {"Service", "Service.run", "main"} <= names
    assert all(imp.confidence == 1.0 for imp in result.imports)
    call_names = {c.callee for c in result.calls}
    assert "get_settings" in call_names and "helper" in call_names
    assert any(c.caller == "main" for c in result.calls)
    assert result.complexity >= 2


def test_python_syntax_error_is_a_warning_not_a_crash():
    result = parse_file("broken.py", "def nope(:\n", "Python")
    assert result.parse_mode == "failed"
    assert result.warnings and "syntax error" in result.warnings[0].lower()
    assert result.symbols == []


def test_javascript_imports_and_declarations():
    source = """
import React from "react";
import { api } from "../lib/api";
const legacy = require("./legacy");

export class Store {
  load() {
    return api.get();
  }
}

function boot() { return new Store().load(); }
const handler = async (event) => api.post(event);
"""
    result = parse_file("src/store.js", source, "JavaScript")
    assert result.parse_mode == "lexer"
    modules = {imp.module for imp in result.imports}
    assert {"react", "../lib/api", "./legacy"} <= modules
    names = {s.name for s in result.symbols}
    assert {"Store", "boot", "handler"} <= names
    assert any(s.kind == "class" for s in result.symbols)


def test_javascript_ignores_declarations_inside_comments_and_strings():
    source = """
// function fake() {}
const message = "function alsoFake() {}";
function real() {}
"""
    result = parse_file("src/real.js", source, "JavaScript")
    assert {s.name for s in result.symbols} == {"real"}


def test_typescript_methods_and_types():
    source = """
import type { User } from "./types";
export class UserService {
  private cache: Map<string, User> = new Map();
  async find(id: string): Promise<User> {
    return this.cache.get(id);
  }
}
"""
    result = parse_file("src/user.service.ts", source, "TypeScript")
    assert result.language == "TypeScript"
    names = {s.name for s in result.symbols}
    assert "UserService" in names
    assert "find" in names
    assert {imp.module for imp in result.imports} == {"./types"}


def test_java_imports_classes_and_methods():
    source = """
package com.example.app;

import java.util.List;
import static java.util.Collections.emptyList;

public class Inventory {
    public List<String> items() {
        return emptyList();
    }
}
"""
    result = parse_file("src/main/java/com/example/app/Inventory.java", source, "Java")
    assert result.parse_mode == "lexer"
    assert {imp.module for imp in result.imports} == {
        "java.util.List",
        "java.util.Collections.emptyList",
    }
    assert result.metadata.get("package") == "com.example.app"
    names = {s.name for s in result.symbols}
    assert "Inventory" in names and "items" in names


def test_unsupported_language_reports_unsupported():
    result = parse_file("main.go", "package main", "Go")
    assert result.parse_mode == "unsupported"
    assert result.warnings


def test_symbol_cap_is_reported():
    source = "\n".join(f"def f{i}(): pass" for i in range(30))
    result = parse_file("many.py", source, "Python", max_symbols=5)
    assert len(result.symbols) == 5
    assert any("Symbol limit" in w for w in result.warnings)
