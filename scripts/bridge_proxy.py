"""Token-protected TCP/HTTP bridge for the web demo (runs on a public jump host, stdlib only).

    python3 bridge_proxy.py --listen 0.0.0.0:8200 --upstream 127.0.0.1:18200 --token <secret>

The upstream is the demo server, reached through an ssh reverse tunnel from the GPU host
(scripts/bridge_tunnel.sh). Open http://<host>:8200/?token=<secret> once: the proxy sets an HttpOnly
cookie and redirects to the same local path and non-token query. Every later connection (page, assets, the /ws WebSocket) must carry the
cookie; anything else gets 401. Ordinary HTTP requests close their upstream connection so a
reverse proxy cannot reuse an authenticated socket for another client. WebSocket upgrades keep
their full-duplex stream. Plain HTTP: the token travels unencrypted.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
import time
from urllib.parse import parse_qs, parse_qsl, quote, urlencode, urlsplit

COOKIE = "la_token"
log = logging.getLogger("bridge")


def _headers(raw: bytes) -> tuple[str, str, dict[str, str]]:
    head = raw.decode("latin-1").split("\r\n")
    method, target, _ = (head[0].split(" ", 2) + ["", ""])[:3]
    hdrs = {}
    for line in head[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            hdrs[k.strip().lower()] = v.strip()
    return method, target, hdrs


def _cookie(hdrs: dict[str, str]) -> str:
    for part in hdrs.get("cookie", "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return ""


def _reply(status: str, body: str, extra: str = "") -> bytes:
    b = body.encode("utf-8")
    return (f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(b)}\r\n"
            f"Cache-Control: no-store\r\nConnection: close\r\n{extra}\r\n").encode("latin-1") + b


def _redirect_location(target: str) -> str:
    """Keep classroom options without reflecting a token or an external authority."""
    parts = urlsplit(target)
    # Always emit an origin-relative path. Encode backslashes and control characters
    # so a supplied request target cannot become a new authority or HTTP header.
    path = quote("/" + parts.path.lstrip("/"), safe="/%:@!$&'()*+,;=-._~")
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                       if key != "token"])
    return path + ("?" + query if query else "")


def _upstream_head(raw: bytes, hdrs: dict[str, str]) -> bytes:
    """Keep authenticated HTTP sockets out of a reverse proxy's connection pool.

    Authentication applies to the first request read by ``handle``. Ordinary HTTP
    must therefore end after that response; only a WebSocket upgrade is a stream
    whose subsequent bytes intentionally belong to the authenticated connection.
    """
    connection = {item.strip().lower() for item in hdrs.get("connection", "").split(",")}
    if hdrs.get("upgrade", "").lower() == "websocket" and "upgrade" in connection:
        return raw
    lines = raw.split(b"\r\n")
    headers = [line for line in lines[1:] if line and
               line.partition(b":")[0].strip().lower() not in
               (b"connection", b"proxy-connection", b"keep-alive")]
    return b"\r\n".join([lines[0], *headers, b"Connection: close", b"", b""])


async def _pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
    try:
        while data := await r.read(65536):
            w.write(data)
            await w.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            w.close()
        except Exception:  # noqa: BLE001
            pass


async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter, upstream: tuple[str, int], token: str) -> None:
    peer = cw.get_extra_info("peername")
    try:
        raw = await asyncio.wait_for(cr.readuntil(b"\r\n\r\n"), timeout=15)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
        cw.close()
        return
    method, target, hdrs = _headers(raw)
    q = parse_qs(urlsplit(target).query)
    if hmac.compare_digest(q.get("token", [""])[0], token):
        location = _redirect_location(target)
        cw.write(_reply("302 Found", "", f"Location: {location}\r\nSet-Cookie: {COOKIE}={token}; HttpOnly; "
                                         f"SameSite=Lax; Max-Age=604800; Path=/\r\n"))
        await cw.drain()
        cw.close()
        log.info("%s token accepted", peer)
        return
    if not hmac.compare_digest(_cookie(hdrs), token):
        cw.write(_reply("401 Unauthorized", "<h3>Live Agent demo</h3><p>需要访问令牌：请使用带 ?token= 的链接打开。</p>"))
        await cw.drain()
        cw.close()
        log.info("%s rejected %s %s", peer, method, target[:80])
        return
    try:
        ur, uw = await asyncio.wait_for(asyncio.open_connection(*upstream), timeout=10)
    except (OSError, asyncio.TimeoutError):
        cw.write(_reply("502 Bad Gateway", "<p>演示服务器未连接（隧道未建立或服务未运行）。</p>"))
        await cw.drain()
        cw.close()
        return
    uw.write(_upstream_head(raw, hdrs))
    await uw.drain()
    await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw))


async def main(args) -> None:
    host, port = args.listen.rsplit(":", 1)
    uh, up = args.upstream.rsplit(":", 1)
    server = await asyncio.start_server(lambda r, w: handle(r, w, (uh, int(up)), args.token), host, int(port),
                                        limit=1 << 16)
    log.info("bridge listening on %s -> %s (%s)", args.listen, args.upstream, time.strftime("%F %T"))
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--listen", default="0.0.0.0:8200")
    p.add_argument("--upstream", default="127.0.0.1:18200")
    p.add_argument("--token", required=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    asyncio.run(main(p.parse_args()))
