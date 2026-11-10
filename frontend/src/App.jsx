import { useCallback, useEffect, useMemo, useState } from "react";
import { auth, get, post } from "./api";
import { AppCtx, useToast } from "./components/ui";
import Login from "./pages/Login";
import Produksi from "./pages/Produksi";
import Kalender from "./pages/Kalender";
import Pengaturan from "./pages/Pengaturan";
import { fmtDate, fmtTime } from "./util";

export default function App() {
  const [state, setState] = useState(null);
  const [meta, setMeta] = useState(null);
  const [viewOnly, setViewOnly] = useState(false);
  const [tab, setTab] = useState(() => new URLSearchParams(location.search).get("tab") || "produksi");
  const [tick, setTick] = useState(0);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [toast, toastView] = useToast();

  const load = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([get("/api/state"), meta ? Promise.resolve(meta) : get("/api/meta")]);
      if (!s.me && auth.token) auth.set("");
      setState(s);
      setMeta(m);
      setLastRefresh(new Date());
    } catch (e) {
      toast("Gagal memuat: " + e.message, "err");
    }
  }, [meta, toast]);

  const reload = useCallback(() => { setTick((t) => t + 1); }, []);

  useEffect(() => { load(); }, [tick]); // eslint-disable-line

  // Realtime ringan: polling 8 detik, berhenti saat tab tersembunyi
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) setTick((t) => t + 1); }, 8000);
    return () => clearInterval(id);
  }, []);

  const ctx = useMemo(() => {
    const me = state?.me || null;
    const members = state?.members || [];
    const byId = Object.fromEntries(members.map((m) => [m.id, m]));
    const role = me?.role;
    return {
      me, members, byId, settings: state?.settings, meta, today: state?.today, tick, reload, toast,
      canEdit: !!me,
      isLead: role === "approver" || role === "creative_lead",
      isApprover: role === "approver",
      isSocmed: role === "socmed" || role === "approver" || role === "creative_lead",
      name: (id) => byId[id]?.name || (id === "panel" ? "Panel Admin" : id || "–"),
    };
  }, [state, meta, tick, reload, toast]);

  if (!state || !meta) return <div className="p-8 text-center text-gray-500">Memuat…</div>;
  if (!state.me && !viewOnly) return (
    <AppCtx.Provider value={ctx}>
      <Login onDone={() => { setViewOnly(false); reload(); }} onViewOnly={() => setViewOnly(true)} />
      {toastView}
    </AppCtx.Provider>
  );

  const tabs = [["produksi", "Produksi"], ["kalender", "Kalender"]];
  if (ctx.isLead) tabs.push(["pengaturan", "Pengaturan"]);
  const go = (t) => { setTab(t); const u = new URL(location.href); u.searchParams.set("tab", t); history.replaceState(null, "", u); };

  return (
    <AppCtx.Provider value={ctx}>
      <div className="min-h-screen">
        <header className="bg-brand text-white">
          <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-3 flex items-center gap-3">
            <img src="/logo.svg" alt="" className="h-9 w-9 rounded-lg bg-white/10" />
            <div className="min-w-0">
              <div className="font-extrabold leading-tight">Cimol Bojot AA</div>
              <div className="text-[11px] opacity-90">{fmtDate(state.today, true)}</div>
            </div>
            <div className="ml-auto flex items-center gap-2 text-right">
              <div className="hidden sm:block text-[11px] leading-tight opacity-90">
                <span className="inline-block h-2 w-2 rounded-full bg-green-300 mr-1 animate-pulse" />LIVE {lastRefresh ? fmtTime(lastRefresh.toISOString()) : ""}
              </div>
              <div className="font-extrabold text-lg hidden md:block">Creative Hub</div>
              {state.me ? (
                <div className="flex items-center gap-2">
                  <div className="text-xs leading-tight text-right">
                    <div className="font-semibold">{state.me.name}</div>
                    <div className="opacity-80">{state.me.jobFunction}</div>
                  </div>
                  <button className="btn btn-sm bg-white/15 hover:bg-white/25" onClick={async () => { try { await post("/api/auth/logout"); } catch { /* */ } auth.set(""); reload(); }}>Keluar</button>
                </div>
              ) : (
                <button className="btn btn-sm bg-white text-brand" onClick={() => setViewOnly(false)}>Masuk</button>
              )}
            </div>
          </div>
          <nav className="max-w-[1400px] mx-auto px-3 md:px-6 flex gap-1">
            {tabs.map(([k, l]) => (
              <button key={k} onClick={() => go(k)}
                className={`px-4 py-2 text-sm font-semibold rounded-t-lg ${tab === k ? "bg-white text-brand" : "text-white/90 hover:bg-white/10"}`}>{l}</button>
            ))}
            {!state.me && <span className="ml-auto self-center text-[11px] opacity-90 pb-1">Mode lihat saja</span>}
          </nav>
        </header>
        <main className="max-w-[1400px] mx-auto px-3 md:px-6 py-4">
          {tab === "produksi" && <Produksi />}
          {tab === "kalender" && <Kalender />}
          {tab === "pengaturan" && ctx.isLead && <Pengaturan />}
        </main>
      </div>
      {toastView}
    </AppCtx.Provider>
  );
}
