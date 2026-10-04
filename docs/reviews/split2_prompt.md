Act as the independent GPT-6 Sol reviewer, read-only, for targeted re-review of split1. All evidence is inlined; do not use shell tools because the host sandbox cannot start. The original owner request is to check the agent and separate frontend/backend. The earlier review and current boundary document are provided. Re-review the concrete fixes for the four findings, and check that those fixes cause no new practical regressions. Do not re-audit unchanged generator/research scope.

Fixes: orderly upstream WebSocket EOF drains downstream pending writes, while error/unexpected close still destroys; a controlled writable callback test reproduces old abrupt-close discard (old code fails), plus slow-client16MiB full-delivery test. Profile periodic fetch captures sid/server, then rechecks dirty, sid/profile identity and visibility before applying; seven controlled real-script regressions, six fail with guard removed. Node minimum is18.2 in package/launcher/README. Decimal port strings normalized before collision check; exact earlier repro now exits2 before GPU use. Current launcher also prevents helper/model/service port overlaps before costly reservations.

Validation is measured on CPU mocks/local sockets, not a GPU runtime or physical lip-sync qualification. Python backend transport/session ASTs match original, unchanged since initial review; reset version behavior and profile sessions remain covered by the existing Python test suite rather than included in this targeted re-review. Give numbered blocking/major/minor actionable findings with evidence and smallest settling check; if resolved without new defects, state that clearly. Do not conflate reported tests with independent code verification.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/reviews/split1_review.md =====
## Findings

1. **Major — WebSocket bytes can be truncated on backend close.** In [frontend/server.mjs](/data/zhoutaichang/live-agent/frontend/server.mjs), `peer.pipe(socket)` is paired with `peer.on('close', () => socket.destroy())`. If the browser reads slowly, `destroy()` can discard writes still queued for it; [Node documents this behavior](https://nodejs.org/download/release/v20.18.1/docs/api/stream.html). The existing test exchanges small frames on loopback. **Smallest check:** pause a WebSocket client, have the mock backend send a large final frame and close, then assert the client receives every byte before EOF.

2. **Major — profile polling can silently erase an unsaved draft.** In [profile.js](/data/zhoutaichang/live-agent/frontend/public/assets/profile.js), the timer checks `dirty` *before* awaiting the profile GET. A user can edit during that request; if a newer version returns, `render()` overwrites the draft and replaces `server.version`. A subsequent save can then succeed without a `409`. **Smallest check:** hold the poll response, edit the name or an exam, return a newer profile, and verify the draft survives or a conflict is shown. The inlined evidence does not establish whether this predates the extraction.

3. **Minor — the declared Node version is too broad.** [package.json](/data/zhoutaichang/live-agent/frontend/package.json) allows Node `>=18`, but the frontend’s signal handler unconditionally calls `server.closeAllConnections()`, which [was added in 18.2.0](https://nodejs.org/download/release/v18.19.1/docs/api/http.html). Shutdown and test teardown fail on 18.0–18.1. **Smallest check:** run the signal test on 18.0 or raise the minimum version to 18.2.

4. **Minor — equivalent port spellings bypass the launcher’s collision check.** [run_live.sh](/data/zhoutaichang/live-agent/scripts/run_live.sh) validates ports numerically but compares their original strings. `PORT=08200 BACKEND_PORT=8200` passes that check, while both processes bind port 8200. **Smallest check:** run the preflight with those values; compare normalized numbers.

By code inspection, all five launcher modes reach the new backend, with `packed` going through `packed_stack.sh`; the frontend starts separately. The compatibility import and repository paths align. HTTP private routes apply `no-store`, and the inspected trace and media routing preserves the intended status and range behavior.

The reported validation exercises the mock stack, not GPU startup or physical lip sync. `ProfileStore.reset` and the model adapter bodies were not inlined, so reset version monotonicity, active-session reset notification, and GPU mode runtime remain unverified.
===== FILE: docs/reviews/split1_results.md =====
# Frontend/backend refactor validation — 2026-10-02

All counts and observed outcomes below are **measured locally** on the CPU mock stack. Port numbers
and HTTP status codes identify configuration/protocol values, not performance measurements.

- `python3 -m pytest`: **363 passed, 1 skipped**. The skipped test requires a real TaoMate GPU run.
  Existing FastAPI startup-handler and Torch deprecation warnings remain. A timestamp fallback regression
  was added after collection; `python3 -m pytest tests/test_backend_api.py` subsequently passed **5 tests**,
  including the new case before and after client clock synchronization.
- `npm --prefix frontend test`: **19 passed**. Includes browser API helper behavior and real local
  HTTP/WebSocket proxy tests: streaming delivery, binary order, both handshake head buffers, ranges,
  HTTP errors, stale-profile status propagation, client abort, static path/symlink containment and
  frontend shutdown with active WebSockets under SIGINT and SIGTERM.
- `python3 scripts/lipsync_page_check.py http://127.0.0.1:18210 --seconds 6 --warmup 2`: exit **0**, every
  check `ok: true`, no browser page errors. Separate mock backend on loopback port `18211`, memory disabled,
  isolated student/trace directories. Covers playback offsets, injected output latency, offset changes
  across request boundaries, render-error fallback, stop on a new comment, reconnect and calibration.
- Chromium profile/trace smoke check against the same frontend: profile loads, a versioned edit saves,
  stale version returns `409`, reset succeeds, and the empty trace page renders. No browser page errors.
  The student store was isolated from existing user profiles.
- `PORT=18220 BACKEND_PORT=18221 RECORD=0 READY_TIMEOUT=20 scripts/run_live.sh demo`: frontend and backend
  started separately, proxied `/api/health` returned `status: ok`, direct backend `/` returned `404`,
  Ctrl-C exited the launcher and stopped its children.
- `bash -n` for changed shell scripts and `git diff --check`: passed.

Inspection of the moved transport and WebSocket session function ASTs found their behavior unchanged.
A missing import of the server clock function was caught in the contributor review and restored before
browser validation. The previous `/traces` HTML renderer was replaced with `/api/traces` JSON plus a
frontend view; session video matching now excludes another session sharing its filename prefix.

These checks verify the separation and the local mock path. They do **not** measure generator throughput,
qualify the GPU stack, evaluate teaching quality or establish physical display/audio alignment. No training,
GPU reservation, deployment or public broadcast was performed for this refactor.

## Additional checks after the first review

- Final frontend code exercised in Chromium: live playback and a typed instruction, nonempty trace API,
  and terminating the frontend with an active browser session. All succeeded, no page errors.
- Launcher failure paths: an occupied backend port rejects before any frontend or GPU start; a sleeping
  fake backend reaches the readiness timeout, prints no ready message and cleans its frontend process.
  SIGTERM of the actual mock stack closes both listeners. No GPU reservations made.
- `PORT=08200 BACKEND_PORT=8200 scripts/run_live.sh full`: exit **2** before acquiring GPUs, with
  `PORT and BACKEND_PORT must be different`. Numeric normalization rejects equivalent port spellings.
- Profile polling regression (pre-existing before extraction): a pending clean-page refresh used to apply
  after the user began editing or after a newer profile loaded. Controlled-response tests now exercise
  the real script's name/exam edits, save, reload, student switch, overlapping polls and hidden-page guard.
  All **7** pass; removing the guard produces **6** failures, confirming that the tests detect the race.
- The launcher version guard accepts Node **18.2** or newer and rejects older versions, matching the
  frontend shutdown API requirement. These are runtime version identifiers.

Test counts, exit outcomes and browser observations here are **measured locally**. Contributor inspection
confirmed the GPU reservation marker is preserved in installed canhazgpu status output; actual GPU worker
shutdown remains untested. All local smoke-test services were stopped after validation.

## Review repairs

- Final `npm --prefix frontend test`: **28 passed** (measured locally).
- WebSocket orderly EOF now relies on `pipe`/`end` to drain writes instead of destroying the downstream
  socket. A deterministic controlled pending-write test holds binary output while observing upstream
  close; the previous implementation destroys the downstream with bytes still queued, and the fixed
  implementation delivers the pending bytes. The regression fails on the previous code and passes on
  the fix. Ordinary slow TCP runs did not reproduce truncation; the additional slow-client test verifies
  complete delivery of a **16 MiB** payload (measured test payload size), without assuming host TCP
  buffers always create observable backpressure.
- Package runtime and launcher guard both require Node **18.2** or newer. Equivalent decimal port
  spellings are normalized before collision checks.

===== FILE: docs/frontend_backend.md =====
# Frontend and backend boundary

Implemented on the owner's request on 2026-10-02 (D-045). This is an engineering refactor of the existing
agent. Its director, generators, scoped memory, judging and evaluation remain in Python.

## Components

| Component | Entry point | Responsibility |
|---|---|---|
| Browser frontend | `frontend/public/` | Live stage, audio/video playback and presentation acknowledgements, controls, profile editor, trace browser |
| Frontend server | `frontend/server.mjs` | Static assets and a streaming same-origin HTTP/WebSocket proxy; Node built-in modules only |
| Backend | `python3 -m live_agent.backend.app` | FastAPI resource APIs, session orchestration, model clients, private storage and media |
| Compatibility entry point | `python3 -m live_agent.server.app` | Delegates to the backend; it serves the same API and no browser pages |

The frontend and backend have independent processes and ports. The default frontend address is
`http://127.0.0.1:8200`; its backend upstream is `http://127.0.0.1:8201`. These are configuration values,
not performance claims. Browser requests use their current origin, so HTTPS proxies and existing SSH
tunnels only need to expose the frontend. Credentials for model services stay in the backend environment.

```mermaid
flowchart LR
    Browser[Browser: HTML / CSS / JavaScript] -->|HTTP and WebSocket, same origin| Frontend[Node frontend server]
    Frontend -->|static pages and assets| Assets[frontend/public]
    Frontend -->|proxied HTTP and /ws| Backend[FastAPI backend]
    Backend --> Agent[Director / orchestrator / memory / models]
```

## HTTP interface

| Route | Owner | Result |
|---|---|---|
| `GET /`, `/profile`, `/traces` | Frontend | Browser pages |
| `GET /assets/*` | Frontend | CSS and classic JavaScript files |
| `GET /api/health` | Backend | `{status: "ok", generator, protocol_version: 1}` after backend startup |
| `GET /api/curriculum` | Backend | Existing course-knowledge summary |
| `GET /api/students` | Backend | Operator-allowed student IDs and basic profile metadata |
| `GET /api/students/{id}` | Backend | Current profile, including its version |
| `PUT /api/students/{id}` | Backend | Apply a validated edit, requiring the current `version` |
| `POST /api/students/{id}/reset` | Backend | Reset to the seed, requiring the current `version` |
| `GET /api/traces` | Backend | Structured recorded-session index |
| `GET /traces/file/{name}` | Backend | JSONL or MP4 download; MP4 supports HTTP range requests |
| `GET /board/img/{name}` | Backend | Existing content-addressed board PNG |

The frontend proxy preserves HTTP methods, request bodies, upstream status codes and media streaming.
Unknown student IDs return HTTP `404`; stale profile versions return `409`; invalid profile edits return
`422`. Private APIs, trace files and board images carry `Cache-Control: no-store`. The backend does not
serve `/`, `/profile` or `/traces` views. Protocol and HTTP status numbers here identify interfaces, not
measurements.

`GET /api/traces` returns:

```json
{
  "sessions": [
    {
      "id": "sess-example",
      "updated_at": "2026-10-02T00:00:00+00:00",
      "size_bytes": 1024,
      "trace_url": "/traces/file/sess-example.jsonl",
      "videos": [
        {"name": "sess-example.mp4", "label": "presented", "url": "/traces/file/sess-example.mp4"}
      ]
    }
  ]
}
```

The timestamp and byte count above are illustrative values. Entries are sorted by modification time,
newest first, and include only recognized session filenames. Video parts are matched to their own session
rather than all filenames sharing an arbitrary prefix. URLs are relative to the frontend origin.

## WebSocket interface

`/ws` retains the existing protocol. The frontend proxy forwards the byte stream without decoding media.
The browser sends a `hello` message with private/public mode, user ID, selected student and supported video
codecs. The backend returns `status`, panel `event`/`state`, user `transcript`, and `chunk` messages.

A `chunk` JSON header contains request and chunk indices, frame count, FPS, sample rate, media duration,
dimensions, scripted transcript, codec and optional board view. For JPEG, the header is followed by one
binary message per frame and a PCM16 binary message. For H.264, it is followed by one Annex-B segment
(access-unit byte lengths in `sizes`) and a PCM16 message. Frame and sample clocks are preserved.

The browser sends `chunk_received`, `chunk_start`, `chunk_end` and clock samples. These remain the backend's
evidence of delivery and presentation; proxy arrival is not treated as user-visible playback. `stop` drops
queued playback on interruption or erasure. Push-to-talk audio, camera opt-in, codec fallback, profile
updates and ping/pong messages retain their current handling. UI captions remain scripted and unverified,
as described in `docs/implementation.md`.

## Local operation and verification

`scripts/run_live.sh demo` supervises the separate frontend and mock backend. Independent start commands,
model-backed modes and environment variables are in `README.md`. A different frontend port requires no
browser code changes; point its `BACKEND_URL` at the desired backend. This local refactor does not deploy
the services or authorize a public broadcast.

Run `python3 -m pytest` for the Python suite and `npm --prefix frontend test` for the browser API helper and
frontend HTTP/WebSocket proxy tests. The existing `scripts/lipsync_page_check.py` should be pointed at the
frontend URL to exercise the extracted playback code through the proxy. These checks do not qualify the
GPU path, model quality or physical audio/video alignment.

===== FILE: frontend/server.mjs =====
import http from 'node:http';
import https from 'node:https';
import { createReadStream } from 'node:fs';
import { realpath, stat } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { isIP } from 'node:net';
import { PassThrough } from 'node:stream';
import { fileURLToPath } from 'node:url';

const frontendDir = dirname(fileURLToPath(import.meta.url));
const hopHeaders = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
]);
const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
};

function backendAddress(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
      || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('BACKEND_URL must be an http(s) origin without credentials, a path, or a query');
  }
  return url;
}

function pathFromRequest(req) {
  const rawPath = req.url.split('?')[0];
  if (!rawPath.startsWith('/') || rawPath.startsWith('//')) throw new Error('Invalid path');
  const path = decodeURIComponent(rawPath);
  if (/[\\\0]/.test(path) || path.split('/').some(part => part === '.' || part === '..')) {
    throw new Error('Invalid path');
  }
  return path;
}

function filteredHeaders(headers) {
  const blocked = new Set(hopHeaders);
  for (const name of (headers.connection || '').split(',')) blocked.add(name.trim().toLowerCase());
  return Object.fromEntries(Object.entries(headers).filter(([name]) => !blocked.has(name.toLowerCase())));
}

function privateHeaders(headers) {
  return {
    ...filteredHeaders(headers),
    'cache-control': 'no-store',
    pragma: 'no-cache',
    expires: '0',
  };
}

function errorResponse(res, status, message) {
  if (res.destroyed || res.writableEnded) return;
  if (res.headersSent) {
    res.destroy();
    return;
  }
  res.writeHead(status, {
    'content-type': 'text/plain; charset=utf-8',
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  });
  res.end(message);
}

function proxyRequest(req, res, backend) {
  const transport = backend.protocol === 'https:' ? https : http;
  const upstream = transport.request(backend, {
    method: req.method,
    path: req.url,
    headers: { ...filteredHeaders(req.headers), host: backend.host },
  });
  let response;
  const cleanup = () => {
    upstream.destroy();
    response?.destroy();
  };
  req.on('aborted', cleanup);
  req.on('error', cleanup);
  res.on('close', cleanup);
  upstream.on('error', () => errorResponse(res, 502, 'Backend unavailable\n'));
  upstream.on('response', incoming => {
    response = incoming;
    if (res.destroyed) return cleanup();
    res.writeHead(incoming.statusCode, privateHeaders(incoming.headers));
    incoming.on('error', () => res.destroy());
    incoming.on('aborted', () => res.destroy());
    incoming.pipe(res);
  });
  req.pipe(upstream);
}

function socketResponse(socket, status, headers, statusMessage = http.STATUS_CODES[status]) {
  const lines = [`HTTP/1.1 ${status} ${statusMessage}`];
  for (const [name, value] of Object.entries(headers)) {
    for (const item of Array.isArray(value) ? value : [value]) lines.push(`${name}: ${item}`);
  }
  socket.write(`${lines.join('\r\n')}\r\n\r\n`);
}

function socketError(socket, status, message) {
  if (socket.destroyed || socket.writableEnded) return;
  const body = `${message}\n`;
  socketResponse(socket, status, {
    'content-type': 'text/plain; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
    connection: 'close',
  });
  socket.end(body);
}

function proxyUpgrade(req, socket, head, backend) {
  // Buffer early client frames with stream backpressure while the backend
  // handshake is pending. Reading also lets a disconnected client cancel it.
  const clientInput = new PassThrough();
  if (head.length) clientInput.write(head);
  socket.pipe(clientInput);
  const transport = backend.protocol === 'https:' ? https : http;
  const upstream = transport.request(backend, {
    method: req.method,
    path: req.url,
    headers: {
      ...filteredHeaders(req.headers),
      host: backend.host,
      connection: 'Upgrade',
      upgrade: req.headers.upgrade,
    },
  });
  let upstreamSocket;
  let response;
  let upgraded = false;
  const cleanup = () => {
    clientInput.destroy();
    upstream.destroy();
    upstreamSocket?.destroy();
    response?.destroy();
  };
  socket.on('error', cleanup);
  socket.on('close', cleanup);
  socket.on('end', () => {
    cleanup();
    socket.destroy();
  });
  upstream.on('error', () => {
    if (upgraded) socket.destroy();
    else socketError(socket, 502, 'Backend unavailable');
  });
  upstream.on('upgrade', (incoming, peer, upstreamHead) => {
    upstreamSocket = peer;
    upgraded = true;
    if (socket.destroyed) return cleanup();
    const lines = [`HTTP/1.1 ${incoming.statusCode} ${incoming.statusMessage}`];
    for (let index = 0; index < incoming.rawHeaders.length; index += 2) {
      lines.push(`${incoming.rawHeaders[index]}: ${incoming.rawHeaders[index + 1]}`);
    }
    socket.write(`${lines.join('\r\n')}\r\n\r\n`);
    // Node has already consumed these bytes while parsing each handshake.
    if (upstreamHead.length) socket.write(upstreamHead);
    peer.on('error', () => socket.destroy());
    peer.on('close', hadError => {
      // pipe() ends the downstream on normal EOF and lets pending writes drain.
      // Destroying it here would discard bytes still in its writable buffer.
      if (hadError || !peer.readableEnded) socket.destroy();
    });
    clientInput.pipe(peer);
    peer.pipe(socket);
  });
  upstream.on('response', incoming => {
    // A refused upgrade is an ordinary HTTP response; retain its status/body.
    response = incoming;
    if (socket.destroyed) return cleanup();
    socketResponse(socket, incoming.statusCode, {
      ...privateHeaders(incoming.headers), connection: 'close',
    }, incoming.statusMessage);
    incoming.on('error', () => socket.destroy());
    incoming.on('aborted', () => socket.destroy());
    incoming.pipe(socket);
  });
  upstream.end();
}

async function serveStatic(req, res, path, publicDir) {
  if (!['GET', 'HEAD'].includes(req.method)) {
    res.setHeader('allow', 'GET, HEAD');
    return errorResponse(res, 405, 'Method not allowed\n');
  }
  const pages = { '/': 'index.html', '/profile': 'profile.html', '/traces': 'traces.html' };
  const relative = pages[path] ?? path.slice(1);
  if (relative.split('/').some(part => part.startsWith('.'))) {
    return errorResponse(res, 404, 'Not found\n');
  }
  try {
    const root = await realpath(publicDir);
    const filename = await realpath(resolve(root, relative));
    if (!filename.startsWith(`${root}${sep}`)) return errorResponse(res, 404, 'Not found\n');
    const info = await stat(filename);
    if (!info.isFile()) return errorResponse(res, 404, 'Not found\n');
    if (res.destroyed) return;
    res.writeHead(200, {
      'content-type': mimeTypes[extname(filename).toLowerCase()] ?? 'application/octet-stream',
      'content-length': info.size,
      'cache-control': 'no-cache',
      'x-content-type-options': 'nosniff',
    });
    if (req.method === 'HEAD') return res.end();
    const stream = createReadStream(filename);
    stream.on('error', () => res.destroy());
    res.on('close', () => stream.destroy());
    stream.pipe(res);
  } catch (error) {
    if (['ENOENT', 'ENOTDIR', 'EACCES'].includes(error.code)) errorResponse(res, 404, 'Not found\n');
    else errorResponse(res, 500, 'Unable to read frontend asset\n');
  }
}

/** Serve the browser application and relay private backend streams on one origin. */
export function createFrontendServer({
  backendUrl = 'http://127.0.0.1:8201',
  publicDir = resolve(frontendDir, 'public'),
} = {}) {
  const backend = backendAddress(backendUrl);
  const server = http.createServer((req, res) => {
    let path;
    try { path = pathFromRequest(req); }
    catch { return errorResponse(res, 400, 'Invalid path\n'); }
    if (path.startsWith('/api/') || path.startsWith('/board/img/') || path.startsWith('/traces/file/')) {
      proxyRequest(req, res, backend);
    } else {
      void serveStatic(req, res, path, publicDir);
    }
  });
  const upgradedSockets = new Set();
  server.on('upgrade', (req, socket, head) => {
    // Install an error listener even for rejected upgrade paths.
    socket.on('error', () => socket.destroy());
    let path;
    try { path = pathFromRequest(req); }
    catch { return socketError(socket, 400, 'Invalid path'); }
    if (path !== '/ws' || req.headers.upgrade?.toLowerCase() !== 'websocket') {
      return socketError(socket, 404, 'Not found');
    }
    upgradedSockets.add(socket);
    socket.on('close', () => upgradedSockets.delete(socket));
    proxyUpgrade(req, socket, head, backend);
  });
  // Node's HTTP shutdown leaves upgraded sockets open. Close them before the
  // HTTP server so backend sessions are released even during process shutdown.
  const closeHttpServer = server.close.bind(server);
  server.close = (...args) => {
    for (const socket of upgradedSockets) socket.destroy();
    return closeHttpServer(...args);
  };
  return server;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const host = process.env.HOST ?? '127.0.0.1';
    const portText = process.env.PORT ?? '8200';
    if (!host || (!isIP(host) && !/^[a-zA-Z0-9._-]+$/.test(host))) throw new Error('HOST must be a hostname or IP address');
    if (!/^\d+$/.test(portText) || Number(portText) > 65535) throw new Error('PORT must be an integer from 0 to 65535');
    const server = createFrontendServer({ backendUrl: process.env.BACKEND_URL });
    server.on('error', error => {
      console.error(`Frontend failed: ${error.message}`);
      process.exitCode = 1;
    });
    server.listen(Number(portText), host, () => {
      const address = server.address();
      const displayHost = isIP(host) === 6 ? `[${host}]` : host;
      console.log(`Live Agent frontend: http://${displayHost}:${address.port}`);
    });
    for (const signal of ['SIGINT', 'SIGTERM']) {
      process.once(signal, () => {
        server.close();
        server.closeAllConnections();
      });
    }
  } catch (error) {
    console.error(`Frontend configuration error: ${error.message}`);
    process.exitCode = 1;
  }
}

===== FILE: frontend/package.json =====
{
  "name": "live-agent-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "node server.mjs",
    "test": "node --test tests/*.test.mjs"
  },
  "engines": {
    "node": ">=18.2"
  }
}

===== FILE: frontend/public/assets/profile.js =====
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const LEVEL = {mastered: "已掌握", partial: "基本理解", weak: "薄弱", unknown: "未评估"};
const GRADES = ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"];
$("grades").innerHTML = GRADES.map(g => `<option value="${g}">`).join("");

let sid = new URLSearchParams(location.search).get("student") || "";
let server = null;          // the profile as last loaded
let exams = [];             // editable copy
let edits = new Map();      // concept name -> {mastery?, delete?, subject?}
let dirty = false;

function setStatus(text, cls) { const el = $("status"); el.textContent = text; el.className = "status " + (cls || ""); }
function markDirty() {
  dirty = true; $("save").disabled = false; $("discard").disabled = false;
  setStatus("有未保存的修改", "dirty");
}
function clean() { dirty = false; $("save").disabled = true; $("discard").disabled = true; }

const api = window.LiveAgentAPI.fetchJson;

async function loadList() {
  const {students} = await api("/api/students");
  if (!students.length) { setStatus("服务器没有开放任何学生档案", "err"); return; }
  if (!students.some(s => s.id === sid)) sid = students[0].id;
  $("student").innerHTML = students.map(s =>
    `<option value="${esc(s.id)}"${s.id === sid ? " selected" : ""}>${esc(s.name || s.id)}${s.grade ? " · " + esc(s.grade) : ""} (${esc(s.id)})</option>`).join("");
  await load();
}

async function load() {
  server = await api(`/api/students/${encodeURIComponent(sid)}`);
  exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
  edits = new Map(); $("clearHist").checked = false;
  history.replaceState(null, "", `?student=${encodeURIComponent(sid)}`);
  $("back").href = "/";
  render(); clean();
  setStatus(`已载入 · 版本 ${server.version}${server.saved ? "" : " · 尚未保存过（显示的是初始档案）"}`, "ok");
}

function render() {
  $("name").value = server.name || ""; $("grade").value = server.grade || "";
  $("meta").textContent = `档案编号 ${server.id} · 版本 ${server.version}`;
  renderExams(); renderConcepts(); renderHistory();
}

function renderExams() {
  const el = $("exams");
  if (!exams.length) { el.innerHTML = `<div class="empty">还没有考试成绩。</div>`; return; }
  el.innerHTML = exams.map((e, i) => {
    const pct = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
    return `<div class="exam" data-i="${i}">
      <label>学科 <input data-k="subject" value="${esc(e.subject)}" maxlength="12"></label>
      <label>考试 <input data-k="name" value="${esc(e.name)}" maxlength="20" placeholder="如 期中考试"></label>
      <label>日期 <input data-k="date" type="date" value="${esc(e.date)}"></label>
      <label>分数 <input data-k="score" type="number" min="0" step="0.5" value="${esc(e.score)}"></label>
      <label>满分 <input data-k="full" type="number" min="1" step="1" value="${esc(e.full)}"></label>
      <label>失分知识点 <input data-k="weak" value="${esc(e.weak)}" placeholder="如 因式分解、浮力"></label>
      <span class="pct">${pct}</span>
      <button class="ghost" data-del="${i}" aria-label="删除这次考试">删除</button></div>`;
  }).join("");
}
$("exams").addEventListener("input", (ev) => {
  const row = ev.target.closest(".exam"), k = ev.target.dataset.k;
  if (!row || !k) return;
  const e = exams[+row.dataset.i];
  e[k] = (k === "score" || k === "full") ? (ev.target.value === "" ? "" : +ev.target.value) : ev.target.value;
  if (k === "score" || k === "full") row.querySelector(".pct").textContent = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
  markDirty();
});
$("exams").addEventListener("click", (ev) => {
  const i = ev.target.dataset.del;
  if (i === undefined) return;
  exams.splice(+i, 1); renderExams(); markDirty();
});
$("addExam").onclick = () => {
  exams.push({subject: "", name: "", date: new Date().toISOString().slice(0, 10), score: "", full: 100, weak: ""});
  renderExams(); markDirty();
  $("exams").lastElementChild.querySelector("input").focus();
};

function srcText(c) {
  if (c.source === "manual") return `<span class="src manual">老师设定</span>`;
  if (c.source === "exercise") return `<span class="src">练习 ${c.correct}/${c.attempts} 对</span>`;
  if (c.source === "exam") return `<span class="src">据考试失分推断</span>`;
  return `<span class="src">未评估</span>`;
}
function levelOf(m, c) {
  if (m == null) return "unknown";
  if (m >= 0.8) return (c.attempts >= 3 || c.source === "manual" || edits.get(c.name)?.mastery != null) ? "mastered" : "partial";
  return m >= 0.5 ? "partial" : "weak";
}
function renderConcepts() {
  const el = $("concepts");
  const list = server.concepts.slice();
  for (const [name, e] of edits) if (e.added && !list.some(c => c.name === name))
    list.push({name, subject: e.subject || "", mastery: null, source: null, attempts: 0, correct: 0, notes: []});
  if (!list.length) { el.innerHTML = `<div class="empty">还没有知识点记录。做练习或在下面添加。</div>`; return; }
  el.innerHTML = list.map(c => {
    const e = edits.get(c.name) || {};
    const m = "mastery" in e ? e.mastery : c.mastery;
    const lvl = levelOf(m, c);
    const pct = m == null ? "–" : (c.source === "exam" && !("mastery" in e) ? "≈" : "") + Math.round(m * 100) + "%";
    const src = "mastery" in e ? (e.mastery == null ? `<span class="src">将清除</span>` : `<span class="src manual">老师设定（未保存）</span>`) : srcText(c);
    return `<div class="concept ${lvl}${e.delete ? " removed" : ""}${Object.keys(e).length ? " changed" : ""}" data-name="${esc(c.name)}">
      <span class="name">${esc(c.name)}</span>
      <span class="muted">${esc(c.subject || "")}</span>
      <span class="grow"><input type="range" min="0" max="100" value="${m == null ? 50 : Math.round(m * 100)}" aria-label="${esc(c.name)} 掌握度"
               title="拖动即由老师设定掌握度"></span>
      <span class="v">${pct}</span>
      <span class="grow">${src}${c.notes && c.notes.length ? `<div class="muted">最近的错误：${esc(c.notes[c.notes.length - 1])}</div>` : ""}
        <div class="muted">${LEVEL[lvl]}</div></span>
      <span class="row" style="gap:4px">
        <button class="ghost" data-act="clear" title="清除估计（回到考试推断的估计；没有考试记录则为未评估）">清除</button>
        <button class="ghost" data-act="${e.delete ? "undo" : "delete"}">${e.delete ? "撤销" : "删除"}</button></span></div>`;
  }).join("");
}
$("concepts").addEventListener("input", (ev) => {
  if (ev.target.type !== "range") return;
  const name = ev.target.closest(".concept").dataset.name;
  edits.set(name, {...(edits.get(name) || {}), mastery: +ev.target.value / 100, delete: false});
  const row = ev.target.closest(".concept");
  row.querySelector(".v").textContent = ev.target.value + "%";
  markDirty();
});
$("concepts").addEventListener("change", (ev) => { if (ev.target.type === "range") renderConcepts(); });
$("concepts").addEventListener("click", (ev) => {
  const act = ev.target.dataset.act; if (!act) return;
  const name = ev.target.closest(".concept").dataset.name, e = edits.get(name) || {};
  if (act === "clear") edits.set(name, {...e, mastery: null, delete: false});
  if (act === "delete") edits.set(name, {...e, delete: true});
  if (act === "undo") { const {delete: _, ...rest} = e; Object.keys(rest).length ? edits.set(name, rest) : edits.delete(name); }
  renderConcepts(); markDirty();
});
$("addConcept").onclick = () => {
  const name = $("newName").value.trim(); if (!name) { $("newName").focus(); return; }
  const raw = $("newMastery").value.trim();
  const e = {added: true, subject: $("newSubject").value.trim()};
  if (raw !== "") e.mastery = Math.max(0, Math.min(100, +raw)) / 100;
  edits.set(name, e);
  $("newName").value = ""; $("newMastery").value = "";
  renderConcepts(); markDirty();
};

function renderHistory() {
  const h = server.history || [];
  $("hist").innerHTML = h.length ? h.map(x => `<tr><td>${esc(x.t)}</td><td>${esc(x.concept)}</td>
      <td class="${x.correct ? "ok" : "bad"}">${x.correct ? "答对" : "答错"}</td><td>${esc(x.question)}</td><td>${esc(x.answer)}</td></tr>`).join("")
    : `<tr><td colspan="5" class="empty">还没有练习记录。</td></tr>`;
}

["name", "grade"].forEach(id => $(id).addEventListener("input", markDirty));
$("clearHist").addEventListener("change", markDirty);

$("save").onclick = async () => {
  const bad = exams.find(e => !String(e.subject).trim() || e.score === "" || !(e.full > 0));
  if (bad) { setStatus("每次考试都要填写学科、分数和满分", "err"); return; }
  const body = {
    version: server.version, name: $("name").value.trim(), grade: $("grade").value.trim(),
    exams: exams.map(e => ({subject: e.subject.trim(), name: e.name.trim(), date: e.date, score: +e.score, full: +e.full,
                            weak: String(e.weak).split(/[、,，;；\s]+/).filter(Boolean)})),
    concepts: [...edits].map(([name, e]) => ({name, ...(e.delete ? {delete: true} : {}),
      ...("mastery" in e && !e.delete ? {mastery: e.mastery} : {}), ...(e.added ? {subject: e.subject} : {})})),
    clear_history: $("clearHist").checked,
  };
  $("save").disabled = true; setStatus("保存中…");
  try {
    server = await api(`/api/students/${encodeURIComponent(sid)}`, {method: "PUT", body: JSON.stringify(body)});
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false; render(); clean();
    setStatus(`已保存 · 版本 ${server.version} · 正在上课的页面会自动更新`, "ok");
  } catch (err) {
    $("save").disabled = false;
    if (err.status === 409) setStatus("保存失败：你编辑时档案被更新了（例如课堂上刚批改了一道练习）。请「放弃修改」重新载入后再改。", "err");
    else setStatus("保存失败：" + err.message, "err");
  }
};
$("discard").onclick = () => load().catch(e => setStatus("载入失败：" + e.message, "err"));
$("reset").onclick = async () => {
  if (!confirm(`确定把「${server.name || sid}」的档案恢复为初始档案吗？保存的成绩、掌握度和练习记录都会删除。`)) return;
  try { server = await api(`/api/students/${encodeURIComponent(sid)}/reset`, {method: "POST", body: JSON.stringify({version: server.version})}); await load(); setStatus("已恢复为初始档案", "ok"); }
  catch (err) { setStatus("恢复失败：" + err.message, "err"); }
};
$("student").onchange = async () => {
  if (dirty && !confirm("有未保存的修改，切换学生会丢弃它们。继续吗？")) { $("student").value = sid; return; }
  sid = $("student").value; await load();
};
window.addEventListener("beforeunload", (ev) => { if (dirty) { ev.preventDefault(); ev.returnValue = ""; } });

// while nothing is being edited, follow changes made by a running lesson (graded exercises)
setInterval(async () => {
  if (dirty || !server || document.hidden) return;
  const refreshSid = sid, refreshProfile = server;
  try {
    const now = await api(`/api/students/${encodeURIComponent(refreshSid)}`);
    // Fetching can overlap edits, saves, student changes or another refresh.
    if (dirty || sid !== refreshSid || server !== refreshProfile || document.hidden) return;
    if (now.version !== server.version) { server = now; exams = now.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
      render(); setStatus(`已自动更新（课堂中有新的练习结果）· 版本 ${now.version}`, "ok"); }
  } catch (_) { /* offline for a moment: try again next time */ }
}, 5000);

loadList().catch(e => setStatus("载入失败：" + e.message, "err"));

===== FILE: frontend/tests/server.test.mjs =====
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import http from 'node:http';
import net from 'node:net';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { mkdtemp, mkdir, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { createFrontendServer } from '../server.mjs';

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}

function manageServer(t, server) {
  const sockets = new Set();
  server.on('connection', socket => {
    sockets.add(socket);
    socket.on('close', () => sockets.delete(socket));
  });
  t.after(async () => {
    for (const socket of sockets) socket.destroy();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  });
  return server;
}

function request(port, path, { method = 'GET', headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const outgoing = http.request({
      hostname: '127.0.0.1', port, path, method, headers, agent: false,
    }, incoming => {
      const chunks = [];
      incoming.on('data', chunk => chunks.push(chunk));
      incoming.on('error', reject);
      incoming.on('end', () => resolve({
        status: incoming.statusCode,
        headers: incoming.headers,
        body: Buffer.concat(chunks),
      }));
    });
    outgoing.on('error', reject);
    outgoing.end(body);
  });
}

async function fixture(t, handler = (_req, res) => res.end('backend')) {
  const directory = await mkdtemp(join(tmpdir(), 'live-agent-frontend-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const publicDir = join(directory, 'public');
  await mkdir(join(publicDir, 'assets'), { recursive: true });
  await Promise.all([
    writeFile(join(publicDir, 'index.html'), '<title>Live</title>'),
    writeFile(join(publicDir, 'profile.html'), '<title>Profile</title>'),
    writeFile(join(publicDir, 'traces.html'), '<title>Traces</title>'),
    writeFile(join(publicDir, 'assets', 'app.js'), 'window.ready = true;'),
    writeFile(join(publicDir, '.private'), 'hidden secret'),
    writeFile(join(directory, 'private.txt'), 'outside secret'),
  ]);
  await symlink(join(directory, 'private.txt'), join(publicDir, 'outside.txt'));
  const backend = manageServer(t, http.createServer(handler));
  const backendPort = await listen(backend);
  const frontend = manageServer(t, createFrontendServer({
    backendUrl: `http://127.0.0.1:${backendPort}`, publicDir,
  }));
  const port = await listen(frontend);
  return { port, backend, backendPort, frontend, publicDir };
}

test('static pages and assets are isolated to the public directory', { timeout: 10000 }, async t => {
  const { port } = await fixture(t);
  for (const [path, title] of [
    ['/', 'Live'], ['/profile', 'Profile'], ['/profile.html', 'Profile'],
    ['/traces', 'Traces'], ['/traces.html', 'Traces'],
  ]) {
    const result = await request(port, path);
    assert.equal(result.status, 200);
    assert.match(result.headers['content-type'], /text\/html/);
    assert.equal(result.body.toString(), `<title>${title}</title>`);
  }
  const asset = await request(port, '/assets/app.js?version=demo');
  assert.equal(asset.status, 200);
  assert.match(asset.headers['content-type'], /javascript/);
  assert.equal(asset.body.toString(), 'window.ready = true;');
  const head = await request(port, '/', { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(head.body.length, 0);
  assert.equal(Number(head.headers['content-length']), Buffer.byteLength('<title>Live</title>'));
  for (const path of ['/server.mjs', '/private.txt', '/outside.txt', '/.private', '/assets/']) {
    assert.equal((await request(port, path)).status, 404, path);
  }
  for (const path of ['/../private.txt', '/%2e%2e/private.txt', '/assets/%2e%2e/index.html', '/%00', '/%5cprivate.txt', '/%zz']) {
    assert.equal((await request(port, path)).status, 400, path);
  }
  const refused = await request(port, '/', { method: 'POST', body: 'ignored' });
  assert.equal(refused.status, 405);
  assert.equal(refused.headers.allow, 'GET, HEAD');
});

test('HTTP proxy forwards bodies, status, cookies and queries without hop headers or caching', { timeout: 10000 }, async t => {
  const { port, backendPort } = await fixture(t, async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    res.writeHead(201, {
      'content-type': 'application/json',
      'x-upstream': 'retained',
      'set-cookie': ['session=private; HttpOnly', 'scope=private'],
      'cache-control': 'public, max-age=3600',
      connection: 'close, x-remove-response',
      'x-remove-response': 'drop',
    });
    res.end(JSON.stringify({ method: req.method, path: req.url, headers: req.headers, body: Buffer.concat(chunks).toString('base64') }));
  });
  for (const method of ['PUT', 'POST']) {
    const body = Buffer.from([0, 255, 65, 13, 10]);
    const result = await request(port, '/api/profile?name=a%20b', {
      method, body, headers: {
        'content-type': 'application/octet-stream', authorization: 'Bearer test', cookie: 'session=private',
        'content-length': body.length, connection: 'close, x-remove-request', 'x-remove-request': 'drop',
      },
    });
    assert.equal(result.status, 201);
    assert.equal(result.headers['x-upstream'], 'retained');
    assert.deepEqual(result.headers['set-cookie'], ['session=private; HttpOnly', 'scope=private']);
    assert.equal(result.headers['cache-control'], 'no-store');
    assert.equal(result.headers['x-remove-response'], undefined);
    const reflected = JSON.parse(result.body);
    assert.equal(reflected.method, method);
    assert.equal(reflected.path, '/api/profile?name=a%20b');
    assert.equal(reflected.body, body.toString('base64'));
    assert.equal(reflected.headers.host, `127.0.0.1:${backendPort}`);
    assert.equal(reflected.headers.authorization, 'Bearer test');
    assert.equal(reflected.headers.cookie, 'session=private');
    assert.equal(reflected.headers['x-remove-request'], undefined);
  }
});

test('media proxy preserves range and binary responses on both private media routes', { timeout: 10000 }, async t => {
  const bytes = Buffer.from([0, 255, 20, 30, 40, 50, 128, 90]);
  const { port } = await fixture(t, (req, res) => {
    assert.equal(req.headers.range, 'bytes=2-5');
    assert.equal(req.headers['if-range'], '"media-version"');
    res.writeHead(206, {
      'content-type': 'video/mp4', 'accept-ranges': 'bytes',
      'content-range': `bytes 2-5/${bytes.length}`, 'content-length': 4,
      etag: '"media-version"', 'cache-control': 'private',
    });
    res.end(bytes.subarray(2, 6));
  });
  for (const path of ['/traces/file/session/clip.mp4', '/board/img/private/image.png']) {
    const result = await request(port, path, { headers: { range: 'bytes=2-5', 'if-range': '"media-version"' } });
    assert.equal(result.status, 206);
    assert.equal(result.headers['content-range'], 'bytes 2-5/8');
    assert.equal(result.headers['accept-ranges'], 'bytes');
    assert.equal(result.headers.etag, '"media-version"');
    assert.equal(result.headers['cache-control'], 'no-store');
    assert.deepEqual(result.body, bytes.subarray(2, 6));
  }
});

test('streaming response arrives before backend completion', { timeout: 10000 }, async t => {
  let finish;
  const { port } = await fixture(t, (_req, res) => {
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write('data: first\n\n');
    finish = () => res.end('data: last\n\n');
  });
  const incoming = await new Promise((resolve, reject) => {
    const outgoing = http.get({ hostname: '127.0.0.1', port, path: '/api/events', agent: false }, resolve);
    outgoing.on('error', reject);
  });
  const [first] = await once(incoming, 'data');
  assert.equal(first.toString(), 'data: first\n\n');
  assert.equal(incoming.complete, false);
  const chunks = [first];
  incoming.on('data', chunk => chunks.push(chunk));
  const ended = once(incoming, 'end');
  finish();
  await ended;
  assert.equal(Buffer.concat(chunks).toString(), 'data: first\n\ndata: last\n\n');
});

test('client abort closes the backend stream and connection errors return 502', { timeout: 10000 }, async t => {
  let backendClosed;
  const closed = new Promise(resolve => { backendClosed = resolve; });
  const { port } = await fixture(t, (req, res) => {
    if (req.url === '/api/fail') return req.socket.destroy();
    res.writeHead(200);
    res.write('started');
    res.on('close', backendClosed);
  });
  assert.equal((await request(port, '/api/fail')).status, 502);
  const incoming = await new Promise((resolve, reject) => {
    const outgoing = http.get({ hostname: '127.0.0.1', port, path: '/api/stream', agent: false }, resolve);
    outgoing.on('error', reject);
  });
  await once(incoming, 'data');
  incoming.destroy();
  await closed;
});

class SocketReader {
  constructor(socket) {
    this.buffer = Buffer.alloc(0);
    this.waiter = null;
    socket.on('data', chunk => {
      this.buffer = Buffer.concat([this.buffer, chunk]);
      this.advance();
    });
    socket.on('error', error => this.fail(error));
    socket.on('close', () => this.fail(new Error('Socket closed before expected bytes')));
  }
  fail(error) {
    this.error = error;
    if (this.waiter) {
      this.waiter.reject(error);
      this.waiter = null;
    }
  }
  advance() {
    if (!this.waiter) return;
    const length = this.waiter.length(this.buffer);
    if (length === null || length > this.buffer.length) return;
    const value = this.buffer.subarray(0, length);
    this.buffer = this.buffer.subarray(length);
    this.waiter.resolve(value);
    this.waiter = null;
  }
  read(length) {
    assert.equal(this.waiter, null, 'reads must be sequential');
    return new Promise((resolve, reject) => {
      this.waiter = { length, resolve, reject };
      this.advance();
      if (this.error && this.waiter) this.fail(this.error);
    });
  }
  bytes(size) { return this.read(() => size); }
  headers() {
    return this.read(buffer => {
      const index = buffer.indexOf('\r\n\r\n');
      return index < 0 ? null : index + 4;
    });
  }
}

function frame(opcode, payload, masked = false) {
  const bytes = Buffer.from(payload);
  assert.ok(bytes.length < 126);
  const header = Buffer.from([0x80 | opcode, (masked ? 0x80 : 0) | bytes.length]);
  if (!masked) return Buffer.concat([header, bytes]);
  const mask = Buffer.from([11, 22, 33, 44]);
  const encoded = Buffer.from(bytes);
  for (let index = 0; index < encoded.length; index++) encoded[index] ^= mask[index % 4];
  return Buffer.concat([header, mask, encoded]);
}

async function websocketClient(t, port, path, firstFrame = Buffer.alloc(0)) {
  const socket = net.connect({ port, host: '127.0.0.1' });
  t.after(() => socket.destroy());
  const reader = new SocketReader(socket);
  await once(socket, 'connect');
  const handshake = [
    `GET ${path} HTTP/1.1`, 'Host: frontend.test', 'Upgrade: websocket', 'Connection: Upgrade',
    'Sec-WebSocket-Version: 13', 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==', '', '',
  ].join('\r\n');
  socket.write(Buffer.concat([Buffer.from(handshake), firstFrame]));
  return { socket, reader };
}

test('WebSocket relays binary order, both handshake head buffers, ping and close', { timeout: 10000 }, async t => {
  const { port, backend } = await fixture(t);
  const received = [];
  const welcome = frame(2, Buffer.from([255, 0, 128]));
  let backendDone;
  const closed = new Promise(resolve => { backendDone = resolve; });
  backend.on('upgrade', (req, socket, head) => {
    const accept = createHash('sha1').update(`${req.headers['sec-websocket-key']}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest('base64');
    const handshake = Buffer.from(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    socket.write(Buffer.concat([handshake, welcome]));
    let buffer = head;
    const consume = () => {
      while (buffer.length >= 6) {
        const length = buffer[1] & 0x7f;
        if (buffer.length < 6 + length) return;
        assert.ok(buffer[1] & 0x80);
        const opcode = buffer[0] & 0xf;
        const bytes = Buffer.from(buffer.subarray(6, 6 + length));
        for (let index = 0; index < bytes.length; index++) bytes[index] ^= buffer[2 + index % 4];
        received.push({ opcode, bytes });
        buffer = buffer.subarray(6 + length);
        const reply = frame(opcode === 9 ? 10 : opcode, bytes);
        if (opcode === 8) socket.end(reply);
        else socket.write(reply);
      }
    };
    socket.on('data', chunk => {
      buffer = Buffer.concat([buffer, chunk]);
      consume();
    });
    socket.on('error', () => {});
    socket.on('close', backendDone);
    consume();
  });
  const first = Buffer.from([0, 255, 3]);
  const second = Buffer.from([128, 127, 0, 10]);
  const { socket, reader } = await websocketClient(t, port, '/ws?session=private', frame(2, first, true));
  assert.match((await reader.headers()).toString(), /^HTTP\/1\.1 101/);
  assert.deepEqual(await reader.bytes(welcome.length), welcome);
  const firstReply = frame(2, first);
  assert.deepEqual(await reader.bytes(firstReply.length), firstReply);
  const secondFrame = frame(2, second, true);
  socket.write(secondFrame.subarray(0, 3));
  socket.write(secondFrame.subarray(3));
  const secondReply = frame(2, second);
  assert.deepEqual(await reader.bytes(secondReply.length), secondReply);
  socket.write(frame(9, 'ping', true));
  const pong = frame(10, 'ping');
  assert.deepEqual(await reader.bytes(pong.length), pong);
  const closePayload = Buffer.from([3, 232]);
  socket.write(frame(8, closePayload, true));
  const closeFrame = frame(8, closePayload);
  assert.deepEqual(await reader.bytes(closeFrame.length), closeFrame);
  await closed;
  assert.deepEqual(received, [
    { opcode: 2, bytes: first }, { opcode: 2, bytes: second },
    { opcode: 9, bytes: Buffer.from('ping') }, { opcode: 8, bytes: closePayload },
  ]);
});

test('WebSocket upgrade rejection retains status and an unchunked body', { timeout: 10000 }, async t => {
  const { port, backend } = await fixture(t);
  backend.on('upgrade', (_req, socket) => {
    socket.end('HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\nConnection: close\r\nCache-Control: public\r\n\r\n6\r\ndenied\r\n0\r\n\r\n');
  });
  const { reader } = await websocketClient(t, port, '/ws');
  const headers = (await reader.headers()).toString();
  assert.match(headers, /^HTTP\/1\.1 403 Forbidden/);
  assert.match(headers, /cache-control: no-store/i);
  assert.doesNotMatch(headers, /transfer-encoding/i);
  assert.equal((await reader.bytes(6)).toString(), 'denied');
});

test('client abort cancels a pending WebSocket handshake at the backend', { timeout: 10000 }, async t => {
  const { port, backend } = await fixture(t);
  let accepted;
  let backendClosed;
  const arrived = new Promise(resolve => { accepted = resolve; });
  const closed = new Promise(resolve => { backendClosed = resolve; });
  backend.on('upgrade', (_req, socket) => {
    socket.on('close', backendClosed);
    socket.on('error', () => {});
    socket.on('end', () => socket.end());
    socket.resume();
    accepted();
  });
  const { socket } = await websocketClient(t, port, '/ws');
  await arrived;
  socket.destroy();
  await closed;
});

test('orderly upstream WebSocket close drains a controlled pending downstream write', { timeout: 10000 }, async t => {
  const { port, backend, backendPort, frontend } = await fixture(t);
  const expected = frame(2, 'queued bytes');
  let downstream;
  let releaseWrite;
  let writePending;
  const pending = new Promise(resolve => { writePending = resolve; });
  frontend.on('connection', socket => {
    downstream = socket;
    const write = socket._write.bind(socket);
    socket._write = (chunk, encoding, callback) => {
      if (chunk[0] === 0x82) {
        releaseWrite = () => write(chunk, encoding, callback);
        writePending();
      } else write(chunk, encoding, callback);
    };
  });
  let upstreamClosed;
  const closed = new Promise(resolve => { upstreamClosed = resolve; });
  // Observe the proxy's actual upstream transport closing without a timing wait.
  const originalRequest = http.request;
  http.request = function (...args) {
    const outgoing = originalRequest.apply(this, args);
    if (args[0] instanceof URL && args[0].port === String(backendPort)) {
      outgoing.on('upgrade', (_response, peer) => peer.on('close', upstreamClosed));
    }
    return outgoing;
  };
  t.after(() => { http.request = originalRequest; });
  backend.on('upgrade', (req, socket) => {
    socket.on('error', () => {});
    socket.resume();
    acceptUpgrade(req, socket);
    socket.end(expected);
  });
  const { reader } = await websocketClient(t, port, '/ws');
  assert.match((await reader.headers()).toString(), /^HTTP\/1\.1 101/);
  await pending;
  await closed;
  assert.ok(downstream.writableLength > 0, 'binary output is still pending after upstream EOF');
  assert.equal(downstream.destroyed, false, 'normal EOF must retain the queued output');
  releaseWrite();
  assert.deepEqual(await reader.bytes(expected.length), expected);
});

test('large WebSocket binary payload reaches a slow client before orderly close', { timeout: 10000 }, async t => {
  const { port, backend } = await fixture(t);
  const payload = Buffer.alloc(16 * 1024 * 1024, 123);
  const header = Buffer.alloc(10);
  header[0] = 0x82;
  header[1] = 127;
  header.writeBigUInt64BE(BigInt(payload.length), 2);
  backend.on('upgrade', (req, socket) => {
    socket.on('error', () => {});
    socket.resume();
    acceptUpgrade(req, socket);
    socket.end(Buffer.concat([header, payload]));
  });
  const { socket, reader } = await websocketClient(t, port, '/ws');
  assert.match((await reader.headers()).toString(), /^HTTP\/1\.1 101/);
  assert.deepEqual(await reader.bytes(header.length), header);
  let received = 0;
  // Consume only one buffered transport chunk at a time; each delay models
  // browser work while the generator continues writing its binary payload.
  while (received < payload.length) {
    const available = await reader.read(buffer => buffer.length ? Math.min(buffer.length, payload.length - received) : null);
    assert.ok(available.every(byte => byte === 123));
    received += available.length;
    socket.pause();
    await delay(2);
    socket.resume();
  }
  assert.equal(received, payload.length);
});

function acceptUpgrade(req, socket) {
  const accept = createHash('sha1').update(`${req.headers['sec-websocket-key']}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest('base64');
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
}

async function startCli(t, backendPort, extraEnv = {}) {
  const child = spawn(process.execPath, [fileURLToPath(new URL('../server.mjs', import.meta.url))], {
    cwd: tmpdir(),
    env: { ...process.env, HOST: '127.0.0.1', PORT: '0', BACKEND_URL: `http://127.0.0.1:${backendPort}`, ...extraEnv },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  t.after(() => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL'); });
  let output = '';
  let errorOutput = '';
  child.stderr.on('data', chunk => { errorOutput += chunk; });
  const exited = once(child, 'exit');
  const port = await new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('exit', code => reject(new Error(`Frontend exited before starting: ${code}: ${errorOutput}`)));
    child.stdout.on('data', chunk => {
      output += chunk;
      const match = output.match(/http:\/\/127\.0\.0\.1:(\d+)/);
      if (match) resolve(Number(match[1]));
    });
  });
  return { child, port, exited };
}

for (const signal of ['SIGTERM', 'SIGINT']) {
  test(`CLI works from another directory and ${signal} closes an active WebSocket`, { timeout: 10000 }, async t => {
    const backend = manageServer(t, http.createServer());
    let backendClosed;
    const closed = new Promise(resolve => { backendClosed = resolve; });
    backend.on('upgrade', (req, socket) => {
      socket.on('error', () => {});
      socket.on('close', backendClosed);
      socket.on('end', () => socket.end());
      socket.resume();
      acceptUpgrade(req, socket);
    });
    const backendPort = await listen(backend);
    const { child, port, exited } = await startCli(t, backendPort);
    const result = await request(port, '/');
    assert.equal(result.status, 200);
    assert.match(result.headers['content-type'], /text\/html/);
    const { reader } = await websocketClient(t, port, '/ws');
    assert.match((await reader.headers()).toString(), /^HTTP\/1\.1 101/);
    child.kill(signal);
    assert.deepEqual(await exited, [0, null]);
    await closed;
  });
}

test('CLI rejects invalid environment values before listening', { timeout: 10000 }, async () => {
  for (const values of [{ PORT: '-1' }, { PORT: '65536' }, { PORT: 'abc' }, { HOST: 'bad host' }, { BACKEND_URL: 'http://localhost/api' }]) {
    const child = spawn(process.execPath, [fileURLToPath(new URL('../server.mjs', import.meta.url))], {
      cwd: tmpdir(), env: { ...process.env, HOST: '127.0.0.1', PORT: '0', BACKEND_URL: 'http://127.0.0.1:8201', ...values },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stderr = '';
    child.stderr.on('data', chunk => { stderr += chunk; });
    const [code, signal] = await once(child, 'close');
    assert.equal(code, 1);
    assert.equal(signal, null);
    assert.match(stderr, /Frontend configuration error/);
  }
});

test('missing upstream returns 502 for HTTP and WebSocket handshakes', { timeout: 10000 }, async t => {
  const reservation = http.createServer();
  const unavailablePort = await listen(reservation);
  await new Promise(resolve => reservation.close(resolve));
  const frontend = manageServer(t, createFrontendServer({ backendUrl: `http://127.0.0.1:${unavailablePort}` }));
  const port = await listen(frontend);
  assert.equal((await request(port, '/api/health')).status, 502);
  const { reader } = await websocketClient(t, port, '/ws');
  assert.match((await reader.headers()).toString(), /^HTTP\/1\.1 502/);
});

test('backend configuration must be an HTTP origin', () => {
  for (const backendUrl of ['ftp://localhost', 'http://user:secret@localhost', 'http://localhost/api', 'http://localhost?x=1', 'http://localhost#hash', 'invalid']) {
    assert.throws(() => createFrontendServer({ backendUrl }));
  }
});

===== FILE: frontend/tests/profile.test.mjs =====
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/profile.js", import.meta.url), "utf8");

function profile(version, name = "Saved name", id = "demo") {
  return {id, version, name, grade: "初二", saved: true,
    exams: [{subject: "数学", name: "期中", date: "2026-10-01", score: 60, full: 100, weak: []}],
    concepts: [], history: []};
}

function editor() {
  const elements = new Map(), requests = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: "", textContent: "", innerHTML: "", checked: false,
      listeners: new Map(),
      addEventListener(event, listener) { this.listeners.set(event, listener); },
    });
    return elements.get(id);
  }
  let poll;
  const document = {hidden: false, getElementById: element};
  const context = vm.createContext({document,
    window: {addEventListener() {}, LiveAgentAPI: {fetchJson(path, opts) {
      // Leave the initial student-list request pending; tests supply a loaded editor.
      if (path === "/api/students") return new Promise(() => {});
      return new Promise(resolve => { requests.push({path, opts, resolve}); });
    }}},
    location: {search: "?student=demo"}, URLSearchParams,
    history: {replaceState() {}}, confirm: () => true,
    setInterval(callback) { poll = callback; },
  });
  function run(code) { return vm.runInContext(code, context); }
  vm.runInContext(source, context);
  run(`server = ${JSON.stringify(profile(1))}; exams = server.exams.map(e => ({...e, weak: ""})); render(); clean();`);
  return {document, element, requests, run, poll: () => poll(),
    editName(value) {
      element("name").value = value;
      element("name").listeners.get("input")();
    },
    editExam(score) {
      const row = {dataset: {i: "0"}, querySelector: () => ({textContent: ""})};
      element("exams").listeners.get("input")({target: {
        dataset: {k: "score"}, value: String(score), closest: () => row,
      }});
    },
  };
}

test("a pending refresh preserves unsaved name and exam drafts", async () => {
  const page = editor(), pending = page.poll();
  page.editName("Unsaved name");
  page.editExam(95);
  page.requests[0].resolve(profile(2, "External name"));
  await pending;
  assert.equal(page.element("name").value, "Unsaved name");
  assert.equal(page.run("exams[0].score"), 95);
  assert.equal(page.run("dirty"), true);
  assert.equal(page.run("server.version"), 1);
  assert.match(page.element("status").textContent, /有未保存的修改/);
});

test("a refresh started before a successful save cannot replace the saved profile", async () => {
  const page = editor(), pending = page.poll();
  page.editName("Just saved name");
  const saving = page.element("save").onclick();
  assert.equal(page.requests[1].opts.method, "PUT");
  assert.equal(JSON.parse(page.requests[1].opts.body).name, "Just saved name");
  page.requests[1].resolve(profile(3, "Just saved name"));
  await saving;
  page.requests[0].resolve(profile(2, "Earlier external name"));
  await pending;
  assert.equal(page.element("name").value, "Just saved name");
  assert.equal(page.run("server.version"), 3);
  assert.equal(page.run("dirty"), false);
});

test("a refresh started before a manual reload cannot replace the loaded profile", async () => {
  const page = editor(), pending = page.poll();
  const reloading = page.element("discard").onclick();
  page.requests[1].resolve(profile(3, "Reloaded name"));
  await reloading;
  page.requests[0].resolve(profile(2, "Earlier external name"));
  await pending;
  assert.equal(page.element("name").value, "Reloaded name");
  assert.equal(page.run("server.version"), 3);
});

test("a pending refresh for the previous student is discarded during student switching", async () => {
  const page = editor(), pending = page.poll();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  assert.equal(page.requests[0].path, "/api/students/demo");
  assert.equal(page.requests[1].path, "/api/students/other");
  // The old refresh returns before the selected student's load finishes.
  page.requests[0].resolve(profile(2, "Previous student"));
  await pending;
  assert.equal(page.element("name").value, "Saved name");
  page.requests[1].resolve(profile(1, "Other student", "other"));
  await switching;
  assert.equal(page.element("name").value, "Other student");
  assert.equal(page.run("server.id"), "other");
});

test("an older overlapping refresh cannot replace a newer refresh result", async () => {
  const page = editor(), first = page.poll(), second = page.poll();
  page.requests[1].resolve(profile(3, "Newer name"));
  await second;
  page.requests[0].resolve(profile(2, "Earlier name"));
  await first;
  assert.equal(page.element("name").value, "Newer name");
  assert.equal(page.run("server.version"), 3);
});

test("an unchanged, clean editor accepts a refresh with a newer version", async () => {
  const page = editor(), pending = page.poll();
  const updated = profile(2, "External name");
  updated.exams[0].score = 80;
  page.requests[0].resolve(updated);
  await pending;
  assert.equal(page.element("name").value, "External name");
  assert.equal(page.run("exams[0].score"), 80);
  assert.equal(page.run("server.version"), 2);
  assert.equal(page.run("dirty"), false);
  assert.match(page.element("status").textContent, /已自动更新/);
});

test("a pending refresh does not update an editor hidden before the response", async () => {
  const page = editor(), pending = page.poll();
  page.document.hidden = true;
  page.requests[0].resolve(profile(2, "External name"));
  await pending;
  assert.equal(page.element("name").value, "Saved name");
  assert.equal(page.run("server.version"), 1);
});

===== FILE: scripts/run_live.sh =====
#!/usr/bin/env bash
# One-command launcher for the live agent (proposal v2.11 A2 system).
#
#   scripts/run_live.sh demo        # CPU only: mock video generator + rule-based responder (no GPUs, no models)
#   scripts/run_live.sh hybrid      # real Qwen3-8B responder + Qwen3-ASR (1 GPU), placeholder video
#   scripts/run_live.sh packed      # TaoMate-H3 (colocated teacher) + all helper models on 4 GPUs
#   scripts/run_live.sh full        # TaoMate-H3 (6 GPUs) + Qwen3-8B / Qwen3-VL-8B / Qwen3-ASR (1 GPU)
#   scripts/run_live.sh omni        # TaoMate-H3 on vLLM-Omni USP4 (4 GPUs) + the helper models (1 GPU)
#                                   OMNI_GPUS=2: USP2 on 2 GPUs instead (FP8 + CUDA-graph teacher, D-036)
#
# Options (env): PORT (frontend, default 8200), HOST (default 127.0.0.1),
#                BACKEND_PORT (default 8201), BACKEND_HOST (default 127.0.0.1), HOURS (default 2h),
#                DIRECTOR (closed_loop | open_loop), ALLOW_UNCALIBRATED (1 = accept `documented` actions; default 1
#                because no capability is calibrated yet — see docs/e1_pilot.md)
# Then open http://HOST:PORT (from a laptop: ssh -L 8200:127.0.0.1:8200 <this host>).
# Stop with Ctrl-C: every process and GPU reservation started here is released.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
mode=${1:-demo}
PORT=${PORT:-8200}; HOST=${HOST:-127.0.0.1}; HOURS=${HOURS:-2h}
BACKEND_PORT=${BACKEND_PORT:-8201}; BACKEND_HOST=${BACKEND_HOST:-127.0.0.1}
case "$mode" in demo|hybrid|packed|full|omni) ;; *) echo "usage: $0 demo|hybrid|packed|full|omni"; exit 2 ;; esac
for tool in node python3 curl; do command -v "$tool" >/dev/null || { echo "$tool not found"; exit 1; }; done
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 18 || (major === 18 && minor >= 2) ? 0 : 1)' || { echo "Node.js 18.2 or newer is required"; exit 1; }
for port in "$PORT" "$BACKEND_PORT"; do
  [[ "$port" =~ ^[0-9]+$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 )) || { echo "invalid port: $port"; exit 2; }
done
PORT=$((10#$PORT)); BACKEND_PORT=$((10#$BACKEND_PORT))
[ "$PORT" != "$BACKEND_PORT" ] || { echo "PORT and BACKEND_PORT must be different"; exit 2; }
if [ "$mode" = "omni" ]; then READY_TIMEOUT=${READY_TIMEOUT:-1800}; else READY_TIMEOUT=${READY_TIMEOUT:-900}; fi
[[ "$READY_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || { echo "READY_TIMEOUT must be a positive number of seconds"; exit 2; }
DIRECTOR=${DIRECTOR:-closed_loop}; ALLOW_UNCALIBRATED=${ALLOW_UNCALIBRATED:-1}
PERSONA=${PERSONA:-hanfu}  # configs/persona_<name>: hanfu (reading host) | teacher (classroom Q&A)
# Responder LLM: local Qwen3-8B by default; a hosted OpenAI-compatible model with LLM_URL + LLM_MODEL, its key read
# from LLM_API_KEY_FILE (default .cache/llm_api_key, git-ignored) into the backend environment
LLM_URL=${LLM_URL:-http://127.0.0.1:8101/v1}; LLM_MODEL=${LLM_MODEL:-qwen3-8b}
LLM_API_KEY_FILE=${LLM_API_KEY_FILE:-.cache/llm_api_key}
if [ -z "${LLM_API_KEY:-}" ] && [ -s "$LLM_API_KEY_FILE" ]; then LLM_API_KEY=$(tr -d '[:space:]' < "$LLM_API_KEY_FILE"); fi
export LLM_API_KEY=${LLM_API_KEY:-}
# no local LLM when the responder is hosted (frees the helper card, e.g. for the board image model)
[ "$LLM_URL" != "http://127.0.0.1:8101/v1" ] && export SKIP_LLM=1
# board images (Qwen-Image on the helper card): default on for the teacher persona
# HELPERS=0 (omni mode): no helper GPU; the VLM checks and speech recognition use the hosted API with the LLM key
# (qwen3.8-flash sees images; qwen-audio-3.0-realtime-plus transcribes), and board illustrations are off
HELPERS=${HELPERS:-1}
HOSTED_VLM_URL=${HOSTED_VLM_URL:-https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1}
HOSTED_ASR_URL=${HOSTED_ASR_URL:-wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime}
IMAGES=${IMAGES:-$([ "$PERSONA" = "teacher" ] && [ "$HELPERS" = "1" ] && echo 1 || echo 0)}; export IMAGE=$IMAGES
mkdir -p .cache/logs .cache/sessions
extra=()
[ -d "configs/persona_$PERSONA" ] || { echo "unknown PERSONA=$PERSONA (no configs/persona_$PERSONA)"; exit 2; }
extra+=(--config "configs/persona_$PERSONA")
[ "$mode" != "demo" ] && extra+=(--llm-url "$LLM_URL" --llm-model "$LLM_MODEL")
[ "$IMAGES" = "1" ] && [ "$mode" != "demo" ] && extra+=(--image-url "http://127.0.0.1:8104")
[ "$ALLOW_UNCALIBRATED" = "1" ] && extra+=(--dev-allow-uncalibrated)
[ "${RECORD:-1}" = "1" ] && extra+=(--record)  # traces: event log + presented video per session (/traces)
pids=()
set -m  # job control: each background child gets its own process group (cleanup kills whole trees)
RUN_ID=$(date +%Y%m%dT%H%M%S)-$$  # per-invocation logs: a run never parses (or releases) another run's GPUs
SERVER_LOG=.cache/logs/run_live_server.$RUN_ID.out
FRONTEND_LOG=.cache/logs/run_live_frontend.$RUN_ID.out
HELPER_LOG=.cache/logs/serve_models.$RUN_ID.out
OMNI_LOG=.cache/logs/vllm_omni.$RUN_ID.out
reserved_ids() {  # GPU ids that *our* gpu run calls reported reserving (from their own output)
  grep -ho "Reserved [0-9]* GPU(s): \[[0-9 ]*\]" "$@" 2>/dev/null | sed 's/.*\[\(.*\)\]/\1/' | tr ' ' '\n' | grep -E '^[0-9]+$' || true
}
still_ours() {  # a reused card must still carry this invocation's reservation note
  local ours
  ours=$(gpu status --no-schedule 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk -F'│' -v marker="live-agent $RUN_ID " '
    NR==1 { for (i=1;i<=NF;i++) { h=$i; gsub(/ /,"",h); if (h=="NOTE") c=i } next }
    c { note=$c; sub(/^ */,"",note); if (index(note,marker)==1) { g=$1; gsub(/ /,"",g); print g } }')
  grep -Fxf <(echo "$ours") || true
}
cleanup() {
  trap - EXIT INT TERM
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -INT -- "-$p" 2>/dev/null || kill -INT "$p" 2>/dev/null; } || true; done
  for _ in $(seq 1 60); do  # give gpu run up to 60 s to stop its command gracefully
    alive=0; for p in "${pids[@]:-}"; do [ -n "$p" ] && kill -0 -- "-$p" 2>/dev/null && alive=1; done
    [ $alive = 0 ] && break; sleep 1
  done
  for p in "${pids[@]:-}"; do [ -n "$p" ] && { kill -9 -- "-$p" 2>/dev/null || kill -9 "$p" 2>/dev/null; } || true; done
  # canhazgpu can keep a reservation after its supervisor is interrupted: release exactly ours. A card can be
  # lost (idle release) and re-reserved by another job: release only cards still marked with this RUN_ID
  if [ "$mode" != "demo" ] && command -v gpu >/dev/null; then
    ids=$(reserved_ids "$SERVER_LOG" "$HELPER_LOG" "$OMNI_LOG" | sort -u | still_ours | paste -sd, -)
    if [ -n "$ids" ]; then gpu release --gpu-ids "$ids" >/dev/null 2>&1 && echo "[run_live] released GPUs $ids"; fi
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

port_free() {
  python3 - "$1" "${2:-127.0.0.1}" <<'PY'
import socket
import sys
try:
    family, kind, proto, _, address = socket.getaddrinfo(sys.argv[2], int(sys.argv[1]), type=socket.SOCK_STREAM)[0]
    with socket.socket(family, kind, proto) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(address)
except (OSError, ValueError):
    sys.exit(1)
PY
}
model_port_free() { [ "$1" != "$BACKEND_PORT" ] && [ "$1" != "$PORT" ] && port_free "$1"; }
port_free "$PORT" "$HOST" || { echo "frontend port $HOST:$PORT is unavailable; set PORT=..."; exit 1; }
port_free "$BACKEND_PORT" "$BACKEND_HOST" || { echo "backend port $BACKEND_HOST:$BACKEND_PORT is unavailable; set BACKEND_PORT=..."; exit 1; }
connect_host() {
  case "$1" in 0.0.0.0) echo 127.0.0.1 ;; ::) echo '[::1]' ;; *:*) echo "[$1]" ;; *) echo "$1" ;; esac
}
BACKEND_URL="http://$(connect_host "$BACKEND_HOST"):$BACKEND_PORT"
FRONTEND_URL="http://$(connect_host "$HOST"):$PORT"
processes_alive() {
  for p in "${pids[@]}"; do
    kill -0 "$p" 2>/dev/null || { echo "[run_live] a process exited; see $FRONTEND_LOG and $SERVER_LOG"; return 1; }
  done
}
env -u LLM_API_KEY HOST="$HOST" PORT="$PORT" BACKEND_URL="$BACKEND_URL" node frontend/server.mjs > "$FRONTEND_LOG" 2>&1 &
pids+=($!)
echo "[run_live] frontend log: $FRONTEND_LOG; backend: $BACKEND_URL"

case "$mode" in
  demo)
    echo "[run_live] demo: mock generator, rule-based responder, simulated judge, no ASR (CPU only)"
    python3 -m live_agent.backend.app --generator mock --llm-url scripted --vlm-url mock --asr-url "" \
      --director-mode "$DIRECTOR" --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    ;;
  packed)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    helper_ports=(8102 8103); [ "${SKIP_LLM:-0}" != "1" ] && helper_ports+=(8101); [ "$IMAGES" = "1" ] && helper_ports+=(8104)
    for p in "${helper_ports[@]}"; do model_port_free "$p" || { echo "helper port $p unavailable or overlaps frontend/backend"; exit 1; }; done
    : > "$SERVER_LOG"; : > "$HELPER_LOG"
    echo "[run_live] packed: TaoMate-H3 + helper models together on 4 GPUs (start-up ~6-8 min) ..."
    sel=(--gpus 4); [ -n "${GPU_IDS:-}" ] && sel=(--gpu-ids "$GPU_IDS")  # pin cards (e.g. avoid shared ones)
    gpu run "${sel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID packed" -- \
      env HELPER_LOG="$HELPER_LOG" scripts/packed_stack.sh --director-mode "$DIRECTOR" --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" \
      > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    echo "[run_live] server log: $SERVER_LOG"
    ;;
  hybrid|full)
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    helper_ports=(8102 8103); [ "${SKIP_LLM:-0}" != "1" ] && helper_ports+=(8101); [ "$IMAGES" = "1" ] && helper_ports+=(8104)
    for p in "${helper_ports[@]}"; do model_port_free "$p" || { echo "helper port $p unavailable or overlaps frontend/backend"; exit 1; }; done
    echo "[run_live] $mode: starting helper models on 1 GPU (log $HELPER_LOG) ..."
    : > "$HELPER_LOG"; : > "$SERVER_LOG"
    hsel=(--gpus 1); [ -n "${HELPER_GPU:-}" ] && hsel=(--gpu-ids "$HELPER_GPU")  # pin (avoid shared cards)
    gpu run "${hsel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID helpers" -- \
      scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
    pids+=($!)
    t0=$SECONDS
    until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null; do
      processes_alive || { tail -20 "$HELPER_LOG"; exit 1; }
      if grep -q "reservation lost\|releasing GPU reservation" "$HELPER_LOG"; then
        echo "helper GPU reservation was lost:"; tail -5 "$HELPER_LOG"; exit 1
      fi
      [ $((SECONDS - t0)) -gt 1200 ] && { echo "helper models not ready after 20 min:"; tail -20 "$HELPER_LOG"; exit 1; }
      sleep 5
    done
    if [ "$mode" = "hybrid" ]; then
      # real Qwen3 responder / ASR, placeholder video (no TaoMate GPUs needed); the placeholder always
      # shows the locked action, so the simulated judge agrees with it
      echo "[run_live] helper models ready; starting hybrid server (real LLM + ASR, placeholder video) ..."
      python3 -m live_agent.backend.app --generator mock --vlm-url mock --director-mode "$DIRECTOR" \
        --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    else
      echo "[run_live] helper models ready; starting TaoMate-H3 server on 6 GPUs (start-up ~2-3 min) ..."
      ssel=(--gpus 6); [ -n "${GPU_IDS:-}" ] && ssel=(--gpu-ids "$GPU_IDS")
      gpu run "${ssel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID backend" -- \
        python3 -m live_agent.backend.app --generator taomate_h3 --director-mode "$DIRECTOR" \
          --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" > "$SERVER_LOG" 2>&1 &
    fi
    echo "[run_live] server log: $SERVER_LOG"
    pids+=($!)
    ;;
  omni)
    # TaoMate-H3 served by vLLM-Omni (pure Ulysses SP on 4 GPUs, D-026/D-027) with the just-in-time prompt
    # hold (configs/vllm_omni/taomate_h3_usp4_jit.yaml, D-028); the web server itself needs no GPU
    command -v gpu >/dev/null || { echo "canhazgpu ('gpu') not found"; exit 1; }
    OMNI_DIR=${OMNI_DIR:-/data/zhoutaichang/worldmodel/vllm-omni-taomate}
    OMNI_PORT=${OMNI_PORT:-8191}
    OMNI_MODEL=${OMNI_MODEL:-/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe/FL2VA}
    [ -x "$OMNI_DIR/.venv/bin/vllm" ] || { echo "vLLM-Omni venv not found: $OMNI_DIR/.venv"; exit 1; }
    ports=("$OMNI_PORT")
    if [ "$HELPERS" = "1" ]; then
      ports+=(8102 8103); [ "${SKIP_LLM:-0}" != "1" ] && ports+=(8101); [ "$IMAGES" = "1" ] && ports+=(8104)
    fi
    for p in "${ports[@]}"; do model_port_free "$p" || { echo "model port $p unavailable or overlaps frontend/backend"; exit 1; }; done
    : > "$HELPER_LOG"; : > "$OMNI_LOG"; : > "$SERVER_LOG"
    OMNI_GPUS=${OMNI_GPUS:-4}  # 4: USP4 (default); 2: USP2 with FP8 linears and CUDA-graph teacher (D-036)
    case "$OMNI_GPUS" in 2|4) ;; *) echo "OMNI_GPUS must be 2 or 4"; exit 1;; esac
    echo "[run_live] omni: helper models $([ "$HELPERS" = "1" ] && echo "on 1 GPU (log $HELPER_LOG)" || echo "hosted (API)"), vLLM-Omni TaoMate-H3 on $OMNI_GPUS GPUs (log $OMNI_LOG) ..."
    if [ "$HELPERS" = "1" ]; then
      hsel=(--gpus 1); [ -n "${HELPER_GPU:-}" ] && hsel=(--gpu-ids "$HELPER_GPU")
      gpu run "${hsel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID helpers" -- \
        scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
      pids+=($!)
    else
      echo "ALL_READY (hosted VLM and ASR)" > "$HELPER_LOG"
      extra+=(--vlm-url "$HOSTED_VLM_URL" --vlm-model "$LLM_MODEL" --asr-url "$HOSTED_ASR_URL"
              --asr-model qwen-audio-3.0-realtime-plus)
    fi
    osel=(--gpus "$OMNI_GPUS"); [ -n "${GPU_IDS:-}" ] && osel=(--gpu-ids "$GPU_IDS")
    repo=$PWD
    gpu run "${osel[@]}" --timeout "$HOURS" --note "live-agent $RUN_ID omni USP$OMNI_GPUS" -- \
      env -C "$OMNI_DIR" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/vllm serve "$OMNI_MODEL" --omni \
        --trust-remote-code --deploy-config "$repo/configs/vllm_omni/taomate_h3_usp${OMNI_GPUS}_jit.yaml" \
        --init-timeout 2400 --stage-init-timeout 2400 \
        --lora-path "$repo/.cache/models/TaoMate-H3" --host 127.0.0.1 --port "$OMNI_PORT" > "$OMNI_LOG" 2>&1 &
    pids+=($!)
    t0=$SECONDS
    until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null && curl --noproxy '*' --connect-timeout 1 --max-time 2 -sf "http://127.0.0.1:$OMNI_PORT/health" >/dev/null 2>&1; do
      processes_alive || { tail -5 "$HELPER_LOG" "$OMNI_LOG"; exit 1; }
      if grep -q "reservation lost\|releasing GPU reservation" "$HELPER_LOG" "$OMNI_LOG"; then
        echo "a GPU reservation was lost during start-up:"; tail -3 "$HELPER_LOG" "$OMNI_LOG"; exit 1
      fi
      [ $((SECONDS - t0)) -gt "${READY_TIMEOUT:-1800}" ] && { echo "model servers not ready in time:"; tail -5 "$HELPER_LOG" "$OMNI_LOG"; exit 1; }
      sleep 5
    done
    echo "[run_live] model servers ready ($((SECONDS - t0)) s); starting the backend ..."
    python3 -m live_agent.backend.app --generator vllm_omni_h3 --omni-url "ws://127.0.0.1:$OMNI_PORT/v1/realtime/video" \
      --omni-model "$OMNI_MODEL" --director-mode "$DIRECTOR" --host "$BACKEND_HOST" --port "$BACKEND_PORT" "${extra[@]}" \
      > "$SERVER_LOG" 2>&1 &
    pids+=($!)
    echo "[run_live] server log: $SERVER_LOG"
    ;;
  *) echo "usage: $0 demo|hybrid|packed|full|omni"; exit 2 ;;
esac

ready=0
t0=$SECONDS
while [ $((SECONDS - t0)) -lt "$READY_TIMEOUT" ]; do  # raise it when gpu run may queue for GPUs
  processes_alive || exit 1
  if curl --noproxy '*' --connect-timeout 1 --max-time 2 -sf "$FRONTEND_URL/api/health" >/dev/null 2>&1; then
    echo "[run_live] ready: $FRONTEND_URL   (backend $BACKEND_URL; Ctrl-C to stop)"
    ready=1
    break
  fi
  if [ "$mode" != "demo" ] && grep -q "reservation lost" "$SERVER_LOG" "$HELPER_LOG" "$OMNI_LOG" 2>/dev/null; then
    echo "[run_live] a GPU reservation was lost during start-up"; exit 1
  fi
  sleep 1
done
[ "$ready" = "1" ] || { echo "[run_live] frontend/backend not ready after $READY_TIMEOUT s; see $FRONTEND_LOG and $SERVER_LOG"; exit 1; }
status=0
wait -n "${pids[@]}" || status=$?
echo "[run_live] a process exited; stopping the stack"
[ "$status" -ne 0 ] || status=1
exit "$status"
