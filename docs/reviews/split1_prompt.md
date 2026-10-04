Act as the independent GPT-6 Sol reviewer of a contributor refactor in live-agent. Work read-only; all evidence is inlined. The owner requested inspection of the existing agent and separation into independent frontend and backend. Evaluate the concrete engineering split rather than revisiting the research proposal. Check boundaries, runnable launch commands and every launch mode by code inspection, runtime imports/paths, profile version semantics and private-data caching, HTTP/WebSocket proxy byte ordering/backpressure/errors/abort/shutdown, trace/media routing, and validation scope. Challenge unsupported assumptions or actual regressions, and avoid demanding unrelated architecture or generator changes.

Implementation: standalone vanilla frontend served by a dependency-free Node server (frontend/public, frontend/server.mjs); API-only FastAPI backend in live_agent/backend; former live_agent.server.app re-exports compatibility entrypoints; same-origin frontend proxy; launcher supervises independent ports. The backend transport and session loop were mechanically moved (AST match checked) apart from a restored now import. Frontend markup/CSS/classic playback JS were mechanically extracted, with only the WebSocket URL construction/profile fetch replaced by the shared helper; model behavior is unchanged. The browser playback smoke checks target the frontend proxy on the mock stack, not GPU or physical lip sync.

Return actionable findings as a numbered list, mark each blocking, major, or minor, and give inspected evidence plus the smallest check that settles it. If there are no actionable findings, state that clearly and retain any material unverified limits. Do not equate passing tests or contributor agreement with verification. Do not try shell tools (host sandbox cannot start). No edits.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

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
    peer.on('close', () => socket.destroy());
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
    "node": ">=18"
  }
}

===== FILE: frontend/public/assets/api.js =====
// Browser requests use the frontend origin; its server proxies backend routes.
(() => {
  function backendUrl(path) {
    const url = new URL(path, window.location.origin);
    if (url.origin !== window.location.origin) {
      throw new Error("Backend requests must use the frontend origin");
    }
    return url;
  }

  function websocketUrl(path = "/ws") {
    const url = backendUrl(path);
    url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return url.href;
  }

  async function fetchJson(path, opts = {}) {
    const headers = new Headers(opts.headers);
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(backendUrl(path).href, {...opts, headers});
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const error = new Error(body?.detail || response.statusText || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  window.LiveAgentAPI = Object.freeze({websocketUrl, fetchJson});
})();

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
  try {
    const now = await api(`/api/students/${encodeURIComponent(sid)}`);
    if (now.version !== server.version) { server = now; exams = now.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
      render(); setStatus(`已自动更新（课堂中有新的练习结果）· 版本 ${now.version}`, "ok"); }
  } catch (_) { /* offline for a moment: try again next time */ }
}, 5000);

loadList().catch(e => setStatus("载入失败：" + e.message, "err"));

===== FILE: frontend/public/assets/traces.js =====
function traceLink(url, label) {
  const link = document.createElement("a");
  link.href = url;
  link.textContent = label;
  return link;
}

function traceUpdateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

async function loadTraces() {
  const {sessions} = await window.LiveAgentAPI.fetchJson("/api/traces");
  const body = document.getElementById("sessions");
  for (const session of sessions) {
    const row = document.createElement("tr");
    const updated = row.insertCell();
    updated.textContent = traceUpdateTime(session.updated_at);
    updated.title = session.updated_at;
    row.insertCell().textContent = session.id;
    const trace = row.insertCell();
    trace.append(traceLink(session.trace_url, "trace.jsonl"), ` (${Math.floor(session.size_bytes / 1024)} KB)`);
    const videos = row.insertCell();
    if (session.videos.length) {
      session.videos.forEach((video, i) => {
        if (i) videos.append(" · ");
        videos.append(traceLink(video.url, video.label));
      });
    } else {
      const empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = "no video";
      videos.append(empty);
    }
    body.append(row);
  }
  const status = document.getElementById("status");
  status.textContent = sessions.length ? "" : "No recorded sessions.";
  status.hidden = sessions.length > 0;
}

loadTraces().catch((error) => {
  const status = document.getElementById("status");
  status.textContent = `Could not load sessions: ${error.message}`;
  status.className = "error";
});

===== FILE: frontend/tests/server.test.mjs =====
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import http from 'node:http';
import net from 'node:net';
import { once } from 'node:events';
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

===== FILE: frontend/tests/api.test.mjs =====
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/api.js", import.meta.url), "utf8");

function browserAPI(origin, fetch = () => { throw new Error("unexpected request"); }) {
  const location = new URL(origin);
  const context = vm.createContext({window: {location}, URL, Headers, fetch});
  vm.runInContext(source, context);
  return context.window.LiveAgentAPI;
}

test("WebSockets keep the frontend host, port, path and query on HTTP or HTTPS", () => {
  const http = browserAPI("http://localhost:8200");
  assert.equal(http.websocketUrl(), "ws://localhost:8200/ws");
  assert.equal(http.websocketUrl("/ws?session=demo"), "ws://localhost:8200/ws?session=demo");
  assert.equal(browserAPI("https://live.example.test").websocketUrl(), "wss://live.example.test/ws");
});

test("backend requests cannot leave the frontend origin", async () => {
  const api = browserAPI("http://localhost:8200");
  assert.throws(() => api.websocketUrl("//example.test/ws"), /frontend origin/);
  await assert.rejects(api.fetchJson("https://example.test/api/students"), /frontend origin/);
});

test("JSON requests forward method, body and caller headers without mutating them", async () => {
  const result = {version: 2};
  let request;
  const api = browserAPI("http://localhost:8200", async (url, options) => {
    request = {url, options};
    return {ok: true, json: async () => result};
  });
  const headers = {"X-Test": "keep"};
  const options = {method: "PUT", body: '{"version":1}', headers};
  assert.equal(await api.fetchJson("/api/students/demo?full=true", options), result);
  assert.equal(request.url, "http://localhost:8200/api/students/demo?full=true");
  assert.equal(request.options.method, "PUT");
  assert.equal(request.options.body, options.body);
  assert.equal(request.options.headers.get("Content-Type"), "application/json");
  assert.equal(request.options.headers.get("X-Test"), "keep");
  assert.deepEqual(headers, {"X-Test": "keep"});
});

test("caller Content-Type remains intact", async () => {
  const api = browserAPI("http://localhost:8200", async (_url, options) => {
    assert.equal(options.headers.get("Content-Type"), "application/merge-patch+json");
    return {ok: true, json: async () => ({})};
  });
  await api.fetchJson("/api/students/demo", {headers: {"content-type": "application/merge-patch+json"}});
});

test("profile conflict responses retain their status and backend detail", async () => {
  const api = browserAPI("http://localhost:8200", async () => ({
    ok: false, status: 409, statusText: "Conflict", json: async () => ({detail: "profile changed"}),
  }));
  await assert.rejects(api.fetchJson("/api/students/demo"), (error) => {
    assert.equal(error.status, 409);
    assert.equal(error.message, "profile changed");
    return true;
  });
});

test("proxy failures with non-JSON bodies report HTTP status", async () => {
  const api = browserAPI("http://localhost:8200", async () => ({
    ok: false, status: 502, statusText: "Bad Gateway", json: async () => { throw new SyntaxError("HTML response"); },
  }));
  await assert.rejects(api.fetchJson("/api/traces"), (error) => {
    assert.equal(error.status, 502);
    assert.equal(error.message, "Bad Gateway");
    return true;
  });
});

===== FILE: live_agent/backend/app.py =====
"""API-only FastAPI backend: scoped resources and one session per WebSocket.

The standalone frontend owns HTML, CSS, JavaScript and its same-origin proxy.
HTTP routes and the existing /ws media protocol are documented in
``docs/frontend_backend.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import SessionView
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import Utterance, new_id, now
from live_agent.backend.config import BOARD_IMAGES, CURRICULUM, STUDENT_SEEDS, parse_args
from live_agent.backend.resources import register_resources
from live_agent.backend.runtime import llm_api_key, make_generator, make_memory
from live_agent.backend.transport import WSTransport, encode_h264, encode_jpeg, panel_event, to_pcm16

log = logging.getLogger("live_agent.backend")


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI(title="Live Agent Backend", version="1.0")

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/", "/traces/file/", "/board/img/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()
    from live_agent.student import ProfileStore

    # one shared copy per student for sessions and the profile page; only ids on the allow-list are reachable
    profiles = ProfileStore(Path(args.student_store), STUDENT_SEEDS,
                            [x for x in (args.students or args.student).split(",")
                             if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", x)])
    app.state.profiles = profiles
    from live_agent.curriculum import Curriculum

    curriculum = Curriculum.load(CURRICULUM)  # course knowledge base (empty if not present)
    app.state.curriculum = curriculum

    @app.get("/api/curriculum")
    async def curriculum_summary() -> dict:
        return curriculum.summary()

    @app.on_event("startup")
    async def _startup() -> None:
        if args.record:  # recordings left unfinished by a killed session
            from live_agent.sim import salvage_recordings

            fixed = await asyncio.to_thread(salvage_recordings, args.log_dir)
            if fixed:
                log.info("finalised %d interrupted recording(s): %s", len(fixed), ", ".join(fixed))
        from live_agent.llm import OpenAICompatLLM, make_chat_llm

        if args.llm_url != "scripted":
            await make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args)).warmup()  # SDK lazy imports
        # Heavy generators are started once and shared (reset per session); the mock is per session.
        if args.generator != "mock":
            gen = make_generator(args)
            try:
                await gen.start()
            except BaseException:
                await gen.close()  # workers / listener of a partial start must not linger
                raise
            app.state.shared_gen = gen

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.shared_gen is not None:
            await app.state.shared_gen.close()

    register_resources(app, args, profiles)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = "public" if hello.get("mode") == "public" else "private"
        session_id = new_id("sess")
        record_path = Path(args.log_dir) / f"{session_id}.mp4" if args.record else None
        if record_path is not None:
            record_path.parent.mkdir(parents=True, exist_ok=True)
        codec = "h264" if args.video_codec == "auto" and "h264" in (hello.get("video_codecs") or []) else "jpeg"
        transport = WSTransport(ws, record_path, video_codec=codec)
        shared = app.state.shared_gen is not None
        if shared:
            if app.state.session_lock.locked():
                await ws.send_text(json.dumps({"type": "error", "error": "generator busy (one live session at a time)"}))
                await ws.close()
                return
            await app.state.session_lock.acquire()
        orch = None
        inputs: asyncio.Queue = asyncio.Queue()
        worker = None
        try:
            from live_agent.llm import OpenAICompatLLM, make_chat_llm

            manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
            if args.llm_url == "scripted":  # CPU-only demo: rule-based responder, no model server
                from live_agent.llm import RuleResponder

                llm = RuleResponder(manifest)
            else:
                llm = make_chat_llm(args.llm_url, args.llm_model, api_key=llm_api_key(args))
            if args.dev_allow_uncalibrated:
                manifest.min_status = Status.DOCUMENTED
            ledger = StateLedger.from_config(cfg_dir / "canon.json")
            intents = canon.get("intents", {})  # persona filler gestures (idle / listen / while speaking)
            director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                                persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode),
                                idle_intent=intents.get("idle", "idle_read"),
                                listen_intent=intents.get("listen", "listen"),
                                speak_intent=intents.get("speak"),
                                responder_style=canon.get("responder_style", ""),
                                responder_examples=canon.get("responder_examples"))
            director.present_intent = intents.get("present")  # gesture toward the page's board
            generator = SessionView(app.state.shared_gen) if shared else make_generator(args)
            sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
                                                  lambda_prior_s=args.lambda_prior))
            judge = speech = None
            if args.vlm_url == "mock":  # demo only: simulated verdicts (p=0.8), never a measurement
                from live_agent.qc.judge import MockJudge

                # the placeholder video always "performs" the locked action, so by default the simulated
                # judge agrees (p=1); a lower --mock-judge-p demonstrates the repair loop
                judge = MockJudge(p_default=args.mock_judge_p)
            elif args.vlm_url:
                from live_agent.qc.judge import VLMJudge

                hosted = not args.vlm_url.startswith(("http://127.", "http://localhost"))
                judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model,
                                                 api_key=llm_api_key(args) if hosted else "EMPTY", timeout_s=60.0),
                                 k=8, contrast=True)
            asr = None
            if args.asr_url.startswith("wss://"):  # hosted realtime audio model: user speech only (no per-request
                from live_agent.asr import HostedRealtimeASR  # speech QC: an API call per 5 s line, ~6 s each)

                asr = HostedRealtimeASR(args.asr_url, args.asr_model, llm_api_key(args))
            elif args.asr_url:
                from live_agent.asr import OpenAIASR
                from live_agent.qc.judge import SpeechCheck

                asr = OpenAIASR(args.asr_url, args.asr_model)
                speech = SpeechCheck(asr.transcribe_sync)
            from live_agent.qc.judge import ForwardCorrector

            log_dir = Path(args.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=ForwardCorrector(None if args.llm_url == "scripted" else llm),
                                speech_check=speech, memory=make_memory(args, hello, session_id, mode),
                                log=EventLog(log_dir / f"{session_id}.jsonl"),
                                cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                       correction_mode=CorrectionMode(args.correction_mode),
                                                       # the demo's vLLM-Omni configs hold for every prompt
                                                       generator_holds=args.generator == "vllm_omni_h3",
                                                       lesson_self_check=args.lesson_self_check))
            transport.orchestrator = orch
            if args.image_url:
                from live_agent.board_images import ImageMaker

                orch.image_maker = ImageMaker(args.image_url, BOARD_IMAGES)
            orch.figure_dir = BOARD_IMAGES  # exact plots need no model
            orch.answer_boards = bool(canon.get("board"))
            orch.curriculum = curriculum  # a persona with a board writes one for every knowledge answer
            # the page may pick a profile only from the server's allow-list: the demo has one shared access token and no
            # per-student accounts, so the operator decides which profiles this deployment exposes
            allowed = [x for x in (args.students or args.student).split(",") if x]
            student_id = str(hello.get("student") or args.student)
            if student_id not in allowed:
                student_id = args.student
            if mode == "private" and student_id in allowed:
                # personal data: only a private session reads or updates the saved profile (the shared copy)
                orch.student = profiles.get(student_id)
                orch.profile_store = profiles
                if orch.student is not None:
                    profiles.subscribe(student_id, orch.on_profile_edited)
            if getattr(judge, "vlm", None) is not None:  # the camera focus check uses the judge's VLM (opt-in)
                from live_agent.attention import AttentionMonitor

                orch.attention = AttentionMonitor(judge.vlm)
            if args.record:  # everything the generator produced, incl. chunks dropped by barge-ins
                from live_agent.sim import Recorder

                parts = iter(range(1, 10**6))

                def gen_rec():
                    n = next(parts)
                    return Recorder(Path(args.log_dir) / (f"{session_id}.generated.mp4" if n == 1
                                                          else f"{session_id}.generated-part{n}.mp4"))

                orch.gen_recorder, orch.gen_recorder_factory = gen_rec(), gen_rec
            # live panel: timeline events + a 2 Hz state snapshot to the page (display only)
            panel_q: asyncio.Queue = asyncio.Queue(maxsize=500)
            t_session = now()

            def on_event(ev) -> None:
                msg = panel_event(ev, t_session)
                if msg is not None and not panel_q.full():
                    panel_q.put_nowait(msg)

            orch.log.listeners.append(on_event)

            async def panel_sender() -> None:
                while True:
                    try:
                        msg = await asyncio.wait_for(panel_q.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        msg = {"type": "state", **orch.snapshot()}
                    await transport.send_json(msg)

            panel_task = asyncio.create_task(panel_sender())
            await orch.start()
            await ws.send_text(json.dumps({"type": "status", "session": session_id, "mode": mode,
                                           "generator": generator.info.name, "director": args.director_mode,
                                           "judge": "mock" if args.vlm_url == "mock" else ("vlm" if args.vlm_url else "none"),
                                           "responder": "rules" if args.llm_url == "scripted" else args.llm_model,
                                           "asr": bool(args.asr_url), "persona": canon.get("display_name", ""),
                                           "examples": canon.get("examples", []),
                                           "attention": orch.attention is not None,
                                           "board": bool(canon.get("board")),
                                           "student": orch.student.view() if orch.student is not None else None},
                                          ensure_ascii=False))

            async def handle_inputs() -> None:
                """Utterances are processed in order, off the receive loop, so presentation acks
                and barge-in keep being read (and timestamped) while ASR / the LLM run."""
                while True:
                    kind, payload, t_end, epoch = await inputs.get()  # epoch stamped at receipt
                    try:
                        if kind == "audio":
                            from live_agent.asr import decode_audio_bytes

                            audio = decode_audio_bytes(payload, 16000)
                            text = await asr.transcribe(audio, 16000)
                            await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                        else:
                            text = payload
                        if text:
                            # t_end = when the user stopped speaking / sent (client clock, mapped), so
                            # ASR and queueing delay count toward the deadlines (proposal §7)
                            await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, t_end,
                                                                   session_id=session_id, scope=mode),
                                                         epoch=epoch)
                    except Exception:  # noqa: BLE001
                        log.exception("input handling failed")

            worker = asyncio.create_task(handle_inputs())
            audio_end = now()
            done = asyncio.create_task(orch.wait_done())
            while True:
                recv = asyncio.create_task(ws.receive())
                await asyncio.wait({recv, done}, return_when=asyncio.FIRST_COMPLETED)
                if not recv.done():  # the orchestrator stopped (fatal error or bounded run)
                    recv.cancel()
                    err = f"{type(orch.error).__name__}: {orch.error}" if orch.error else "session ended"
                    try:
                        await ws.send_text(json.dumps({"type": "error", "error": err}))
                        await ws.close()
                    except Exception:  # noqa: BLE001
                        pass
                    break
                msg = recv.result()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    if asr is not None:
                        inputs.put_nowait(("audio", msg["bytes"], audio_end, orch.input_epoch))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end", "chunk_received"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    await orch.on_speech_start()
                elif t == "text" and data.get("text", "").strip():
                    # a typed instruction interrupts like speech does (before its LLM work is queued)
                    await orch.on_speech_start()
                    inputs.put_nowait(("text", data["text"].strip(), transport._to_server(data), orch.input_epoch))
                elif t == "audio_end":  # precedes the recorded audio bytes
                    audio_end = transport._to_server(data)
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
                elif t == "clock":
                    transport.on_clock(data)
                elif t == "camera" and isinstance(data.get("jpeg"), str) and len(data["jpeg"]) <= 400_000:
                    try:  # opt-in attention check: analysed in memory, never stored or recorded
                        orch.on_camera(base64.b64decode(data["jpeg"]))
                    except (ValueError, TypeError):
                        pass
                elif t == "camera_off":
                    orch.camera_off()
                elif t == "profile" and orch.student is not None and isinstance(data.get("profile"), dict):
                    orch.student.update_basics(data["profile"])  # name, grade, exams (mastery comes from exercises)
                    orch._save_profile()
                    orch._emit_profile()
                elif t == "video_codec" and data.get("codec") == "jpeg":
                    transport.video_codec = "jpeg"  # the page failed to decode H.264
        except WebSocketDisconnect:
            pass
        finally:
            try:
                if "panel_task" in locals():
                    panel_task.cancel()
                if worker is not None:
                    worker.cancel()
                if orch is not None:
                    if orch.student is not None:
                        profiles.unsubscribe(orch.student.student_id, orch.on_profile_edited)
                    await orch.stop()
                if transport.recorder is not None:
                    await asyncio.to_thread(transport.recorder.close)  # mux video + audio
            except Exception:  # noqa: BLE001
                log.exception("session cleanup failed")
            finally:
                if shared:
                    app.state.session_lock.release()

    return app


def main() -> None:
    import uvicorn

    args = parse_args()
    # Media binary frames need no deflate; it stalls the event loop.
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info", ws_per_message_deflate=False)


if __name__ == "__main__":
    main()

===== FILE: live_agent/backend/config.py =====
"""Backend paths and command-line configuration, independent of frontend assets."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD_IMAGES = ROOT / ".cache" / "board_images"
CURRICULUM = ROOT / "configs" / "curriculum"
STUDENT_SEEDS = ROOT / "configs" / "students"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live-agent API and streaming backend")
    p.add_argument("--config", default=str(ROOT / "configs" / "persona_hanfu"))
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3", "vllm_omni_h3"])
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--llm-api-key-env", default="LLM_API_KEY",
                   help="environment variable holding the responder's API key (hosted models)")
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--asr-url", default="http://127.0.0.1:8103/v1")
    p.add_argument("--asr-model", default="qwen3-asr")
    p.add_argument("--memory-db", default=str(ROOT / ".cache" / "memory.sqlite"))
    p.add_argument("--log-dir", default=str(ROOT / ".cache" / "sessions"))
    p.add_argument("--record", action="store_true", help="record each session's presented audio/video to <log-dir>/<session>.mp4")
    p.add_argument("--director-mode", default="closed_loop", choices=["closed_loop", "open_loop"])
    p.add_argument("--correction-mode", default="gradient", choices=["gradient", "repeat", "none"])
    p.add_argument("--lambda-prior", type=float, default=3.0)
    p.add_argument("--mock-judge-p", type=float, default=1.0, help="with --vlm-url mock: P(action judged done)")
    p.add_argument("--dev-allow-uncalibrated", action="store_true",
                   help="allow capabilities that were never executed (development only)")
    p.add_argument("--image-url", default="", help="board figure server (Qwen-Image via vLLM-Omni), empty: none")
    p.add_argument("--video-codec", default="auto", choices=["auto", "jpeg"],
                   help="auto: H.264 segments to pages that can decode them (WebCodecs), else JPEG frames")
    p.add_argument("--student", default="demo", help="student profile id for private sessions (the page may pick one)")
    p.add_argument("--students", default="", help="comma-separated profile ids the page may pick (default: only --student)")
    p.add_argument("--student-store", default=str(BOARD_IMAGES.parent / "students"), help="saved student profiles (personal data)")
    p.add_argument("--lesson-self-check", default="log", choices=["off", "log", "revise"],
                   help="judge every lesson section against the lesson-quality checklist: log only, or rewrite "
                        "a failing section once before it plays (sections after the first)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8201)
    # Generator options (--taomate-*, --omni-*) are parsed by the adapters (taomate_h3.py, vllm_omni_h3.py).
    args, rest = p.parse_known_args(argv)
    args.extra = rest
    return args

===== FILE: live_agent/backend/runtime.py =====
"""Factories for backend-only models and scoped memory; credentials stay here."""

from __future__ import annotations

import argparse


def llm_api_key(args: argparse.Namespace) -> str:
    """The responder's API key comes from an environment variable (never argv: visible in ps); local vLLM
    needs none."""
    import os

    return os.environ.get(args.llm_api_key_env) or "EMPTY"


def make_generator(args: argparse.Namespace):
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator

        return MockGenerator(size=(864, 480), render_text=True)  # portrait, like TaoMate-H3 480x864
    if args.generator == "taomate_h3":
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        return TaoMateH3Generator.from_args(args)
    if args.generator == "vllm_omni_h3":  # TaoMate-H3 served by vLLM-Omni (USP4) over its realtime WebSocket
        from live_agent.generator.vllm_omni_h3 import VllmOmniH3Generator

        return VllmOmniH3Generator.from_args(args)
    raise ValueError(args.generator)


def make_memory(args: argparse.Namespace, hello: dict, session_id: str, scope: str = "private"):
    if not args.memory_db:
        return None
    from live_agent.memory_bridge import MemoryBridge

    return MemoryBridge(args.memory_db, user_id=hello.get("user_id", "anon"),
                        stream_id=hello.get("stream_id", "stream-0"), session_id=session_id, mode=scope)



===== FILE: live_agent/backend/resources.py =====
"""Backend resource APIs and media files; browser views belong to frontend/."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

from live_agent.backend.config import BOARD_IMAGES
from live_agent.student import ProfileStore

TRACE_NAME = re.compile(r"^sess-[A-Za-z0-9_-]+(\.generated(-part\d+)?)?\.(jsonl|mp4)$")
BOARD_IMAGE = re.compile(r"^(p[0-9a-f]{15}|[0-9a-f]{16})\.png$")
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


def register_resources(app: FastAPI, args: argparse.Namespace, profiles: ProfileStore) -> None:
    @app.get("/api/health")
    async def health() -> dict:
        # Uvicorn does not serve until model startup has completed.
        return {"status": "ok", "generator": args.generator, "protocol_version": 1}

    @app.get("/api/traces")
    def traces() -> dict:
        """Structured trace metadata for the frontend's recorded-session view."""
        directory = Path(args.log_dir)
        sessions = []
        files = [f for f in directory.glob("sess-*.jsonl") if TRACE_NAME.fullmatch(f.name) and f.is_file()]
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:200]:
            stat = f.stat()
            video_name = re.compile(re.escape(f.stem) + r"(\.generated(-part\d+)?|-part\d+)?\.mp4$")
            videos = []
            for video in sorted(directory.glob(f"{f.stem}*.mp4")):
                if not video.is_file() or not video_name.fullmatch(video.name):
                    continue
                rest = video.name[len(f.stem):-4].lstrip(".-")
                label = rest if rest.startswith("generated") else "presented" + (" " + rest if rest else "")
                videos.append({"name": video.name, "label": label, "url": f"/traces/file/{video.name}"})
            sessions.append({"id": f.stem, "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                             "size_bytes": stat.st_size, "trace_url": f"/traces/file/{f.name}", "videos": videos})
        return {"sessions": sessions}

    @app.get("/traces/file/{name}")
    async def trace_file(name: str) -> FileResponse:
        if not TRACE_NAME.fullmatch(name):
            raise HTTPException(404)
        path = Path(args.log_dir) / name
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "application/x-ndjson",
                            filename=name, headers=PRIVATE_HEADERS)

    @app.get("/board/img/{name}")
    async def board_img(name: str) -> FileResponse:
        path = BOARD_IMAGES / name
        if not BOARD_IMAGE.fullmatch(name) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/png", headers=PRIVATE_HEADERS)

    def profile_or_404(student_id: str):
        profile = profiles.get(student_id)
        if profile is None:
            raise HTTPException(404, "unknown student")
        return profile

    def full(profile) -> dict:
        return {**profile.view(), "saved": profiles.exists(profile.student_id)}

    @app.get("/api/students")
    async def list_students() -> dict:
        return {"students": [{"id": sid, "name": profiles.get(sid).name, "grade": profiles.get(sid).grade,
                              "saved": profiles.exists(sid)} for sid in profiles.allowed]}

    @app.get("/api/students/{student_id}")
    async def get_student(student_id: str) -> dict:
        return full(profile_or_404(student_id))

    @app.put("/api/students/{student_id}")
    async def put_student(student_id: str, body: dict = Body(...)) -> dict:
        profile = profile_or_404(student_id)
        if body.get("version") != profile.version:
            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
        try:
            profile.page_edit(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        profiles.changed(student_id)
        return full(profile)

    @app.post("/api/students/{student_id}/reset")
    async def reset_student(student_id: str, body: dict = Body(default={})) -> dict:
        profile = profile_or_404(student_id)
        if body.get("version") != profile.version:
            raise HTTPException(409, "the profile changed since it was loaded (reload to see the latest)")
        return full(profiles.reset(student_id))

===== FILE: live_agent/backend/transport.py =====
"""WebSocket media encoding, presentation acknowledgements and panel events.

The binary protocol is preserved across the frontend proxy; the browser's audio
output clock is mapped to server monotonic time using ping samples.
"""

from __future__ import annotations

import asyncio
import io
from fractions import Fraction
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import WebSocket

from live_agent.orchestrator import Orchestrator
from live_agent.types import BlockScript, Chunk, now

log = logging.getLogger("live_agent.backend.transport")


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def encode_h264(frames: np.ndarray, crf: int = 26) -> tuple[bytes, list[int]]:
    """One self-contained H.264 segment per chunk (baseline, IDR first, no B-frames: decodable on its own,
    so a barge-in can drop any chunk). Returns the Annex-B bytes and the size of each frame's access unit.
    About 5x smaller than per-frame JPEG q80 at 480x864 [measured locally], which the remote bridge needs."""
    import av

    n, h, w = frames.shape[:3]
    enc = av.CodecContext.create("libx264", "w")
    enc.width, enc.height, enc.pix_fmt = w, h, "yuv420p"
    enc.time_base = Fraction(1, 24)
    enc.framerate = Fraction(24, 1)
    enc.options = {"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline", "crf": str(crf),
                   "g": str(max(n, 1) + 1), "bf": "0", "threads": "4"}
    out, sizes = [], []

    def keep(packets):
        for pkt in packets:
            b = bytes(pkt)
            out.append(b)
            sizes.append(len(b))

    for i, f in enumerate(frames):
        vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24").reformat(format="yuv420p")
        vf.pts = i
        keep(enc.encode(vf))
    keep(enc.encode(None))
    return b"".join(out), sizes


def to_pcm16(audio: np.ndarray | None, n_samples: int) -> bytes:
    if audio is None or len(audio) == 0:
        return np.zeros(n_samples, dtype=np.int16).tobytes()
    a = audio.mean(axis=1) if audio.ndim == 2 else audio
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


PANEL_EVENTS = {"lock", "verdict", "repair", "completion_claim", "refusal", "capacity_skip", "narration_guard",
                "playback_stop", "speech_onset", "utterance_end", "audit", "error", "request_done", "continuity", "lesson", "attention"}
PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
                "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
                "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
                "decision", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
                "audibility", "revision", "speaker", "uid", "counts", "expected", "wrong", "target", "gave_up", "anchor_removed", "stage",
                "title", "sections", "section", "lines", "points", "board", "seconds",
                "attempt", "labels",
                "point", "judgements", "state", "stable", "nudge",
                "plan", "note", "adaptive", "depth", "exercise", "concept", "correct", "skipped", "misconception",
                "mastery", "profile", "changed", "options", "topic")


def panel_event(ev, t0: float) -> dict | None:
    """Compact, display-only form of a timeline event (the full log stays on disk)."""
    if ev.type.value not in PANEL_EVENTS:
        return None
    if ev.type.value == "error" and ev.data.get("where") in ("event_loop_stack",):
        return None
    data = {k: ev.data[k] for k in PANEL_FIELDS if k in ev.data}
    if isinstance(data.get("rationale"), str):
        data["rationale"] = data["rationale"][:160]
    return {"type": "event", "event": ev.type.value, "t": round(ev.t - t0, 2), "request": ev.request_index,
            "data": data}


class WSTransport:
    """Orchestrator transport over one WebSocket connection.

    Presentation times: the client reports, for each chunk, when its audio starts / ends at the
    audio *output* (AudioContext.getOutputTimestamp -> performance clock, ``tp`` in ms). The
    server maps that clock to its own with the lowest-RTT ping sample (NTP-style,
    offset = t_server - (t_client_send + rtt/2)). Until a mapping exists, arrival time is used
    (and the event says so)."""

    def __init__(self, ws: WebSocket, record_path: Path | None = None, video_codec: str = "jpeg"):
        self.ws = ws
        self.video_codec = video_codec  # "h264" when the page can decode it (WebCodecs), else "jpeg"
        self.orchestrator: Orchestrator | None = None
        # trace recording: exactly the chunks the client reports as played (chunk_end acks), in order
        self.record_path = record_path
        self.recorder = None
        self._part = 1
        self._sent: dict[tuple[int, int], Chunk] = {}
        if record_path is not None:
            self._new_recorder()
        self._send_lock = asyncio.Lock()
        self._starts: dict[tuple[int, int], float] = {}
        self._epoch = 0  # incremented on stop; stale sends are skipped
        self.clock_offset_s: float | None = None
        self.clock_rtt_s: float | None = None

    def _new_recorder(self) -> None:
        from live_agent.sim import Recorder

        path = self.record_path if self._part == 1 else self.record_path.with_name(
            f"{self.record_path.stem}-part{self._part}{self.record_path.suffix}")
        self.recorder = Recorder(path)

    def restart_recording(self) -> None:
        """After an erasure deleted the recording, continue in a new part file."""
        if self.record_path is not None:
            self._part += 1
            self._new_recorder()

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        if self.recorder is not None:
            self._sent[(chunk.request_index, chunk.chunk_index)] = chunk
        epoch = self._epoch
        frames = chunk.video if chunk.video is not None else np.zeros((chunk.n_frames, 8, 8, 3), np.uint8)
        # Encode off the event loop.
        loop = asyncio.get_running_loop()
        segment, sizes, jpegs = None, None, None
        if self.video_codec == "h264" and chunk.video is not None and len(frames):
            try:
                segment, sizes = await loop.run_in_executor(None, encode_h264, frames)
                if len(sizes) != len(frames):
                    segment = sizes = None  # one access unit per frame or nothing: fall back for this chunk
            except Exception:  # noqa: BLE001 - never lose a chunk to the encoder
                log.exception("H.264 encode failed; sending JPEG")
                segment = sizes = None
        if segment is None:
            jpegs = await loop.run_in_executor(None, lambda: [encode_jpeg(f) for f in frames])
        pcm = to_pcm16(chunk.audio, int(chunk.duration_s * chunk.sample_rate))
        async with self._send_lock:
            if epoch != self._epoch:
                return
            h, w = frames.shape[1:3]
            header = {
                "type": "chunk", "request": chunk.request_index, "chunk": chunk.chunk_index,
                "n_frames": len(frames), "fps": chunk.fps, "sample_rate": chunk.sample_rate,
                "duration": chunk.duration_s,  # media duration (may differ from n_frames / fps)
                "width": int(w), "height": int(h), "transcript": script.transcript,
                "codec": "h264" if segment is not None else "jpeg"}
            if segment is not None:
                header["sizes"] = sizes
            board = getattr(script, "board", None)
            if board is not None and chunk.chunk_index == 0:
                header["board"] = board  # shown when this chunk starts playing: aligned with the line
            await self.ws.send_text(json.dumps(header))
            if segment is not None:
                await self.ws.send_bytes(segment)
            else:
                for j in jpegs:
                    if epoch != self._epoch:
                        return  # interrupted mid-chunk: the client discards the partial chunk
                    await self.ws.send_bytes(j)
            if epoch == self._epoch:
                await self.ws.send_bytes(pcm)

    async def send_json(self, obj: dict) -> None:
        """Small control/panel messages, sent between (never inside) a chunk's binary frames."""
        async with self._send_lock:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))

    async def stop_playback(self) -> None:
        """Immediate: does not wait for an in-flight chunk send (which aborts at its next frame)."""
        self._epoch += 1
        self._sent.clear()  # interrupted chunks were never (fully) shown: not recorded
        await self.ws.send_text(json.dumps({"type": "stop"}))

    def in_flight(self):
        """(request, chunk, start time) of a chunk that started playing but has not ended."""
        if not self._starts:
            return None
        (k, ci), t = max(self._starts.items(), key=lambda kv: kv[1])
        return (k, ci, t)

    def on_clock(self, msg: dict) -> None:
        rtt = float(msg["rtt"]) / 1000.0
        if self.clock_rtt_s is None or rtt <= self.clock_rtt_s:
            self.clock_rtt_s = rtt
            self.clock_offset_s = float(msg["t_server"]) - (float(msg["t_client"]) / 1000.0 + rtt / 2)

    def _to_server(self, msg: dict) -> float:
        if msg.get("tp") is not None and self.clock_offset_s is not None:
            return float(msg["tp"]) / 1000.0 + self.clock_offset_s
        return now()

    def on_client_message(self, msg: dict) -> None:
        t = self._to_server(msg)
        key = (int(msg.get("request", -1)), int(msg.get("chunk", -1)))
        if msg["type"] == "chunk_start":
            self._starts[key] = t
        elif msg["type"] == "chunk_end" and self.orchestrator is not None:
            ch = self._sent.pop(key, None)
            if ch is not None and self.recorder is not None:
                self.recorder.write(ch)  # background-thread encoding
            painted = msg.get("painted")
            t_paint = (self._to_server({"tp": msg["tp_last_paint"]}) if msg.get("tp_last_paint") is not None
                       and self.clock_offset_s is not None else None)
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t,
                                           painted=[int(i) for i in painted] if painted is not None else None,
                                           t_last_paint=t_paint)
        elif msg["type"] == "chunk_received" and self.orchestrator is not None and self.clock_offset_s is not None:
            self.orchestrator.on_received(key[0], key[1], t)



===== FILE: live_agent/server/app.py =====
"""Compatibility entrypoint for the API backend; use live_agent.backend.app.

Browser pages are served independently by frontend/server.mjs.
"""

from live_agent.backend.app import build_app, main
from live_agent.backend.runtime import llm_api_key, make_generator, make_memory
from live_agent.backend.transport import WSTransport, encode_h264, encode_jpeg, panel_event, to_pcm16

__all__ = ["build_app", "main", "llm_api_key", "make_generator", "make_memory",
           "WSTransport", "encode_h264", "encode_jpeg", "panel_event", "to_pcm16"]

if __name__ == "__main__":
    main()

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
for port in "$PORT" "$BACKEND_PORT"; do
  [[ "$port" =~ ^[0-9]+$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 )) || { echo "invalid port: $port"; exit 2; }
done
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
    for p in "${helper_ports[@]}"; do port_free "$p" || { echo "helper port $p already in use (models running?)"; exit 1; }; done
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
    for p in "${helper_ports[@]}"; do port_free "$p" || { echo "helper port $p already in use (models running?)"; exit 1; }; done
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
    for p in "${ports[@]}"; do port_free $p || { echo "port $p already in use (models running?)"; exit 1; }; done
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

===== FILE: scripts/packed_stack.sh =====
#!/usr/bin/env bash
# Everything on 4 GPUs (run inside ONE `gpu run --gpus 4` reservation; CUDA_VISIBLE_DEVICES = those 4):
# helper models packed next to TaoMate-H3 (student + colocated audio teacher on all 4 cards).
# Memory per card [measured locally, M0]: TaoMate colocated ~106 GiB + <=24 GiB helper, of 140 GiB.
# (ASR needs >=0.10: at 0.06 vLLM had no room left for its KV cache.)
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
IFS=, read -r -a D <<< "${CUDA_VISIBLE_DEVICES:?run inside gpu run --gpus 4}"
[ "${#D[@]}" -ge 4 ] || { echo "need 4 GPUs, got ${CUDA_VISIBLE_DEVICES}"; exit 1; }
HELPER_LOG=${HELPER_LOG:-.cache/logs/serve_models.packed.out}
mkdir -p "$(dirname "$HELPER_LOG")"
: > "$HELPER_LOG"
DEV_LLM=${D[0]} DEV_VLM=${D[1]} DEV_ASR=${D[2]} UTIL_LLM=0.16 UTIL_VLM=0.17 UTIL_ASR=0.10 LEN_LLM=8192 LEN_VLM=8192 \
  scripts/serve_models.sh > "$HELPER_LOG" 2>&1 &
H=$!
trap 'kill "$H" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
t0=$SECONDS
until grep -q ALL_READY "$HELPER_LOG" 2>/dev/null; do
  kill -0 $H 2>/dev/null || { echo "helper models failed:"; tail -20 "$HELPER_LOG"; exit 1; }
  [ $((SECONDS - t0)) -lt "${READY_TIMEOUT:-1200}" ] || { echo "packed helper models not ready in time:"; tail -20 "$HELPER_LOG"; exit 1; }
  sleep 5
done
echo "[packed] helper models ready on GPUs ${D[0]},${D[1]},${D[2]}; starting TaoMate-H3 on ${D[0]},${D[1]},${D[2]},${D[3]} (colocated teacher)"
python3 -m live_agent.backend.app --generator taomate_h3 --taomate-student-devices "${D[0]},${D[1]},${D[2]},${D[3]}" \
  --taomate-colocate-teacher "$@"

===== FILE: scripts/server_check.sh =====
#!/usr/bin/env bash
# Backend-path check with TaoMate-H3: start the API (generator started once), run the headless client.
# Run under canhazgpu, e.g.:
#   gpu run --gpu-ids 0,1,2,3,4,5 --timeout 1h --note "live-agent server-path check" -- scripts/server_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
BACKEND_PORT=${BACKEND_PORT:-8201}
mkdir -p .cache/logs .cache/server_check
python3 -m live_agent.backend.app --generator taomate_h3 --dev-allow-uncalibrated --host 127.0.0.1 --port "$BACKEND_PORT" \
  --log-dir .cache/server_check > .cache/logs/server_check_server.log 2>&1 &
srv=$!
trap 'kill $srv 2>/dev/null; wait $srv 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
ready=0
for i in $(seq 1 600); do
  if curl --noproxy '*' --connect-timeout 1 --max-time 2 -sf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then ready=1; break; fi
  kill -0 $srv 2>/dev/null || { echo "server died"; tail -30 .cache/logs/server_check_server.log; exit 1; }
  sleep 1
done
[ "$ready" = "1" ] || { echo "backend not ready after readiness timeout"; tail -30 .cache/logs/server_check_server.log; exit 1; }
python3 scripts/ws_client_check.py --url "ws://127.0.0.1:$BACKEND_PORT/ws" --seconds 80 --say "8:请喝口茶吧" --say "30:跟我挥挥手吧" --say "50:我妹妹住在杭州" --say "62:请忘掉我妹妹住在哪"

===== FILE: tests/test_backend_api.py =====
"""The standalone backend owns data and media, without depending on browser assets."""

import json
import os

from fastapi.testclient import TestClient

from live_agent.backend.app import build_app
from live_agent.backend.config import parse_args


def backend(tmp_path):
    args = parse_args(["--generator", "mock", "--llm-url", "scripted", "--vlm-url", "mock", "--asr-url", "",
                       "--memory-db", "", "--student-store", str(tmp_path / "students"),
                       "--log-dir", str(tmp_path / "logs"), "--dev-allow-uncalibrated"])
    return build_app(args)


def test_backend_runs_without_browser_views_and_documents_its_api(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "generator": "mock", "protocol_version": 1}
        for path in ("/", "/profile", "/traces", "/assets/live.js", "/static/index.html"):
            assert client.get(path).status_code == 404
        paths = client.get("/openapi.json").json()["paths"]
        assert {"/api/health", "/api/traces", "/api/students", "/api/curriculum"} <= paths.keys()
        assert "/profile" not in paths and "/traces" not in paths
        assert client.get("/api/students").headers["cache-control"] == "no-store"


def test_trace_index_returns_data_and_only_its_own_media(tmp_path):
    directory = tmp_path / "logs"
    directory.mkdir()
    first = directory / "sess-a.jsonl"
    first.write_text('{"type":"lock"}\n')
    second = directory / "sess-ab.jsonl"
    second.write_text('{"type":"stop"}\n')
    os.utime(first, (100, 100))
    os.utime(second, (200, 200))
    names = ["sess-a.mp4", "sess-a-part2.mp4", "sess-a.generated.mp4", "sess-a.generated-part2.mp4", "sess-ab.mp4"]
    for name in names:
        (directory / name).write_bytes(b"media")
    (directory / "sess-<bad>.jsonl").write_text("untrusted filename")
    (directory / "secret.txt").write_text("private")
    with TestClient(backend(tmp_path)) as client:
        response = client.get("/api/traces")
        assert response.headers["cache-control"] == "no-store"
        sessions = response.json()["sessions"]
        assert [s["id"] for s in sessions] == ["sess-ab", "sess-a"]
        session = sessions[1]
        assert session["size_bytes"] == first.stat().st_size
        assert session["updated_at"].endswith("+00:00")
        assert session["trace_url"] == "/traces/file/sess-a.jsonl"
        assert {v["name"] for v in session["videos"]} == set(names[:-1])
        assert {v["label"] for v in session["videos"]} == {"presented", "presented part2", "generated", "generated-part2"}
        assert client.get(session["trace_url"]).content == first.read_bytes()
        media = client.get("/traces/file/sess-a.mp4", headers={"Range": "bytes=1-3"})
        assert media.status_code == 206 and media.content == b"edi"
        assert media.headers["cache-control"] == "no-store"
        for path in ("/traces/file/secret.txt", "/traces/file/sess-missing.mp4", "/board/img/secret.txt"):
            assert client.get(path).status_code == 404


def test_websocket_keeps_hello_clock_and_binary_media_contract(tmp_path):
    with TestClient(backend(tmp_path)) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "mode": "private", "user_id": "test", "video_codecs": []})
            ws.send_json({"type": "ping", "t": 123.0})
            status = pong = chunk = None
            binary_frames = 0
            for _ in range(150):
                msg = ws.receive()
                if "bytes" in msg:
                    binary_frames += 1
                else:
                    data = json.loads(msg["text"])
                    if data["type"] == "status":
                        status = data
                    elif data["type"] == "pong":
                        pong = data
                    elif data["type"] == "chunk":
                        chunk = data
                if status and pong and chunk and binary_frames >= chunk["n_frames"] + 1:
                    break
            assert status["generator"] == "mock" and status["responder"] == "rules"
            assert pong["t"] == 123.0 and isinstance(pong["ts"], float)
            assert chunk["codec"] == "jpeg" and chunk["sample_rate"] > 0 and chunk["duration"] > 0
            assert binary_frames >= chunk["n_frames"] + 1


def test_old_server_module_is_a_compatibility_entrypoint():
    from live_agent.server.app import WSTransport, build_app as old_build_app
    from live_agent.backend.transport import WSTransport as transport

    assert old_build_app is build_app and WSTransport is transport


def test_presentation_timestamps_work_before_and_after_clock_sync():
    from live_agent.backend.transport import WSTransport
    from live_agent.types import now

    transport = WSTransport(None)
    start = now()
    assert start <= transport._to_server({}) <= now()
    assert start <= transport._to_server({"tp": 10.0}) <= now()
    transport.on_clock({"rtt": 20.0, "t_server": 100.0, "t_client": 1000.0})
    assert abs(transport._to_server({"tp": 1500.0}) - 100.49) < 1e-9
