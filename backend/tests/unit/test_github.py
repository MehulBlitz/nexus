import httpx
import pytest

from app.core.errors import NotFoundError, UnprocessableError, UpstreamError
from app.integrations.github import (
    GitHubClient,
    GitHubFile,
    parse_repository_url,
    validate_file_path,
)

REPO = "https://github.com/octocat/Hello-World"


@pytest.mark.parametrize(
    "url,expected",
    [
        (REPO, ("octocat", "Hello-World")),
        ("https://github.com/owner/repo.git", ("owner", "repo")),
        ("https://www.github.com/owner/repo/", ("owner", "repo")),
    ],
)
def test_valid_urls_are_parsed(url, expected):
    ref = parse_repository_url(url)
    assert (ref.owner, ref.repo) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://github.com/owner/repo",
        "https://gitlab.com/owner/repo",
        "https://github.com.evil.com/owner/repo",
        "https://user:pass@github.com/owner/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/extra",
        "https://github.com/owner/repo?x=1",
        "https://github.com/../../etc/passwd",
        "https://127.0.0.1/owner/repo",
        "https://github.com//repo",
    ],
)
def test_invalid_urls_are_rejected(url):
    with pytest.raises(UnprocessableError):
        parse_repository_url(url)


@pytest.mark.parametrize("path", ["../etc/passwd", "/abs/path.py", "a/../../b.py", "a\\b.py"])
def test_file_path_traversal_is_rejected(path):
    with pytest.raises(UnprocessableError):
        validate_file_path(path)


def make_client(handler, **kwargs):
    return GitHubClient(
        api_base="https://api.github.com",
        raw_base="https://raw.githubusercontent.com",
        timeout_seconds=1,
        max_retries=kwargs.pop("max_retries", 0),
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
        **kwargs,
    )


def test_repository_metadata_mapping():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World"
        return httpx.Response(200, json={"id": 123, "full_name": "octocat/Hello-World"})

    with make_client(handler) as client:
        data = client.get_repository(parse_repository_url(REPO))
    assert data["id"] == 123


def test_tree_keeps_only_blobs_and_reports_truncation():
    def handler(request):
        assert request.url.params["recursive"] == "1"
        return httpx.Response(
            200,
            json={
                "truncated": True,
                "tree": [
                    {"type": "blob", "path": "a.py", "sha": "abc", "size": 10},
                    {"type": "tree", "path": "src", "sha": "def"},
                    {"type": "blob", "path": "b.ts", "sha": "ghi", "size": 20},
                ],
            },
        )

    with make_client(handler) as client:
        tree = client.get_tree(parse_repository_url(REPO), "abcdef1")
    assert [f.path for f in tree.files] == ["a.py", "b.ts"]
    assert tree.truncated is True


def test_fetch_file_is_size_limited_and_skips_binary():
    def handler(request):
        assert request.url.host == "raw.githubusercontent.com"
        if request.url.path.endswith("big.py"):
            return httpx.Response(200, content=b"x" * 500)
        if request.url.path.endswith("bin.py"):
            return httpx.Response(200, content=b"abc\x00def")
        return httpx.Response(200, content=b"print('hi')\n")

    with make_client(handler) as client:
        ref = parse_repository_url(REPO)
        assert client.fetch_file(ref, "abcdef1", "ok.py", max_bytes=100) == "print('hi')\n"
        assert client.fetch_file(ref, "abcdef1", "big.py", max_bytes=100) is None
        assert client.fetch_file(ref, "abcdef1", "bin.py", max_bytes=100) is None


def test_404_maps_to_not_found():
    with make_client(lambda _r: httpx.Response(404)) as client, pytest.raises(NotFoundError):
        client.get_repository(parse_repository_url(REPO))


def test_rate_limit_maps_to_upstream_error():
    def handler(_request):
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
        )

    with make_client(handler) as client, pytest.raises(UpstreamError) as excinfo:
        client.get_repository(parse_repository_url(REPO))
    assert "rate limit" in excinfo.value.message.lower()


def test_transient_500_is_retried():
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"id": 1})

    with make_client(handler, max_retries=1) as client:
        assert client.get_repository(parse_repository_url(REPO))["id"] == 1
    assert calls["n"] == 2


def test_activity_failure_is_reported_as_unavailable():
    with make_client(lambda _r: httpx.Response(404)) as client:
        result = client.list_workflow_runs(parse_repository_url(REPO))
    assert result.available is False
    assert result.reason
    assert result.items == []


def test_tree_files_can_be_built_from_entries():
    f = GitHubFile(path="src/app.py", sha="a", size=12)
    assert f.path.endswith(".py")
