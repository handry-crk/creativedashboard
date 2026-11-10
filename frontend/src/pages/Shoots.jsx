import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Drawer, Empty, Field, Select, StatusPill, useApp, useRunner } from "../components/ui";
import { fmtDate } from "../util";

const SHOOT_TYPES = ["REEL", "TIKTOK", "STORY", "FEED", "CAROUSEL", "ADS", "EVENTDOC", "MKT"];

export default function Shoots({ reqs, open }) {
  const { tick, canEdit, name, members, settings } = useApp();
  const run = useRunner();
  const [list, setList] = useState([]);
  const [edit, setEdit] = useState(null);
  useEffect(() => { get("/api/shoots").then(setList).catch(() => {}); }, [tick]);

  const vgs = members.filter((m) => ["creative", "creative_lead"].includes(m.role));
  const candidates = reqs.filter((r) => SHOOT_TYPES.includes(r.assetType) && ["Brief Masuk", "Brief OK", "Shoot"].includes(r.status));

  async function save() {
    const body = { ...edit };
    delete body.requests;
    const ok = edit.id ? await run(() => put(`/api/shoots/${edit.id}`, body), "Sesi shoot disimpan") : await run(() => post("/api/shoots", body), "Sesi shoot dibuat");
    if (ok) setEdit(null);
  }

  const upcoming = list.filter((s) => s.status !== "Selesai" && s.status !== "Batal");
  const done = list.filter((s) => s.status === "Selesai" || s.status === "Batal");

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <div className="text-sm text-gray-600">{upcoming.length} sesi direncanakan</div>
        {canEdit && <button className="btn-primary" onClick={() => setEdit({ date: "", time: "", location: settings?.locations?.[0] || "", videographerId: "", requestIds: [], equipmentChecklist: {}, footageLog: "" })}>+ Sesi shoot</button>}
      </div>
      {!list.length && <Empty>Belum ada jadwal shoot.</Empty>}
      <div className="grid md:grid-cols-2 gap-3">
        {[...upcoming, ...done].map((s) => {
          const eq = settings?.equipmentChecklist || [];
          const ready = eq.filter((x) => s.equipmentChecklist?.[x]).length;
          return (
            <div key={s.id} className={`card p-3 ${s.status === "Selesai" ? "opacity-70" : ""}`}>
              <div className="flex items-center justify-between">
                <div className="font-bold">{fmtDate(s.date, true)} {s.time}</div>
                <span className={`chip ${s.status === "Selesai" ? "bg-green-100 text-green-800" : s.status === "Batal" ? "bg-gray-100" : "bg-purple-100 text-purple-800"}`}>{s.status}</span>
              </div>
              <div className="text-sm text-gray-600">{s.location} · Videographer: <b>{name(s.videographerId)}</b> · Alat {ready}/{eq.length}</div>
              <div className="mt-2 space-y-1">
                {s.requests.map((r) => <button key={r.id} onClick={() => open(r.id)} className="flex items-center gap-2 text-sm hover:text-brand"><span className="font-mono text-xs">{r.code}</span>{r.title}<StatusPill s={r.status} /></button>)}
              </div>
              {s.footageLog && <div className="mt-2 text-xs whitespace-pre-wrap bg-gray-50 rounded p-2">{s.footageLog}</div>}
              {canEdit && s.status === "Rencana" && (
                <div className="flex gap-2 mt-3">
                  <button className="btn-ghost btn-sm" onClick={() => setEdit({ ...s })}>Ubah / checklist</button>
                  <button className="btn-primary btn-sm" onClick={() => window.confirm("Tandai shoot selesai? Request berstatus Shoot akan pindah ke Produksi.") && run(() => post(`/api/shoots/${s.id}/complete`), "Shoot selesai")}>Tandai selesai</button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {edit && (
        <Drawer open onClose={() => setEdit(null)} title={edit.id ? "Ubah sesi shoot" : "Sesi shoot baru"}
          footer={<div className="flex justify-end gap-2"><button className="btn-ghost" onClick={() => setEdit(null)}>Batal</button><button className="btn-primary" onClick={save}>Simpan</button></div>}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tanggal"><input type="date" className="inp" value={edit.date} onChange={(e) => setEdit({ ...edit, date: e.target.value })} /></Field>
            <Field label="Jam"><input type="time" className="inp" value={edit.time} onChange={(e) => setEdit({ ...edit, time: e.target.value })} /></Field>
            <Field label="Lokasi"><Select value={edit.location} onChange={(v) => setEdit({ ...edit, location: v })} options={settings?.locations || []} /></Field>
            <Field label="Videographer"><Select value={edit.videographerId} onChange={(v) => setEdit({ ...edit, videographerId: v })} options={vgs.map((m) => ({ value: m.id, label: m.name }))} placeholder="–" /></Field>
          </div>
          <h4 className="lbl mt-4">Request yang di-shoot</h4>
          {candidates.length === 0 && <div className="text-xs text-gray-500">Tidak ada request tipe video/foto yang menunggu shoot.</div>}
          {[...candidates, ...reqs.filter((r) => edit.requestIds.includes(r.id) && !candidates.includes(r))].map((r) => (
            <label key={r.id} className="flex items-center gap-2 text-sm py-1">
              <input type="checkbox" checked={edit.requestIds.includes(r.id)} onChange={(e) => setEdit({ ...edit, requestIds: e.target.checked ? [...edit.requestIds, r.id] : edit.requestIds.filter((x) => x !== r.id) })} />
              <span className="font-mono text-xs">{r.code}</span> {r.title} <StatusPill s={r.status} />
            </label>
          ))}
          <h4 className="lbl mt-4">Checklist alat & set</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
            {(settings?.equipmentChecklist || []).map((x) => (
              <label key={x} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!edit.equipmentChecklist?.[x]} onChange={(e) => setEdit({ ...edit, equipmentChecklist: { ...edit.equipmentChecklist, [x]: e.target.checked } })} />{x}
              </label>
            ))}
          </div>
          <Field label="Log footage (kartu/folder, take, catatan)" className="mt-4">
            <textarea className="inp" rows={4} value={edit.footageLog} onChange={(e) => setEdit({ ...edit, footageLog: e.target.value })} />
          </Field>
        </Drawer>
      )}
    </div>
  );
}
