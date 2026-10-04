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
