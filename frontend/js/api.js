/* Banca Hípica P2P — cliente HTTP (token Bearer + manejo de errores). */
"use strict";

const API = (() => {
  const TOKEN_KEY = "banca_hipica_token";
  const USER_KEY = "banca_hipica_user";

  const token = () => localStorage.getItem(TOKEN_KEY) || "";
  const currentUser = () => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); }
    catch (_) { return null; }
  };
  const setSession = (tkn, user) => {
    localStorage.setItem(TOKEN_KEY, tkn);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  };
  const clearSession = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  };

  function extractDetail(data) {
    if (!data) return "Error inesperado.";
    const d = data.detail;
    if (typeof d === "string") return d;
    if (d && Array.isArray(d.errors)) {
      const head = d.message || "Errores";
      const shown = d.errors.slice(0, 5).join(" | ");
      const more = d.errors.length > 5 ? ` (+${d.errors.length - 5} más)` : "";
      return `${head} ${shown}${more}`;
    }
    if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join(", ");
    if (d && d.message) return d.message;
    return JSON.stringify(d || data);
  }

  async function request(method, path, body, isForm = false) {
    const headers = {};
    if (token()) headers["Authorization"] = `Bearer ${token()}`;

    let payload;
    if (isForm) {
      payload = body; // FormData: el navegador fija el Content-Type.
    } else if (body !== undefined && body !== null) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(path, { method, headers, body: payload });
    } catch (_) {
      throw new Error("No se pudo conectar con el servidor.");
    }

    const text = await res.text();
    let data = null;
    if (text) { try { data = JSON.parse(text); } catch (_) { data = { detail: text }; } }

    if (!res.ok) {
      if (res.status === 401 && currentUser()) {
        clearSession();
        window.dispatchEvent(new CustomEvent("auth:expired"));
      }
      const error = new Error(extractDetail(data));
      error.detail = data ? data.detail : null;  // Detalle crudo (p. ej. lista de errores)
      error.status = res.status;
      throw error;
    }
    return data;
  }

  return {
    token, currentUser, setSession, clearSession,
    get: (p) => request("GET", p),
    post: (p, b) => request("POST", p, b),
    put: (p, b) => request("PUT", p, b),
    del: (p) => request("DELETE", p),
    upload: (p, formData) => request("POST", p, formData, true),
    logout: async () => { try { await request("POST", "/auth/logout"); } catch (_) {} finally { clearSession(); } },
  };
})();
