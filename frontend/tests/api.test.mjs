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
