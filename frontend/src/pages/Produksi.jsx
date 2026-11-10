import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api";
import { Avatar, Empty, GateBadge, Select, StatusPill, Tile, useApp, useRunner } from "../components/ui";
import { fmtDate, parseD } from "../util";
import BriefForm from "./BriefForm";
import RequestDrawer from "./RequestDrawer";
import Shoots from "./Shoots";

const BOARD = ["Brief Masuk", "Ditahan Gate", "Brief OK", "Shoot", "Produksi", "Review", "Revisi", "Approval", "Final", "Diserahkan"];
const TILE_FILTERS = {
  aktif: (r) => ["Brief OK", "Shoot", "Produksi", "Review", "Revisi", "Approval"].includes(r.status),
  overdue: (r) => r.overdue,
  atRisk: (r) => r.atRisk,
  review: (r) => r.status === "Review",
  approval: (r) => r.status === "Approval",
  ditahanGate: (r) => r.status === "Ditahan Gate",
  selesai: (r) => r.status === "Diserahkan",
};

function urlReq() { return new URLSearchParams(location.search).get("req"); }
function setUrlReq(id) {
  const u = new URL(location.href);
  id ? u.searchParams.set("req", id) : u.searchParams.delete("req");
  history.replaceState(null, "", u);
}

export default function Produksi() {
  const { tick, me, members, name, canEdit, meta, settings } = useApp();
  const [reqs, setReqs] = useState([]);
  const [sum, setSum] = useState({});
  const [view, setView] = useState("board");
  const [tile, setTile] = useState(null);
  const [f, setF] = useState({ q: "", type: "", pic: "", source: "", location: "", mine: false, closed: false });
  const [openId, setOpenId] = useState(urlReq());
  const [newBrief, setNewBrief] = useState(false);

  useEffect(() => {
    Promise.all([get("/api/requests"), get("/api/requests/summary")]).then(([r, s]) => { setReqs(r); setSum(s); }).catch(() => {});
  }, [tick]);

  const open = (id) => { setOpenId(id); setUrlReq(id); };
  const close = (nextId) => { setOpenId(nextId || null); setUrlReq(nextId || null); };

  const filtered = useMemo(() => reqs.filter((r) => {
    if (!f.closed && ["Ditolak", "Batal"].includes(r.status)) return false;
    if (tile && !TILE_FILTERS[tile](r)) return false;
    if (f.type && r.assetType !== f.type) return false;
    if (f.source && r.source !== f.source) return false;
    if (f.location && r.location !== f.location) return false;
    if (f.pic && ![r.picShootId, r.picDesignId, r.picEditId, r.reviewerId].includes(f.pic)) return false;
    if (f.mine && me && ![r.picShootId, r.picDesignId, r.picEditId, r.reviewerId, r.requesterId].includes(me.id)) return false;
    if (f.q && !`${r.code} ${r.title}`.toLowerCase().includes(f.q.toLowerCase())) return false;
    return true;
  }), [reqs, tile, f, me]);

  const creatives = members.filter((m) => ["creative", "creative_lead"].includes(m.role));
  const tiles = [
    ["aktif", "Aktif", sum.aktif], ["overdue", "Overdue", sum.overdue, "red"], ["atRisk", "At risk", sum.atRisk, "amber"],
    ["review", "Menunggu review", sum.review], ["approval", "Menunggu approval", sum.approval], ["ditahanGate", "Ditahan Gate", sum.ditahanGate, "red"],
    ["selesai", "Selesai minggu ini", sum.selesaiMingguIni, "green"], [null, "On-time % 30 hari", sum.onTimePct != null ? `${sum.onTimePct}%` : "–", "green"],
    [null, "Rata-rata ronde revisi", sum.avgRevisi ?? "–"],
  ];

  return (
    <div>
      <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2 mb-4">
        {tiles.map(([k, l, v, tone]) => (
          <Tile key={l} label={l} value={v} tone={tone} active={k && tile === k} onClick={() => k && setTile(tile === k ? null : k)} />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="flex rounded-lg border border-brand-line overflow-hidden text-sm">
          {[["board", "Board"], ["list", "Daftar"], ["load", "Beban Kerja"], ["shoot", "Jadwal Shoot"]].map(([k, l]) => (
            <button key={k} onClick={() => setView(k)} className={`px-3 py-2 font-semibold ${view === k ? "bg-brand text-white" : "bg-white"}`}>{l}</button>
          ))}
        </div>
        {canEdit && <button className="btn-primary ml-auto" onClick={() => setNewBrief(true)}>+ Brief baru</button>}
      </div>

      {(view === "board" || view === "list") && (
        <div className="flex flex-wrap gap-2 mb-3 text-sm">
          <input className="inp !w-44" placeholder="Cari kode/judul" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
          <Select className="!w-36" value={f.type} onChange={(v) => setF({ ...f, type: v || "" })} options={meta.assetTypes} placeholder="Semua tipe" />
          <Select className="!w-40" value={f.pic} onChange={(v) => setF({ ...f, pic: v || "" })} options={creatives.map((m) => ({ value: m.id, label: m.name }))} placeholder="Semua PIC" />
          <Select className="!w-40" value={f.source} onChange={(v) => setF({ ...f, source: v || "" })} options={meta.sources} placeholder="Semua sumber" />
          <Select className="!w-40" value={f.location} onChange={(v) => setF({ ...f, location: v || "" })} options={settings?.locations || []} placeholder="Semua lokasi" />
          {me && <label className="flex items-center gap-1"><input type="checkbox" checked={f.mine} onChange={(e) => setF({ ...f, mine: e.target.checked })} /> Milik saya</label>}
          <label className="flex items-center gap-1"><input type="checkbox" checked={f.closed} onChange={(e) => setF({ ...f, closed: e.target.checked })} /> Tampilkan Ditolak/Batal</label>
          {tile && <button className="btn-ghost btn-sm" onClick={() => setTile(null)}>Hapus filter tile ✕</button>}
        </div>
      )}

      {view === "board" && <Board reqs={filtered} open={open} showClosed={f.closed} />}
      {view === "list" && <List reqs={filtered} open={open} name={name} />}
      {view === "load" && <Workload open={open} />}
      {view === "shoot" && <Shoots reqs={reqs} open={open} />}

      {newBrief && <BriefForm open onClose={() => setNewBrief(false)} onSaved={(r) => open(r.id)} />}
      {openId && <RequestDrawer id={openId} onClose={close} />}
    </div>
  );
}

function Card({ r, open, draggable }) {
  const { byId, today } = useApp();
  const dl = r.deadlineFinal;
  const tone = r.overdue ? "text-brand font-bold" : r.atRisk ? "text-amber-700 font-semibold" : "text-green-700";
  return (
    <div draggable={draggable} onDragStart={(e) => e.dataTransfer.setData("text/plain", r.id)} onClick={() => open(r.id)}
      className={`card p-2 cursor-pointer hover:border-brand text-sm ${r.overdue ? "border-brand" : ""}`}>
      <div className="flex items-center gap-1 text-[11px] text-gray-500">
        <span className="font-mono">{r.code}</span>
        {r.priority !== "Normal" && <span className={`chip ${r.priority === "Urgent" ? "bg-brand text-white" : "bg-amber-100 text-amber-800"}`}>{r.priority}</span>}
        <span className="ml-auto chip bg-gray-100">R{r.revisionRound}/2</span>
      </div>
      <div className="font-semibold leading-snug my-1">{r.title}</div>
      <div className="flex flex-wrap gap-1 mb-1">
        {r.assetType && <span className="chip bg-brand-tint text-brand-deep">{r.assetType}</span>}
        <span className="chip bg-gray-100">{r.source}</span>
        <GateBadge gate={r.gateStatus} />
      </div>
      <div className="flex items-center justify-between text-[11px]">
        <div className="flex -space-x-1">{[...new Set([r.picShootId, r.picDesignId, r.picEditId].filter(Boolean))].map((p) => <Avatar key={p} name={byId[p]?.name || p} />)}</div>
        <span>{r.outputsDone}/{r.outputs.length} output</span>
        {dl && <span className={tone}>{fmtDate(dl)}{r.overdue ? ` (+${(parseD(today) - parseD(dl)) / 86400000}h)` : ""}</span>}
      </div>
    </div>
  );
}

function Board({ reqs, open, showClosed }) {
  const run = useRunner();
  const { canEdit } = useApp();
  const cols = showClosed ? [...BOARD, "Ditolak", "Batal"] : BOARD;
  const [mobileCol, setMobileCol] = useState(null);

  async function drop(e, to) {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/plain");
    const r = reqs.find((x) => x.id === id);
    if (!r || r.status === to) return;
    let note = "";
    if (to === "Revisi" || to === "Ditolak" || to === "Batal") {
      note = window.prompt(to === "Revisi" ? "Catatan revisi:" : "Alasan:");
      if (note === null) return;
    }
    if (to === "Final" && r.status === "Approval") return alert("Gunakan tombol Setujui di detail request.");
    await run((confirm) => post(`/api/requests/${id}/transition`, { to, note, confirm }), `${r.code} → ${to}`);
  }

  return (
    <>
      <div className="hidden md:flex gap-2 overflow-x-auto pb-2">
        {cols.map((c) => {
          const list = reqs.filter((r) => r.status === c);
          return (
            <div key={c} className="w-64 shrink-0 rounded-xl bg-brand-cream/60 p-2" onDragOver={(e) => canEdit && e.preventDefault()} onDrop={(e) => drop(e, c)}>
              <div className="flex items-center justify-between mb-2 px-1"><StatusPill s={c} /><span className="text-xs text-gray-500">{list.length}</span></div>
              <div className="space-y-2 min-h-[60px]">{list.map((r) => <Card key={r.id} r={r} open={open} draggable={canEdit} />)}</div>
            </div>
          );
        })}
      </div>
      <div className="md:hidden space-y-3">
        {cols.map((c) => {
          const list = reqs.filter((r) => r.status === c);
          if (!list.length) return null;
          const opened = mobileCol === null ? true : mobileCol === c;
          return (
            <div key={c}>
              <button className="w-full flex items-center justify-between py-2" onClick={() => setMobileCol(mobileCol === c ? null : c)}>
                <StatusPill s={c} /><span className="text-xs text-gray-500">{list.length} {opened ? "▾" : "▸"}</span>
              </button>
              {opened && <div className="space-y-2">{list.map((r) => <Card key={r.id} r={r} open={open} />)}</div>}
            </div>
          );
        })}
        {!reqs.length && <Empty>Belum ada request.</Empty>}
      </div>
    </>
  );
}

function List({ reqs, open, name }) {
  const [sort, setSort] = useState({ k: "deadlineFinal", d: 1 });
  const rows = [...reqs].sort((a, b) => ((a[sort.k] ?? "~") > (b[sort.k] ?? "~") ? 1 : -1) * sort.d);
  const H = ({ k, children }) => <th className="th cursor-pointer" onClick={() => setSort({ k, d: sort.k === k ? -sort.d : 1 })}>{children}{sort.k === k ? (sort.d > 0 ? " ▲" : " ▼") : ""}</th>;
  function exportCsv() {
    const head = ["Kode", "Judul", "Status", "Tipe", "Sumber", "Lokasi", "PIC", "Deadline draft", "Deadline final", "Revisi", "Overdue", "Gate"];
    const lines = rows.map((r) => [r.code, r.title, r.status, r.assetType, r.source, r.location, [r.picShootId, r.picDesignId, r.picEditId].filter(Boolean).map(name).join(", "),
      r.deadlineDraft, r.deadlineFinal, r.revisionRound, r.overdue ? "ya" : "", `${r.gateStatus} ${r.gateRef || ""}`].map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(";"));
    const blob = new Blob(["﻿" + [head.join(";"), ...lines].join("\n")], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "request-produksi.csv"; a.click();
  }
  return (
    <div>
      <div className="flex justify-end mb-2"><button className="btn-ghost btn-sm" onClick={exportCsv}>Unduh CSV</button></div>
      <div className="hidden md:block overflow-x-auto card">
        <table className="w-full">
          <thead><tr><H k="code">Kode</H><H k="title">Judul</H><H k="status">Status</H><H k="assetType">Tipe</H><H k="source">Sumber</H><th className="th">PIC</th><H k="deadlineFinal">Deadline</H><H k="revisionRound">Revisi</H><th className="th">Output</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="hover:bg-brand-tint/30 cursor-pointer" onClick={() => open(r.id)}>
                <td className="td font-mono text-xs">{r.code}</td><td className="td font-semibold">{r.title}</td><td className="td"><StatusPill s={r.status} /></td>
                <td className="td">{r.assetType}</td><td className="td">{r.source}</td>
                <td className="td text-xs">{[...new Set([r.picShootId, r.picDesignId, r.picEditId].filter(Boolean))].map(name).join(", ")}</td>
                <td className={`td whitespace-nowrap ${r.overdue ? "text-brand font-bold" : r.atRisk ? "text-amber-700" : ""}`}>{fmtDate(r.deadlineFinal)}</td>
                <td className="td">{r.revisionRound}/2</td><td className="td">{r.outputsDone}/{r.outputs.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <Empty>Tidak ada request yang cocok.</Empty>}
      </div>
      <div className="md:hidden space-y-2">{rows.map((r) => <Card key={r.id} r={r} open={open} />)}{!rows.length && <Empty>Tidak ada request.</Empty>}</div>
    </div>
  );
}

function Workload({ open }) {
  const { tick } = useApp();
  const [w, setW] = useState([]);
  useEffect(() => { get("/api/workload").then(setW).catch(() => {}); }, [tick]);
  if (!w.length) return <Empty>Belum ada anggota kreatif atau tugas aktif.</Empty>;
  const ST = ["Brief OK", "Shoot", "Produksi", "Review", "Revisi"];
  const COL = { "Brief OK": "bg-blue-400", Shoot: "bg-purple-400", Produksi: "bg-amber-400", Review: "bg-cyan-500", Revisi: "bg-orange-500" };
  return (
    <div className="grid md:grid-cols-2 gap-3">
      {w.map((m) => (
        <div key={m.memberId} className={`card p-3 ${m.over ? "border-brand" : ""}`}>
          <div className="flex items-center justify-between">
            <div><div className="font-bold">{m.name}</div><div className="text-xs text-gray-500">{m.jobFunction}</div></div>
            <div className={`text-lg font-extrabold ${m.over ? "text-brand" : ""}`}>{m.active}<span className="text-sm text-gray-500">/{m.capacity}</span></div>
          </div>
          <div className="flex h-3 rounded overflow-hidden bg-gray-100 my-2">
            {ST.map((s) => m.byStatus[s] ? <div key={s} title={`${s}: ${m.byStatus[s]}`} className={COL[s]} style={{ width: `${(m.byStatus[s] / Math.max(m.capacity, m.active)) * 100}%` }} /> : null)}
          </div>
          <div className="flex flex-wrap gap-2 text-[11px] text-gray-600 mb-2">{ST.filter((s) => m.byStatus[s]).map((s) => <span key={s}><span className={`inline-block h-2 w-2 rounded-full mr-1 ${COL[s]}`} />{s} {m.byStatus[s]}</span>)}</div>
          {m.over && <div className="text-xs text-brand font-semibold mb-1">Melebihi kapasitas</div>}
          <div className="text-xs font-semibold text-gray-600">Deadline 7 hari ke depan</div>
          {m.next7.length === 0 && <div className="text-xs text-gray-400">Tidak ada.</div>}
          {m.next7.map((t) => <button key={t.id} onClick={() => open(t.id)} className="block text-left text-xs hover:text-brand"><span className="font-mono">{t.code}</span> {t.title} · <b>{fmtDate(t.deadlineFinal)}</b></button>)}
        </div>
      ))}
    </div>
  );
}
