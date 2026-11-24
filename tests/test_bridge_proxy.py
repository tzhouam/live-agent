"""Offline token-bootstrap and forwarding checks; no running services or providers."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qsl, urljoin, urlsplit

import pytest

from scripts import bridge_proxy as bridge


class Writer:
    def __init__(self):
        self.output = bytearray()
        self.closed = False

    def get_extra_info(self, key):
        return ("127.0.0.1", 12345) if key == "peername" else None

    def write(self, data):
        self.output.extend(data)

    async def drain(self):
        pass

    def close(self):
        self.closed = True


def reader(data=b""):
    stream = asyncio.StreamReader()
    stream.feed_data(data)
    stream.feed_eof()
    return stream


async def request(target, cookie=None, extra_headers=()):
    raw = f"GET {target} HTTP/1.1\r\nHost: classroom.test\r\n"
    if cookie:
        raw += f"Cookie: {cookie}\r\n"
    for key, value in extra_headers:
        raw += f"{key}: {value}\r\n"
    raw = (raw + "\r\n").encode("latin-1")
    writer = Writer()
    await bridge.handle(reader(raw), writer, ("127.0.0.1", 18250), "test-secret")
    return writer, raw


def headers(response):
    head = bytes(response).split(b"\r\n\r\n", 1)[0].decode("latin-1")
    return head.split("\r\n")[0], dict(line.split(": ", 1) for line in head.split("\r\n")[1:])


@pytest.mark.asyncio
async def test_bootstrap_preserves_mesh_options_and_removes_every_token(monkeypatch):
    async def unexpected_connection(*args, **kwargs):
        pytest.fail("Token bootstrap must not contact the upstream")

    monkeypatch.setattr(bridge.asyncio, "open_connection", unexpected_connection)
    writer, _ = await request("/?token=test-secret&avatar=mesh&edition=secondary&student=demo"
                              "&token=discard-this-too&tag=a&tag=b&empty=")
    status, result = headers(writer.output)
    assert status == "HTTP/1.1 302 Found"
    assert result["Location"] == "/?avatar=mesh&edition=secondary&student=demo&tag=a&tag=b&empty="
    assert "token" not in dict(parse_qsl(urlsplit(result["Location"]).query))
    assert result["Set-Cookie"] == ("la_token=test-secret; HttpOnly; SameSite=Lax; "
                                     "Max-Age=604800; Path=/")
    assert writer.closed


@pytest.mark.asyncio
async def test_bootstrap_encodes_query_values_without_header_injection():
    writer, _ = await request("/profile?token=test-secret&student=%E5%B0%8F%E6%98%8E"
                              "&note=%0D%0AX-Injected%3A+yes&next=https%3A%2F%2Fevil.test%2F")
    status, result = headers(writer.output)
    assert status == "HTTP/1.1 302 Found"
    location = result["Location"]
    assert location.startswith("/profile?")
    assert "%0D%0AX-Injected%3A+yes" in location
    assert dict(parse_qsl(urlsplit(location).query)) == {
        "student": "小明", "note": "\r\nX-Injected: yes", "next": "https://evil.test/"}
    assert "X-Injected" not in result
    assert "test-secret" not in location


@pytest.mark.parametrize("target", [
    "//evil.test/profile?token=test-secret&avatar=mesh",
    "https://evil.test/profile?token=test-secret&avatar=mesh",
    "/\\evil.test/profile?token=test-secret&avatar=mesh",
    "/%2f%2fevil.test/profile?token=test-secret&avatar=mesh",
    "/\x00profile?token=test-secret&avatar=mesh",
])
def test_redirect_stays_on_the_classroom_origin(target):
    location = bridge._redirect_location(target)
    resolved = urlsplit(urljoin("https://classroom.test/", location))
    assert resolved.scheme == "https" and resolved.netloc == "classroom.test"
    assert location.startswith("/") and not location.startswith("//")
    assert not any(ord(character) < 32 for character in location)
    assert "\\" not in location
    assert dict(parse_qsl(resolved.query)) == {"avatar": "mesh"}


@pytest.mark.asyncio
@pytest.mark.parametrize("target,cookie", [
    ("/?avatar=mesh", None),
    ("/?token=wrong&avatar=mesh", None),
    ("/ws", "la_token=wrong"),
])
async def test_missing_or_invalid_auth_remains_unauthorized(monkeypatch, target, cookie):
    async def unexpected_connection(*args, **kwargs):
        pytest.fail("Unauthorized requests must not contact the upstream")

    monkeypatch.setattr(bridge.asyncio, "open_connection", unexpected_connection)
    writer, _ = await request(target, cookie)
    status, result = headers(writer.output)
    assert status == "HTTP/1.1 401 Unauthorized"
    assert "Location" not in result and "Set-Cookie" not in result
    assert writer.closed


@pytest.mark.asyncio
async def test_existing_cookie_still_forwards_request_and_response(monkeypatch):
    upstream_writer = Writer()
    response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"

    async def connect(host, port):
        assert (host, port) == ("127.0.0.1", 18250)
        return reader(response), upstream_writer

    monkeypatch.setattr(bridge.asyncio, "open_connection", connect)
    writer, raw = await request("/assets/avatar-renderer.js", "la_token=test-secret")
    forwarded = bytes(upstream_writer.output)
    assert forwarded == raw[:-2] + b"Connection: close\r\n\r\n"
    assert bytes(writer.output) == response
    assert writer.closed and upstream_writer.closed


@pytest.mark.parametrize("extra", [
    b"", b"Connection: keep-alive\r\n", b"cOnNeCtIoN: keep-alive\r\nKeep-Alive: timeout=60\r\n",
    b"Connection: keep-alive\r\nProxy-Connection: keep-alive\r\n",
    b"Connection: Upgrade\r\nUpgrade: h2c\r\n",
])
def test_ordinary_http_cannot_reuse_an_authenticated_upstream(extra):
    raw = b"GET /api/health HTTP/1.1\r\nHost: classroom.test\r\n" + extra + b"\r\n"
    _, _, parsed = bridge._headers(raw)
    forwarded = bridge._upstream_head(raw, parsed)
    _, _, upstream = bridge._headers(forwarded)
    assert upstream["connection"] == "close"
    assert "keep-alive" not in upstream and "proxy-connection" not in upstream
    assert forwarded.count(b"Connection: close\r\n") == 1


@pytest.mark.asyncio
async def test_websocket_upgrade_keeps_its_authenticated_stream(monkeypatch):
    upstream_writer = Writer()
    response = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"

    async def connect(host, port):
        return reader(response), upstream_writer

    monkeypatch.setattr(bridge.asyncio, "open_connection", connect)
    writer, raw = await request("/ws", "la_token=test-secret", (
        ("Upgrade", "websocket"), ("Connection", "keep-alive, Upgrade"),
        ("Sec-WebSocket-Key", "dGVzdC13ZWJzb2NrZXQta2V5"), ("Sec-WebSocket-Version", "13")))
    assert bytes(upstream_writer.output) == raw
    assert bytes(writer.output) == response
