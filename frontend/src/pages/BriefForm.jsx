import { useMemo, useState } from "react";
import { post, put } from "../api";
import { Drawer, Field, Select, useApp, useRunner } from "../components/ui";

const PRESET_1SHOOT = [
  { format: "Reels hook A", ratio: "9:16", size: "1080x1920", duration: "7-15 detik", platform: "IG" },
  { format: "Reels hook B", ratio: "9:16", size: "1080x1920", duration: "7-15 detik", platform: "IG" },
  { format: "TikTok (tanpa watermark)", ratio: "9:16", size: "1080x1920", duration: "7-15 detik", platform: "TT" },
  { format: "Story x4", ratio: "9:16", size: "1080x1920", duration: "", platform: "IG" },
  { format: "Feed foto hero", ratio: "4:5", size: "1080x1350", duration: "", platform: "IG" },
  { format: "Foto marketplace", ratio: "1:1", size: "1080x1080", duration: "", platform: "MKT" },
  { format: "Cutout PNG", ratio: "bebas", size: "", duration: "", platform: "PRINT" },
];

const EMPTY = {
  title: "", source: "Socmed", funnelGoal: "", assetType: "", outputs: [], keyMessage: "", hook: "", heroProduct: "",
  supportingSkus: "", talent: "", props: "", location: "", shootDate: "", shootTime: "", mood: "", referenceLinks: [],
  mandatoryText: "", mandatoryTextSource: "", cta: "", trackingCode: "", isPromo: false, isBudgeted: false, budget: 0,
  gateStatus: "NA", gateRef: "", priority: "Normal", picShootId: "", picDesignId: "", picEditId: "", reviewerId: "",
  requestedDeadline: "", notes: "",
};

const Sec = ({ n, t, children }) => (
  <section className="mb-5">
    <h3 className="text-sm font-bold text-brand-deep mb-2">{n}. {t}</h3>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{children}</div>
  </section>
);

function addWorkdays(start, n, settings) {
  const d = new Date(start);
  let added = 0;
  const ok = (x) => {
    const iso = x.getDay() === 0 ? 7 : x.getDay();
    const s = `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
    return settings.workDays.includes(iso) && !settings.holidays.includes(s);
  };
  while (added < n) { d.setDate(d.getDate() + 1); if (ok(d)) added++; }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function BriefForm({ open, onClose, initial, onSaved }) {
  const { meta, members, settings, isApprover, today } = useApp();
  const run = useRunner();
  const editing = !!initial?.id;
  const [f, setF] = useState(() => ({ ...EMPTY, ...(initial || {}), referenceLinks: initial?.referenceLinks || [] }));
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v?.target ? (v.target.type === "checkbox" ? v.target.checked : v.target.value) : v }));
  const creatives = members.filter((m) => m.active !== false && ["creative", "creative_lead"].includes(m.role));
  const reviewers = members.filter((m) => m.active !== false && ["creative_lead", "approver"].includes(m.role));
  const opt = (list) => list.map((m) => ({ value: m.id, label: `${m.name} (${m.jobFunction})` }));

  const missing = useMemo(() => {
    const m = [];
    if (!f.title.trim()) m.push("Judul");
    if (!f.funnelGoal) m.push("Tujuan funnel");
    if (!f.assetType) m.push("Tipe aset");
    if (!f.outputs.length) m.push("Output");
    if (!f.keyMessage.trim()) m.push("Key message");
    if (!f.cta.trim()) m.push("CTA");
    if (!(f.picShootId || f.picDesignId || f.picEditId)) m.push("PIC");
    if (f.isPromo && !f.mandatoryText.trim()) m.push("Teks wajib");
    if (f.isPromo && !f.mandatoryTextSource.trim()) m.push("Sumber angka");
    return m;
  }, [f]);
  const total = 9;
  const pct = Math.round(((total - Math.min(missing.length, total)) / total) * 100);

  const sla = settings?.slaTable?.[f.assetType];
  const slaPreview = sla ? (() => {
    const base = sla.basis === "shoot" && f.shootDate ? f.shootDate : today;
    return { draft: addWorkdays(base, sla.draftDays, settings), final: addWorkdays(base, sla.finalDays, settings), note: sla.note };
  })() : null;

  const setOut = (i, k, v) => setF((x) => ({ ...x, outputs: x.outputs.map((o, j) => (j === i ? { ...o, [k]: v } : o)) }));

  async function save() {
    const body = { ...f };
    ["picShootId", "picDesignId", "picEditId", "reviewerId", "shootDate", "requestedDeadline", "funnelGoal", "assetType"].forEach((k) => { if (!body[k]) body[k] = null; });
    body.budget = Number(body.budget) || 0;
    body.referenceLinks = (typeof body.referenceLinks === "string" ? body.referenceLinks.split("\n") : body.referenceLinks).map((s) => s.trim()).filter(Boolean);
    if (!isApprover) { delete body.gateStatus; if (!editing && (f.isPromo || f.isBudgeted)) body.gateStatus = "PENDING"; }
    if (editing) {
      ["id", "code", "status", "qc", "approval", "log", "revisionNotes", "contentItems", "children", "parent", "requesterId", "createdAt", "updatedAt",
        "revisionRound", "deadlineDraft", "deadlineFinal", "overdue", "atRisk", "draftLate", "approvalRequired", "qcComplete", "suggestedFileNames",
        "fileNameWarnings", "outputsDone", "missing", "contentItemIds", "parentRequestId", "rejectReason", "holdReason", "closedNote", "briefOkAt",
        "finalAt", "handoverAt", "approvalRequestedAt", "finalFileNames", "driveFolderLink"].forEach((k) => delete body[k]);
      if (!isApprover) delete body.gateRef;
    }
    const r = await run((confirm) => editing ? put(`/api/requests/${initial.id}${confirm ? "?confirm=true" : ""}`, body) : post("/api/requests", body),
      editing ? "Brief disimpan" : "Brief terkirim");
    if (r) { onSaved?.(r); onClose(); }
  }

  return (
    <Drawer open={open} onClose={onClose} wide title={editing ? `Ubah brief ${initial.code}` : "Brief baru"}
      footer={
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="h-2 rounded bg-gray-100 overflow-hidden"><div className="h-2 bg-brand" style={{ width: `${pct}%` }} /></div>
            <div className="text-[11px] text-gray-600 mt-1">{missing.length ? "Belum lengkap: " + missing.join(", ") : "Brief lengkap ✓"}</div>
          </div>
          <button className="btn-ghost" onClick={onClose}>Batal</button>
          <button className="btn-primary" onClick={save}>{editing ? "Simpan" : "Kirim brief"}</button>
        </div>
      }>
      <Sec n={1} t="Tujuan & KPI">
        <Field label="Judul aset" className="sm:col-span-2"><input className="inp" value={f.title} onChange={set("title")} placeholder="mis. ASMR Mozza tarik bumbu" /></Field>
        <Field label="Sumber permintaan"><Select value={f.source} onChange={set("source")} options={meta.sources} /></Field>
        <Field label="Tujuan funnel"><Select value={f.funnelGoal} onChange={set("funnelGoal")} options={meta.funnelGoals} placeholder="Pilih…" /></Field>
        <Field label="Tipe aset"><Select value={f.assetType} onChange={set("assetType")} options={meta.assetTypes} placeholder="Pilih…" /></Field>
        <Field label="Prioritas"><Select value={f.priority} onChange={set("priority")} options={meta.priorities} /></Field>
      </Sec>

      <section className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-brand-deep">2. Output & turunan</h3>
          <div className="flex gap-1">
            <button className="btn-ghost btn-sm" onClick={() => setF((x) => ({ ...x, outputs: [...x.outputs, ...PRESET_1SHOOT] }))}>+ Paket 1 shoot</button>
            <button className="btn-ghost btn-sm" onClick={() => setF((x) => ({ ...x, outputs: [...x.outputs, { format: "", ratio: "9:16", size: "1080x1920", duration: "", platform: "IG" }] }))}>+ Output</button>
          </div>
        </div>
        {f.outputs.length === 0 && <div className="text-xs text-gray-500">Belum ada output. Tambahkan minimal satu.</div>}
        <div className="space-y-2">
          {f.outputs.map((o, i) => (
            <div key={i} className="grid grid-cols-12 gap-1 items-center">
              <input className="inp col-span-12 sm:col-span-4" placeholder="Format" value={o.format} onChange={(e) => setOut(i, "format", e.target.value)} />
              <input className="inp col-span-3 sm:col-span-2" placeholder="Rasio" value={o.ratio} onChange={(e) => setOut(i, "ratio", e.target.value)} />
              <input className="inp col-span-4 sm:col-span-2" placeholder="Durasi" value={o.duration} onChange={(e) => setOut(i, "duration", e.target.value)} />
              <select className="inp col-span-3 sm:col-span-2" value={o.platform} onChange={(e) => setOut(i, "platform", e.target.value)}>
                {["IG", "TT", "FB", "MKT", "PRINT", "DECK"].map((p) => <option key={p}>{p}</option>)}
              </select>
              <button className="btn-ghost btn-sm col-span-2 sm:col-span-2" onClick={() => setF((x) => ({ ...x, outputs: x.outputs.filter((_, j) => j !== i) }))}>Hapus</button>
            </div>
          ))}
        </div>
      </section>

      <Sec n={3} t="Pesan">
        <Field label={`Key message (${f.keyMessage.length}/140)`} className="sm:col-span-2"><input className="inp" maxLength={140} value={f.keyMessage} onChange={set("keyMessage")} /></Field>
        <Field label="Hook (teks on-screen + visual pembuka)" className="sm:col-span-2"><textarea className="inp" rows={2} value={f.hook} onChange={set("hook")} /></Field>
        <Field label="CTA"><input className="inp" value={f.cta} onChange={set("cta")} /></Field>
        <Field label="Kode tracking"><input className="inp" list="tracking-codes" value={f.trackingCode} onChange={set("trackingCode")} /></Field>
        <datalist id="tracking-codes">{(settings?.trackingCodes || []).map((t) => <option key={t} value={t} />)}</datalist>
      </Sec>

      <Sec n={4} t="Produk & talent">
        <Field label="Produk hero"><input className="inp" value={f.heroProduct} onChange={set("heroProduct")} /></Field>
        <Field label="SKU pendukung"><input className="inp" value={f.supportingSkus} onChange={set("supportingSkus")} /></Field>
        <Field label="Talent"><input className="inp" value={f.talent} onChange={set("talent")} placeholder="crew, KOL, maskot, customer (dengan izin)" /></Field>
        <Field label="Props"><input className="inp" value={f.props} onChange={set("props")} /></Field>
      </Sec>

      <Sec n={5} t="Lokasi & jadwal">
        <Field label="Lokasi"><Select value={f.location} onChange={set("location")} options={settings?.locations || []} placeholder="Pilih…" /></Field>
        <Field label="Tanggal shoot"><input type="date" className="inp" value={f.shootDate || ""} onChange={set("shootDate")} /></Field>
        <Field label="Jam shoot" hint="Jam lapar 11.00–13.00 / 17.00–20.00 untuk konten live kios"><input type="time" className="inp" value={f.shootTime} onChange={set("shootTime")} /></Field>
        <Field label="Deadline yang diminta (opsional)"><input type="date" className="inp" value={f.requestedDeadline || ""} onChange={set("requestedDeadline")} /></Field>
        <Field label="Mood" className="sm:col-span-2"><input className="inp" value={f.mood} onChange={set("mood")} /></Field>
      </Sec>

      <Sec n={6} t="Teks wajib & sumber angka">
        <Field label="Teks wajib (harga, periode, kuota, outlet, syarat)" className="sm:col-span-2"><textarea className="inp" rows={2} value={f.mandatoryText} onChange={set("mandatoryText")} /></Field>
        <Field label="Sumber angka" hint="Kode Gate (mis. N12) atau nama dokumen" className="sm:col-span-2"><input className="inp" value={f.mandatoryTextSource} onChange={set("mandatoryTextSource")} /></Field>
      </Sec>

      <Sec n={7} t="Promo & Gate">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.isPromo} onChange={set("isPromo")} /> Aset promo</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.isBudgeted} onChange={set("isBudgeted")} /> Berbudget (ads / KOL / berbayar)</label>
        {f.isBudgeted && <Field label="Budget (Rp)"><input type="number" className="inp" value={f.budget} onChange={set("budget")} /></Field>}
        <Field label="Status Gate" hint={isApprover ? "" : "Hanya Approver yang bisa mengubah"}>
          <Select value={f.gateStatus} onChange={set("gateStatus")} options={meta.gateStatuses} disabled={!isApprover} />
        </Field>
        <Field label="Kode Gate (Alignment Board)"><input className="inp" value={f.gateRef} onChange={set("gateRef")} disabled={!isApprover && editing} placeholder="mis. N12" /></Field>
        {(f.isPromo || f.isBudgeted) && (f.gateStatus === "NA" || f.gateStatus === "PENDING" || f.gateStatus === "HOLD") &&
          <div className="sm:col-span-2 text-xs rounded-lg bg-red-50 text-red-700 p-2">Request akan berstatus <b>Ditahan Gate</b> sampai Approver mengubah status menjadi GO/GWC.</div>}
      </Sec>

      <Sec n={8} t="Referensi">
        <Field label="Link referensi (satu per baris)" className="sm:col-span-2">
          <textarea className="inp" rows={3} value={Array.isArray(f.referenceLinks) ? f.referenceLinks.join("\n") : f.referenceLinks} onChange={(e) => set("referenceLinks")(e.target.value.split("\n"))} />
        </Field>
        <Field label="Catatan" className="sm:col-span-2"><textarea className="inp" rows={2} value={f.notes} onChange={set("notes")} /></Field>
      </Sec>

      <Sec n={9} t="Deadline & PIC">
        <Field label="PIC shoot"><Select value={f.picShootId} onChange={set("picShootId")} options={opt(creatives)} placeholder="–" /></Field>
        <Field label="PIC design"><Select value={f.picDesignId} onChange={set("picDesignId")} options={opt(creatives)} placeholder="–" /></Field>
        <Field label="PIC edit"><Select value={f.picEditId} onChange={set("picEditId")} options={opt(creatives)} placeholder="–" /></Field>
        <Field label="Reviewer"><Select value={f.reviewerId} onChange={set("reviewerId")} options={opt(reviewers)} placeholder="Default: Creative Lead" /></Field>
        <div className="sm:col-span-2 rounded-lg bg-brand-cream p-3 text-sm">
          {slaPreview ? <>SLA {f.assetType}: draft <b>{slaPreview.draft}</b> · final <b>{slaPreview.final}</b>
            <span className="text-xs text-gray-600"> (dihitung saat Brief OK{sla.basis === "shoot" ? ", dari tanggal shoot bila diisi" : ""}){slaPreview.note ? ` · ${slaPreview.note}` : ""}</span></> : "Pilih tipe aset untuk melihat SLA."}
        </div>
      </Sec>
    </Drawer>
  );
}
