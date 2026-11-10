import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Field, Select, useApp, useRunner } from "../components/ui";
import { fmtTime } from "../util";

const DAYS = [[1, "Sen"], [2, "Sel"], [3, "Rab"], [4, "Kam"], [5, "Jum"], [6, "Sab"], [7, "Min"]];
const lines = (a) => (a || []).join("\n");
const unlines = (s) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export default function Pengaturan() {
  const { settings, members, meta, isApprover, tick, canApproveMembers } = useApp();
  const run = useRunner();
  const [s, setS] = useState(null);
  const [month, setMonth] = useState("");
  const [emails, setEmails] = useState([]);

  useEffect(() => { if (settings && !s) setS(JSON.parse(JSON.stringify(settings))); }, [settings]); // eslint-disable-line
  useEffect(() => { get("/api/emaillog?limit=20").then(setEmails).catch(() => {}); }, [tick]);
  if (!s) return null;
  const set = (k, v) => setS((x) => ({ ...x, [k]: v }));
  const tgt = month ? s.monthOverrides?.[month] || { ...s.pillarTargets } : s.pillarTargets;
  const tgtSum = Object.values(tgt).reduce((a, b) => a + Number(b || 0), 0);

  async function save() {
    const body = { ...s };
    ["id", "appName", "_id"].forEach((k) => delete body[k]);
    const r = await run(() => put("/api/settings", body), "Pengaturan disimpan");
    if (r) setS(JSON.parse(JSON.stringify(r)));
  }

  const setTgt = (p, v) => {
    const t = { ...tgt, [p]: Number(v) };
    if (month) set("monthOverrides", { ...(s.monthOverrides || {}), [month]: t });
    else set("pillarTargets", t);
  };

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-extrabold">Pengaturan</h2>
        <button className="btn-primary" onClick={save}>Simpan pengaturan</button>
      </div>

      {canApproveMembers && <PendingMembers />}

      <section className="card p-4">
        <h3 className="font-bold mb-3">SLA produksi (hari kerja)</h3>
        <div className="overflow-x-auto">
          <table className="w-full"><thead><tr><th className="th">Tipe</th><th className="th">Draft H+</th><th className="th">Final H+</th><th className="th">Dasar</th><th className="th">Catatan</th></tr></thead>
            <tbody>{meta.assetTypes.map((t) => {
              const r = s.slaTable[t] || { draftDays: 2, finalDays: 3, basis: "request" };
              const up = (k, v) => set("slaTable", { ...s.slaTable, [t]: { ...r, [k]: v } });
              return (
                <tr key={t}><td className="td font-semibold">{t}</td>
                  <td className="td"><input type="number" min={0} className="inp !w-20" value={r.draftDays} onChange={(e) => up("draftDays", Number(e.target.value))} /></td>
                  <td className="td"><input type="number" min={0} className="inp !w-20" value={r.finalDays} onChange={(e) => up("finalDays", Number(e.target.value))} /></td>
                  <td className="td"><Select value={r.basis} onChange={(v) => up("basis", v)} options={[{ value: "shoot", label: "Tanggal shoot" }, { value: "request", label: "Tanggal Brief OK" }]} /></td>
                  <td className="td"><input className="inp" value={r.note || ""} onChange={(e) => up("note", e.target.value)} /></td></tr>
              );
            })}</tbody></table>
        </div>
      </section>

      <section className="card p-4 grid md:grid-cols-2 gap-4">
        <div>
          <h3 className="font-bold mb-2">Hari kerja</h3>
          <div className="flex flex-wrap gap-2">{DAYS.map(([d, l]) => (
            <label key={d} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={s.workDays.includes(d)} onChange={(e) => set("workDays", e.target.checked ? [...s.workDays, d].sort() : s.workDays.filter((x) => x !== d))} />{l}</label>
          ))}</div>
          <Field label="Hari libur (YYYY-MM-DD, satu per baris)" className="mt-3"><textarea className="inp" rows={4} value={lines(s.holidays)} onChange={(e) => set("holidays", unlines(e.target.value))} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3 content-start">
          <Field label="Jam posting (satu per baris)" className="col-span-2"><textarea className="inp" rows={2} value={lines(s.postingWindows)} onChange={(e) => set("postingWindows", unlines(e.target.value))} /></Field>
          <Field label="Maks. promo per hari"><input type="number" min={1} className="inp" value={s.maxPromoPerDay} onChange={(e) => set("maxPromoPerDay", Number(e.target.value))} /></Field>
          <Field label="Slot reaktif (%)"><input type="number" min={0} max={100} className="inp" value={s.reactiveSlotPct} onChange={(e) => set("reactiveSlotPct", Number(e.target.value))} /></Field>
          <Field label="Kapasitas default"><input type="number" min={1} className="inp" value={s.defaultCapacity} onChange={(e) => set("defaultCapacity", Number(e.target.value))} /></Field>
          <Field label="Pengganti Creative Lead"><Select value={s.creativeLeadFallback} onChange={(v) => set("creativeLeadFallback", v)} options={["Brand Lead", "Marketing Lead", "Brand Manager", "Marketing Manager"]} /></Field>
        </div>
      </section>

      <section className="card p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <h3 className="font-bold">Target pillar</h3>
          <input type="month" className="inp !w-44" value={month} onChange={(e) => setMonth(e.target.value)} />
          <span className="text-xs text-gray-500">{month ? "Override untuk bulan ini" : "Default (kosongkan bulan)"}</span>
          {month && s.monthOverrides?.[month] && <button className="btn-ghost btn-sm" onClick={() => { const m = { ...s.monthOverrides }; delete m[month]; set("monthOverrides", m); }}>Hapus override</button>}
          <span className={`ml-auto text-sm font-bold ${tgtSum === 100 ? "text-green-700" : "text-brand"}`}>Total {tgtSum}%</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
          {meta.pillars.map((p) => <Field key={p} label={p}><input type="number" className="inp" value={tgt[p] ?? 0} onChange={(e) => setTgt(p, e.target.value)} /></Field>)}
        </div>
      </section>

      <section className="card p-4 grid md:grid-cols-3 gap-3">
        <Field label="Lokasi (satu per baris)"><textarea className="inp" rows={5} value={lines(s.locations)} onChange={(e) => set("locations", unlines(e.target.value))} /></Field>
        <Field label="Kode tracking (satu per baris)"><textarea className="inp" rows={5} value={lines(s.trackingCodes)} onChange={(e) => set("trackingCodes", unlines(e.target.value))} /></Field>
        <Field label="Checklist alat shoot (satu per baris)"><textarea className="inp" rows={5} value={lines(s.equipmentChecklist)} onChange={(e) => set("equipmentChecklist", unlines(e.target.value))} /></Field>
      </section>

      <section className="card p-4">
        <h3 className="font-bold mb-3">Email & jadwal (WIB)</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Field label="Digest pagi"><input type="time" className="inp" value={s.digestTime} onChange={(e) => set("digestTime", e.target.value)} /></Field>
          <Field label="Approval menunggu"><input type="time" className="inp" value={s.approvalTime} onChange={(e) => set("approvalTime", e.target.value)} /></Field>
          <Field label="Pengingat deadline"><input type="time" className="inp" value={s.deadlineTime} onChange={(e) => set("deadlineTime", e.target.value)} /></Field>
          <Field label="Rekap mingguan"><div className="flex gap-1"><Select className="!w-20" value={String(s.weeklyDay)} onChange={(v) => set("weeklyDay", Number(v))} options={DAYS.map(([d, l]) => ({ value: String(d), label: l }))} /><input type="time" className="inp" value={s.weeklyTime} onChange={(e) => set("weeklyTime", e.target.value)} /></div></Field>
          <Field label="Email admin" className="col-span-2"><input className="inp" value={s.adminEmail} onChange={(e) => set("adminEmail", e.target.value)} /></Field>
          {isApprover && <Field label="PIN panel baru" className="col-span-2"><input className="inp" inputMode="numeric" value={s.newPanelPin || ""} onChange={(e) => set("newPanelPin", e.target.value)} placeholder="kosongkan bila tidak diubah" /></Field>}
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          {[["digest", "Kirim digest sekarang"], ["deadline", "Kirim pengingat deadline"], ["approval", "Kirim pengingat approval"], ["weekly", "Kirim rekap mingguan sekarang"], ["backup", "Backup sekarang"]].map(([k, l]) => (
            <button key={k} className="btn-ghost btn-sm" onClick={() => run(() => post(`/api/jobs/${k}/run`), `${l}: selesai`)}>{l}</button>
          ))}
          <button className="btn-ghost btn-sm" onClick={() => window.confirm("Tambahkan data contoh ke kalender bulan ini?") && run(() => post("/api/demo-data"), "Data contoh ditambahkan")}>Isi data contoh</button>
        </div>
        <div className="mt-4">
          <div className="lbl">Email terakhir</div>
          <div className="text-xs space-y-1 max-h-48 overflow-y-auto">
            {emails.map((e, i) => <div key={i}><span className="text-gray-500">{fmtTime(e.at)}</span> · <b>{e.subject}</b> → {e.to.length} penerima {e.delivered ? "" : <span className="text-amber-700">(belum terkirim — email belum dikonfigurasi)</span>}</div>)}
            {!emails.length && <div className="text-gray-400">Belum ada.</div>}
          </div>
        </div>
      </section>

      <Members members={members} meta={meta} />
    </div>
  );
}

function PendingMembers() {
  const { tick } = useApp();
  const run = useRunner();
  const [list, setList] = useState([]);
  useEffect(() => { get("/api/members/pending").then(setList).catch(() => {}); }, [tick]);
  return (
    <section className="card p-4 border-brand-yellow">
      <h3 className="font-bold mb-1">Persetujuan anggota</h3>
      <p className="text-xs text-gray-600 mb-3">Hanya Marketing Manager dan Brand Manager yang bisa menyetujui. Periksa nama, fungsi kerja, dan email sebelum menyetujui.</p>
      {!list.length && <div className="text-sm text-gray-500">Tidak ada pendaftaran yang menunggu.</div>}
      <div className="space-y-2">
        {list.map((m) => (
          <div key={m.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-brand-line p-3">
            <div className="flex-1 min-w-[200px]">
              <div className="font-semibold">{m.name} <span className="chip bg-gray-100">{m.jobFunction}</span></div>
              <div className="text-xs text-gray-600">{m.email} · daftar {fmtTime(m.createdAt)}</div>
            </div>
            <button className="btn-primary btn-sm" onClick={() => run(() => post(`/api/members/${m.id}/approve`), `${m.name} disetujui`)}>Setujui</button>
            <button className="btn-ghost btn-sm" onClick={() => { const n = window.prompt(`Alasan menolak ${m.name}:`); if (n !== null) run(() => post(`/api/members/${m.id}/reject`, { note: n }), `${m.name} ditolak`); }}>Tolak</button>
          </div>
        ))}
      </div>
    </section>
  );
}

function Members({ members, meta }) {
  const run = useRunner();
  return (
    <section className="card p-4">
      <h3 className="font-bold mb-3">Anggota</h3>
      <div className="grid md:grid-cols-2 gap-3">
        {members.map((m) => <MemberCard key={m.id} m={m} meta={meta} run={run} />)}
      </div>
    </section>
  );
}

function MemberCard({ m, meta, run }) {
  const { canApproveMembers } = useApp();
  const [f, setF] = useState({ name: m.name, jobFunction: m.jobFunction, email: m.email, capacity: m.capacity || 6 });
  return (
    <div className={`rounded-lg border border-brand-line p-3 ${m.active === false ? "opacity-60" : ""}`}>
      <div className="grid grid-cols-2 gap-2">
        <input className="inp" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <Select value={f.jobFunction} onChange={(v) => setF({ ...f, jobFunction: v })} options={meta.jobFunctions} disabled={!canApproveMembers} title={canApproveMembers ? "" : "Hanya Marketing/Brand Manager"} />
        <input className="inp" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <label className="flex items-center gap-2 text-xs">Kapasitas<input type="number" min={1} className="inp" value={f.capacity} onChange={(e) => setF({ ...f, capacity: Number(e.target.value) })} /></label>
      </div>
      <div className="flex flex-wrap gap-2 mt-2 text-xs items-center">
        <span className="chip bg-gray-100">{m.role}</span>
        <button className="btn-primary btn-sm" onClick={() => { const b = { ...f }; if (b.jobFunction === m.jobFunction) delete b.jobFunction; run(() => put(`/api/members/${m.id}`, b), "Anggota disimpan"); }}>Simpan</button>
        <button className="btn-ghost btn-sm" onClick={() => run(() => put(`/api/members/${m.id}`, { active: m.active === false }), m.active === false ? "Diaktifkan" : "Dinonaktifkan")}>{m.active === false ? "Aktifkan" : "Nonaktifkan"}</button>
        <button className="btn-ghost btn-sm" onClick={() => { const p = window.prompt(`PIN baru untuk ${m.name} (4–6 angka):`); if (p) run(() => post(`/api/members/${m.id}/reset-pin`, { pin: p }), "PIN direset"); }}>Reset PIN</button>
      </div>
    </div>
  );
}
