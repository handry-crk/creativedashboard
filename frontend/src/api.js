const BASE = import.meta.env.VITE_API_URL || "";

export const auth = {
  get token() { try { return localStorage.getItem("crk_ch_token") || ""; } catch { return ""; } },
  set(t) { try { t ? localStorage.setItem("crk_ch_token", t) : localStorage.removeItem("crk_ch_token"); } catch { /* */ } },
};

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : detail?.message || "Terjadi kesalahan");
    this.status = status;
    this.detail = typeof detail === "object" ? detail : { message: detail };
  }
}

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch(BASE + path, { method, headers, body: payload });
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data);
  return data;
}

export const get = (p) => api(p);
export const post = (p, body) => api(p, { method: "POST", body: body ?? {} });
export const put = (p, body) => api(p, { method: "PUT", body });
export const del = (p) => api(p, { method: "DELETE" });

export function download(path, filename) {
  fetch(BASE + path, { headers: auth.token ? { Authorization: `Bearer ${auth.token}` } : {} })
    .then((r) => r.blob())
    .then((b) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
}
