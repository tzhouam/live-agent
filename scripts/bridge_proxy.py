"""Token-protected TCP/HTTP bridge for the web demo (runs on a public jump host, stdlib only).

    python3 bridge_proxy.py --listen 0.0.0.0:8200 --upstream 127.0.0.1:18200 --token <secret>

The upstream is the demo server, reached through an ssh reverse tunnel from the GPU host
(scripts/bridge_tunnel.sh). Open http://<host>:8200/?token=<secret> once: the proxy sets an HttpOnly
cookie and redirects to /. Every later connection (page, assets, the /ws WebSocket) must carry the
cookie; anything else gets 401. After the first request of a connection is authorised, bytes are
relayed verbatim (so WebSocket upgrades work). Plain HTTP: the token travels unencrypted.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
import time
from urllib.parse import parse_qs, urlsplit

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
        path = urlsplit(target).path or "/"
        cw.write(_reply("302 Found", "", f"Location: {path}\r\nSet-Cookie: {COOKIE}={token}; HttpOnly; "
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
    uw.write(raw)
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
