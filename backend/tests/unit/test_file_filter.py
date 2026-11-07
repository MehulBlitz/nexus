from app.ingestion.file_filter import is_test_path, language_for, select_files
from app.integrations.github import GitHubFile


def test_language_detection():
    assert language_for("a/b.py") == "Python"
    assert language_for("a/b.tsx") == "TypeScript"
    assert language_for("a/b.jsx") == "JavaScript"
    assert language_for("a/b.java") == "Java"
    assert language_for("a/b.md") is None


def test_test_path_detection():
    assert is_test_path("tests/test_api.py")
    assert is_test_path("src/thing.test.ts")
    assert is_test_path("app/__tests__/x.js")
    assert not is_test_path("src/contest.ts")


def test_select_files_filters_directories_types_and_size():
    files = [
        GitHubFile("src/app.py", "1", 100),
        GitHubFile("node_modules/pkg/index.js", "2", 100),
        GitHubFile("vendor/lib.java", "3", 100),
        GitHubFile("README.md", "4", 100),
        GitHubFile("empty.py", "5", 0),
        GitHubFile("huge.py", "6", 10_000),
        GitHubFile("src/view.tsx", "7", 200),
    ]
    selected, skipped, truncated = select_files(files, max_files=10, max_file_bytes=1000)
    paths = [f.path for f in selected]
    assert paths == ["src/app.py", "src/view.tsx"]
    reasons = {s.path: s.reason for s in skipped}
    assert reasons["node_modules/pkg/index.js"] == "excluded directory"
    assert reasons["empty.py"] == "empty file"
    assert reasons["huge.py"] == "file exceeds size limit"
    assert "README.md" not in reasons  # unsupported languages are summarised, not listed
    assert truncated is False


def test_select_files_reports_cap_truncation():
    files = [GitHubFile(f"src/f{i}.py", str(i), 10) for i in range(5)]
    selected, skipped, truncated = select_files(files, max_files=2, max_file_bytes=1000)
    assert len(selected) == 2
    assert truncated is True
    assert any(s.reason == "repository file limit reached" for s in skipped)
