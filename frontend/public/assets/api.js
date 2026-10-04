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
