from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import frontend_cache_control


def test_hashed_build_files_are_kept_for_good() -> None:
    assert (
        frontend_cache_control("/assets/index-DltPoCOd.js")
        == "public, max-age=31536000, immutable"
    )
    assert (
        frontend_cache_control("/assets/index-Bx_9-aQz.css")
        == "public, max-age=31536000, immutable"
    )


def test_unhashed_files_and_pages_are_revalidated() -> None:
    # index.html names the current hashes, and a public file keeps its name
    # across deploys, so neither may be served from a stale cache.
    assert frontend_cache_control("/") == "no-cache"
    assert frontend_cache_control("/tasks") == "no-cache"
    assert frontend_cache_control("/assets/images/favicon.png") == "no-cache"


def test_api_responses_keep_their_own_caching() -> None:
    assert frontend_cache_control(f"{settings.API_V1_STR}/tasks/") is None


def test_large_api_responses_are_compressed(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/openapi.json",
        headers={**superuser_token_headers, "Accept-Encoding": "gzip"},
    )
    assert r.status_code == 200
    assert r.headers["content-encoding"] == "gzip"
    assert "cache-control" not in r.headers
