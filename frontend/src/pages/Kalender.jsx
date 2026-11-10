import { useEffect, useMemo, useRef, useState } from "react";
import { api, download, get, put } from "../api";
import { Empty, Select, useApp, useRunner } from "../components/ui";
import { CONTENT_COLORS, PLATFORM_ICON, fmtDate, isoWeek, monthLabel, parseD, shiftMonth, ymd } from "../util";
import ContentDrawer from "./ContentDrawer";
import RequestDrawer from "./RequestDrawer";

const HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

export default function Kalender() {
  const { tick, today, members, meta, isSocmed, settings, isLead } = useApp();
  const run = useRunner();
  const [month, setMonth] = useState(() => (today || ymd(new Date())).slice(0, 7));
  const [items, setItems] = useState([]);
  const [mix, setMix] = useState(null);
  const [warns, setWarns] = useState([]);
  const [f, setF] = useState({ platform: "semua", pic: "", pillar: "" });
  const [view, setView] = useState(() => (window.innerWidth < 768 ? "list" : "month"));
  const [open, setOpen] = useState(null); // {id} | {date}
  const [reqOpen, setReqOpen] = useState(null);
  const [showPanel, setShowPanel] = useState(window.innerWidth >= 1024);
  const fileRef = useRef();

  useEffect(() => {
    const q = `month=${month}${f.platform !== "semua" ? `&platform=${f.platform}` : ""}${f.pic ? `&pic=${f.pic}` : ""}`;
    Promise.all([get(`/api/content?${q}`), get(`/api/content/mix?month=${month}`), get(`/api/content/warnings?month=${month}`)])
      .then(([i, m, w]) => { setItems(i); setMix(m); setWarns(w); }).catch(() => {});
  }, [tick, month, f.platform, f.pic]);

  const shown = useMemo(() => items.filter((i) => !f.pillar || i.pillar === f.pillar), [items, f.pillar]);
  const byDate = useMemo(() => {
    const m = {};
    shown.forEach((i) => { (m[i.date] = m[i.date] || []).push(i); });
    return m;
  }, [shown]);
  const warnByItem = useMemo(() => {
    const m = {};
    warns.forEach((w) => { (m[w.itemId] = m[w.itemId] || []).push(w); });
    return m;
  }, [warns]);

  // grid hari
  const first = parseD(`${month}-01`);
  const startPad = (first.getDay() + 6) % 7;
  const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const cells = [...Array(startPad).fill(null), ...Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  while (cells.length % 7) cells.push(null);
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  async function importCsv(e) {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const r = await run(() => api("/api/content/import", { method: "POST", form }));
    if (r) alert(`${r.created} baris diimpor.${r.errors.length ? `\n\n${r.errors.length} baris gagal:\n` + r.errors.slice(0, 15).map((x) => `Baris ${x.row}: ${x.message}`).join("\n") : ""}`);
    e.target.value = "";
  }

  async function setTheme(week) {
    const cur = settings?.weekThemes?.[week] || "";
    const v = window.prompt(`Tema minggu ${week}:`, cur);
    if (v === null) return;
    await run(() => put("/api/settings", { weekThemes: { ...(settings?.weekThemes || {}), [week]: v } }), "Tema disimpan");
  }

  const Chip = ({ i }) => {
    const w = warnByItem[i.id] || [];
    return (
      <button onClick={(e) => { e.stopPropagation(); setOpen({ id: i.id }); }}
        className={`w-full text-left rounded border px-1 py-0.5 text-[11px] leading-tight ${CONTENT_COLORS[i.status]}`}>
        <span className="font-bold">{PLATFORM_ICON[i.platform]}</span> {i.format}{i.time ? ` ${i.time}` : ""}
        <div className="truncate">{i.hook || i.idea || "–"}</div>
        <div className="flex flex-wrap gap-0.5 mt-0.5">
          {i.assetReady && <span className="chip !px-1 bg-brand-yellow text-brand-ink">Aset siap</span>}
          {i.isPromo && <span className="chip !px-1 bg-brand text-white">Promo</span>}
          {i.isPromo && !["GO", "GWC"].includes(i.gateStatus) && <span className="chip !px-1 bg-red-100 text-red-700">Menunggu Gate</span>}
          {i.isReactiveSlot && <span className="chip !px-1 bg-indigo-100 text-indigo-700">Reaktif</span>}
          {w.some((x) => ["asset_not_ready", "double_promo", "asset_cancelled"].includes(x.type)) && <span className="chip !px-1 bg-red-600 text-white">Konflik</span>}
        </div>
      </button>
    );
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="flex items-center gap-1">
          <button className="btn-ghost btn-sm" onClick={() => setMonth(shiftMonth(month, -1))}>‹</button>
          <div className="font-bold w-36 text-center">{monthLabel(month)}</div>
          <button className="btn-ghost btn-sm" onClick={() => setMonth(shiftMonth(month, 1))}>›</button>
          <button className="btn-ghost btn-sm" onClick={() => setMonth(today.slice(0, 7))}>Hari ini</button>
        </div>
        <Select className="!w-28" value={f.platform} onChange={(v) => setF({ ...f, platform: v || "semua" })} options={[{ value: "semua", label: "Semua" }, { value: "IG", label: "IG" }, { value: "TT", label: "TikTok" }]} />
        <Select className="!w-36" value={f.pic} onChange={(v) => setF({ ...f, pic: v || "" })} options={members.filter((m) => m.role === "socmed").map((m) => ({ value: m.id, label: m.name }))} placeholder="Semua PIC" />
        <Select className="!w-44" value={f.pillar} onChange={(v) => setF({ ...f, pillar: v || "" })} options={meta.pillars} placeholder="Semua pillar" />
        <div className="flex rounded-lg border border-brand-line overflow-hidden text-sm">
          {[["month", "Bulan"], ["list", "List"]].map(([k, l]) => <button key={k} onClick={() => setView(k)} className={`px-3 py-2 font-semibold ${view === k ? "bg-brand text-white" : "bg-white"}`}>{l}</button>)}
        </div>
        <button className="btn-ghost btn-sm" onClick={() => setShowPanel(!showPanel)}>Mix & peringatan {warns.length ? `(${warns.length})` : ""}</button>
        <div className="ml-auto flex gap-2">
          <button className="btn-ghost btn-sm" onClick={() => download(`/api/content/export?month=${month}`, `kalender-konten-${month}.csv`)}>Ekspor CSV</button>
          {isSocmed && <><button className="btn-ghost btn-sm" onClick={() => fileRef.current.click()}>Impor CSV</button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={importCsv} /></>}
          {isSocmed && <button className="btn-primary btn-sm" onClick={() => setOpen({ date: today.startsWith(month) ? today : `${month}-01` })}>+ Konten</button>}
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-3">
        <div className="flex-1 min-w-0">
          {view === "month" ? (
            <div className="card overflow-x-auto">
              <div className="grid grid-cols-[repeat(7,minmax(110px,1fr))_minmax(90px,0.7fr)] min-w-[880px]">
                {HARI.map((h) => <div key={h} className="th text-center">{h}</div>)}
                <div className="th text-center">Tema</div>
                {weeks.map((w, wi) => {
                  const firstDay = w.find(Boolean);
                  const wk = firstDay ? isoWeek(firstDay) : "";
                  return [
                    ...w.map((d, di) => {
                      if (!d) return <div key={`e${wi}${di}`} className="border-b border-r border-brand-line bg-gray-50 min-h-[110px]" />;
                      const list = byDate[d] || [];
                      const stories = list.filter((i) => i.format === "Story");
                      const main = list.filter((i) => i.format !== "Story");
                      const weekend = di >= 5;
                      return (
                        <div key={d} onClick={() => isSocmed && setOpen({ date: d })}
                          className={`border-b border-r border-brand-line p-1 min-h-[110px] space-y-1 ${weekend ? "bg-brand-cream" : ""} ${d === today ? "ring-2 ring-inset ring-brand" : ""} ${isSocmed ? "cursor-pointer" : ""}`}>
                          <div className={`text-xs font-bold ${d === today ? "text-brand" : "text-gray-500"}`}>{Number(d.slice(8))}</div>
                          {main.map((i) => <Chip key={i.id} i={i} />)}
                          {stories.length > 0 && (
                            <button onClick={(e) => { e.stopPropagation(); stories.length === 1 ? setOpen({ id: stories[0].id }) : setView("list"); }}
                              className={`chip ${CONTENT_COLORS[stories[0].status]} border`}>Story ×{stories.length}</button>
                          )}
                        </div>
                      );
                    }),
                    <div key={`t${wi}`} className="border-b border-brand-line p-1 text-[11px] bg-white">
                      <div className="text-gray-400">{wk.slice(5)}</div>
                      <button disabled={!isLead && !isSocmed} onClick={() => setTheme(wk)} className="text-left font-semibold text-brand-deep">{settings?.weekThemes?.[wk] || (isSocmed ? "+ tema" : "")}</button>
                    </div>,
                  ];
                })}
              </div>
            </div>
          ) : (
            <ListView byDate={byDate} warnByItem={warnByItem} setOpen={setOpen} isSocmed={isSocmed} month={month} />
          )}
        </div>

        {showPanel && mix && (
          <aside className="lg:w-80 shrink-0 space-y-3">
            <div className="card p-3">
              <div className="font-bold text-sm mb-2">Mix pillar {monthLabel(month)} <span className="text-xs font-normal text-gray-500">({mix.total} konten, tanpa Story)</span></div>
              {mix.pillars.map((p) => (
                <div key={p.pillar} className="mb-2">
                  <div className="flex justify-between text-xs"><span>{p.pillar}</span>
                    <span className={p.flag ? "text-brand font-bold" : ""}>{p.pct}% / {p.target}% ({p.delta > 0 ? "+" : ""}{p.delta})</span></div>
                  <div className="relative h-2 rounded bg-gray-100">
                    <div className={`h-2 rounded ${p.flag ? "bg-brand" : "bg-brand-deep/70"}`} style={{ width: `${Math.min(p.pct, 100)}%` }} />
                    <div className="absolute top-[-2px] h-3 w-0.5 bg-brand-ink" style={{ left: `${Math.min(p.target, 100)}%` }} title="Target" />
                  </div>
                </div>
              ))}
              <div className="grid grid-cols-2 gap-2 text-xs mt-3">
                <div className="rounded bg-brand-cream p-2"><div className="font-bold text-base">{mix.promoDays}</div>hari promo</div>
                <div className={`rounded p-2 ${mix.reactiveFlag ? "bg-red-50 text-brand" : "bg-brand-cream"}`}><div className="font-bold text-base">{mix.reactivePct}%</div>slot reaktif (target {mix.reactiveTarget}%)</div>
                <div className="rounded bg-brand-cream p-2 col-span-2">
                  {Object.entries(mix.formats).map(([k, v]) => <span key={k} className="mr-2">{k} <b>{v}</b></span>)}
                  <span>· hari Story <b>{mix.storyDays}</b></span>
                </div>
              </div>
            </div>
            <div className="card p-3">
              <div className="font-bold text-sm mb-2">Peringatan ({warns.length})</div>
              {!warns.length && <div className="text-xs text-gray-500">Tidak ada peringatan.</div>}
              <div className="space-y-1 max-h-[420px] overflow-y-auto">
                {warns.map((w, i) => (
                  <button key={i} onClick={() => setOpen({ id: w.itemId })} className="block w-full text-left text-xs rounded border border-brand-line p-2 hover:border-brand">
                    <b>{fmtDate(w.date)}</b> · {w.message}
                  </button>
                ))}
              </div>
            </div>
          </aside>
        )}
      </div>

      {open && <ContentDrawer {...open} onClose={() => setOpen(null)} onOpenRequest={(id) => { setOpen(null); setReqOpen(id); }} />}
      {reqOpen && <RequestDrawer id={reqOpen} onClose={(n) => setReqOpen(n || null)} />}
    </div>
  );
}

function ListView({ byDate, warnByItem, setOpen, isSocmed, month }) {
  const dates = Object.keys(byDate).sort();
  if (!dates.length) return <Empty>Belum ada konten di {monthLabel(month)}.{isSocmed ? " Klik + Konten atau Impor CSV." : ""}</Empty>;
  return (
    <div className="space-y-3">
      {dates.map((d) => (
        <div key={d} className="card">
          <div className="px-3 py-2 border-b border-brand-line font-bold text-sm bg-brand-cream/60 rounded-t-xl flex justify-between">
            <span>{fmtDate(d, true)}</span>
            {isSocmed && <button className="text-brand text-xs" onClick={() => setOpen({ date: d })}>+ tambah</button>}
          </div>
          <div className="divide-y divide-brand-line">
            {byDate[d].map((i) => (
              <button key={i.id} onClick={() => setOpen({ id: i.id })} className="w-full text-left px-3 py-2 hover:bg-brand-tint/30">
                <div className="flex flex-wrap items-center gap-1 text-xs">
                  <span className={`chip border ${CONTENT_COLORS[i.status]}`}>{i.status}</span>
                  <b>{PLATFORM_ICON[i.platform]} {i.format}</b>{i.time && <span>{i.time}</span>}
                  <span className="chip bg-gray-100">{i.pillar}</span>
                  {i.goal && <span className="chip bg-gray-100">{i.goal}</span>}
                  {i.trackingCode && <span className="chip bg-brand-tint text-brand-deep">{i.trackingCode}</span>}
                  {i.assetReady && <span className="chip bg-brand-yellow">Aset siap</span>}
                  {i.request && <span className="chip bg-blue-50 text-blue-800">{i.request.code} · {i.request.status}</span>}
                </div>
                <div className="text-sm font-semibold mt-1">{i.hook || i.idea || "–"}</div>
                {i.idea && i.hook && <div className="text-xs text-gray-600">{i.idea}</div>}
                {(warnByItem[i.id] || []).map((w, k) => <div key={k} className="text-[11px] text-brand">⚠ {w.message}</div>)}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
