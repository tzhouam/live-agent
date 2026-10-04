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
