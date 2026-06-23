from __future__ import annotations

import asyncio
from collections.abc import Iterator

import httpx
import pytest
from sqlmodel import Session, create_engine, select

from scoutbot_module.db.models import Target
from scoutbot_module.db.repo import create_target
from scoutbot_module.db.session import init_schema
from scoutbot_module.discovery.feeds import extract_feeds
from scoutbot_module.discovery.fetch import fetch_page
from scoutbot_module.discovery.links import extract_links
from scoutbot_module.discovery.socials import extract_socials
from scoutbot_module.discovery.urls import normalize_url, validate_url


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def test_extract_rss_from_html() -> None:
    html = """
    <html>
    <head>
        <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="RSS">
        <link rel="alternate" type="application/atom+xml" href="/atom.xml">
    </head>
    <body>
        <a href="/blog">Blog</a>
        <a href="https://github.com/example/repo">GitHub</a>
        <a href="https://t.me/example_channel">Telegram</a>
        <a href="https://youtube.com/@example">YouTube</a>
    </body>
    </html>
    """
    feeds = extract_feeds(html, "https://example.com")
    assert len(feeds) >= 2
    urls = {f["url"] for f in feeds}
    assert "https://example.com/feed.xml" in urls
    assert "https://example.com/atom.xml" in urls


def test_extract_social_links() -> None:
    html = """
    <html><body>
        <a href="https://github.com/example">GitHub</a>
        <a href="https://t.me/example_channel">Telegram</a>
        <a href="https://youtube.com/@example">YouTube</a>
        <a href="https://x.com/example">X</a>
    </body></html>
    """
    socials = extract_socials(html, "https://example.com")
    urls = {s["url"] for s in socials}
    assert "https://github.com/example" in urls
    assert "https://t.me/example_channel" in urls
    assert "https://youtube.com/@example" in urls


def test_extract_common_pages() -> None:
    html = """
    <html><body>
        <a href="/blog">Blog</a>
        <a href="/docs">Docs</a>
        <a href="/pricing">Pricing</a>
        <a href="/careers">Careers</a>
        <a href="/changelog">Changelog</a>
    </body></html>
    """
    links = extract_links(html, "https://example.com")
    kinds = {link["kind"] for link in links}
    assert "blog" in kinds or any("blog" in link.get("url", "") for link in links)
    urls = {link["url"] for link in links}
    assert "https://example.com/blog" in urls or "https://example.com/blog" in str(
        links
    )


def test_private_network_rejected() -> None:
    with pytest.raises(ValueError):
        validate_url("http://127.0.0.1/test", allow_private_networks=False)

    with pytest.raises(ValueError):
        validate_url("http://10.0.0.1/test", allow_private_networks=False)

    with pytest.raises(ValueError):
        validate_url("http://192.168.1.1/test", allow_private_networks=False)


def test_malformed_url_rejected() -> None:
    with pytest.raises(ValueError):
        validate_url("not-a-url")

    with pytest.raises(ValueError):
        validate_url("ftp://example.com")

    with pytest.raises(ValueError):
        validate_url("")


def test_normalize_url() -> None:
    assert normalize_url("https://Example.COM/Path/") == "https://example.com/Path"
    assert normalize_url("https://example.com#frag") == "https://example.com/"
    assert (
        normalize_url("https://example.com/path?a=1") == "https://example.com/path?a=1"
    )


def test_link_aggregator_detected() -> None:
    html = """
    <html><body>
        <a href="https://linktr.ee/example">Linktree</a>
        <a href="https://bio.link/example">Bio</a>
    </body></html>
    """
    links = extract_links(html, "https://example.com")
    urls = {link["url"] for link in links}
    assert "https://linktr.ee/example" in urls


def test_sitemap_candidate() -> None:
    html = """
    <html><body>
        <a href="/about">About</a>
    </body></html>
    """
    links = extract_links(html, "https://example.com")
    urls = {link["url"] for link in links}
    assert "https://example.com/sitemap.xml" in urls


def test_fetch_page_truncates_response_to_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self) -> None:
            self.url = "https://example.com"
            self.status_code = 200
            self.headers = {"content-type": "text/html; charset=utf-8"}
            self.encoding = "utf-8"

        async def aiter_bytes(self):
            yield b"x" * 8
            yield b"x" * 8
            yield b"x" * 16

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

        def stream(self, method: str, url: str):
            captured["method"] = method
            captured["url"] = url
            return FakeStreamContext()

    class FakeStreamContext:
        async def __aenter__(self) -> FakeResponse:
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

    monkeypatch.setattr(
        "scoutbot_module.discovery.fetch.validate_url",
        lambda url, allow_private_networks=False: None,
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        fetch_page(
            url="https://example.com",
            timeout=10,
            max_response_bytes=10,
            allow_private_networks=False,
        )
    )

    assert len(result["html"]) == 10
    assert result["html"] == "x" * 10
    assert result["truncated"] is True
    assert captured["follow_redirects"] is False


def test_fetch_page_redirect_response_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    class FakeResponse:
        def __init__(self) -> None:
            self.url = "https://example.com/start"
            self.status_code = 302
            self.headers = {
                "content-type": "text/html; charset=utf-8",
                "location": "http://127.0.0.1/private",
            }
            self.encoding = "utf-8"

        async def aiter_bytes(self):
            if False:
                yield b""

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

        def stream(self, method: str, url: str):
            assert method == "GET"
            requested.append(url)
            return FakeStreamContext()

    class FakeStreamContext:
        async def __aenter__(self) -> FakeResponse:
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

    monkeypatch.setattr(
        "scoutbot_module.discovery.fetch.validate_url",
        lambda url, allow_private_networks=False: None,
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(fetch_page(url="https://example.com/start"))

    assert requested == ["https://example.com/start"]
    assert result["status_code"] == 302
    assert result["url"] == "https://example.com/start"


def test_auto_queued_child_target_keeps_parent_target_id(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from scoutbot_module.services.discovery import run_bounded_discovery

    root_target = create_target(
        db_session,
        project_id=None,
        title="Root",
        url="https://example.com",
        kind="website",
        status="queued",
    )

    def fake_discover(url: str, settings: dict) -> dict:
        del url, settings
        return {
            "url": "https://example.com",
            "links": [
                {
                    "url": "https://example.com/blog",
                    "kind": "blog",
                    "relationship": "child",
                    "confidence": 0.9,
                }
            ],
        }

    monkeypatch.setattr(
        "scoutbot_module.services.discovery.discover",
        fake_discover,
        raising=False,
    )
    monkeypatch.setattr(
        "scoutbot_module.discovery.service.discover",
        fake_discover,
    )

    settings = {
        "discovery": {
            "auto_queue": True,
            "allowed_kinds": ["blog"],
            "require_confirmation_kinds": [],
        }
    }

    result = run_bounded_discovery(
        session=db_session,
        target_id=root_target.target_id,
        url=root_target.url,
        settings=settings,
        storage_root=str(tmp_path),
    )

    assert result["children_created"] == 1

    child_target = db_session.exec(
        select(Target).where(Target.url == "https://example.com/blog")
    ).first()
    assert child_target is not None
    assert child_target.parent_target_id == root_target.target_id
