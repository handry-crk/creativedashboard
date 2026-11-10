import { useEffect, useState } from "react";
import { del, get, post, put } from "../api";
import { Drawer, Field, GateBadge, Select, StatusPill, useApp, useRunner } from "../components/ui";
import { fmtDate, fmtTime } from "../util";

const BLANK = { date: "", time: "", platform: "IG+TT", format: "Reels", pillar: "Product Craving", goal: "Reach", theme: "", idea: "", hook: "", cta: "",
  trackingCode: "", isPromo: false, gateStatus: "NA", gateRef: "", isReactiveSlot: false, picSocmedId: "", status: "Idea", captionFinal: "", postedUrl: "", notes: "" };

export default function ContentDrawer({ id, date, onClose, onOpenRequest }) {
  const { meta, members, isSocmed, settings, name, me, tick } = useApp();
  const run = useRunner();
  const [item, setItem] = useState(null);
  const [f, setF] = useState(id ? null : { ...BLANK, date, picSocmedId: me?.role === "socmed" ? me.id : "" });
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!id) return;
    get(`/api/content/${id}`).then((x) => {
      setItem(x);
      if (!dirty) setF({ ...BLANK, ...Object.fromEntries(Object.entries(x).map(([k, v]) => [k, v ?? ""])) });
    }).catch((e) => alert(e.message));
  }, [id, tick]); // eslint-disable-line

  if (!f) return <Drawer open onClose={onClose} title="Memuat…"><div /></Drawer>;
  const set = (k) => (v) => { setDirty(true); setF((x) => ({ ...x, [k]: v?.target ? (v.target.type === "checkbox" ? v.target.checked : v.target.value) : v })); };
  const ro = !isSocmed;
  const socmed = members.filter((m) => m.role === "socmed" || m.role === "approver" || m.role === "creative_lead");

  async function save() {
    const body = {};
    Object.keys(BLANK).forEach((k) => { body[k] = f[k] === "" ? null : f[k]; });
    body.isPromo = !!f.isPromo; body.isReactiveSlot = !!f.isReactiveSlot;
    if (!body.captionFinal) body.captionFinal = "";
    const r = id ? await run(() => put(`/api/content/${id}`, body), "Konten disimpan") : await run(() => post("/api/content", body), "Konten ditambahkan");
    if (r) { setDirty(false); onClose(); }
  }

  async function createBrief() {
    let extra = {};
    if (f.isPromo) {
      const t = window.prompt("Teks wajib promo (harga, periode, kuota, outlet, syarat):");
      if (!t) return;
      const s = window.prompt("Sumber angka (kode Gate / dokumen):");
      if (!s) return;
      extra = { mandatoryText: t, mandatoryTextSource: s };
    }
    const r = await run(() => post(`/api/content/${id}/create-brief`, extra), "Brief dibuat");
    if (r) onOpenRequest(r.id);
  }

  const gateOk = ["GO", "GWC"].includes(f.gateStatus);
  const statusOpts = meta.contentStatuses.filter((s) => !(f.isPromo && !gateOk) || ["Idea", "Batal"].includes(s));

  return (
    <Drawer open onClose={onClose} title={id ? `${fmtDate(f.date, true)} · ${f.platform} ${f.format}` : "Konten baru"}
      footer={!ro && (
        <div className="flex flex-wrap gap-2">
          {id && <button className="btn-ghost text-brand" onClick={async () => { if (window.confirm("Hapus konten ini?") && await run(() => del(`/api/content/${id}`), "Konten dihapus")) onClose(); }}>Hapus</button>}
          <div className="ml-auto flex gap-2"><button className="btn-ghost" onClick={onClose}>Tutup</button><button className="btn-primary" onClick={save}>Simpan</button></div>
        </div>
      )}>
      {item?.request ? (
        <button onClick={() => onOpenRequest(item.request.id)} className="w-full text-left card p-3 mb-4 hover:border-brand">
          <div className="text-xs text-gray-500">Request produksi</div>
          <div className="flex items-center gap-2"><span className="font-mono text-sm">{item.request.code}</span><StatusPill s={item.request.status} />
            {item.assetReady && <span className="chip bg-brand-yellow">Aset siap</span>}</div>
          <div className="text-sm">{item.request.title} · deadline final {fmtDate(item.request.deadlineFinal)}</div>
        </button>
      ) : id && !ro && (
        <div className="card p-3 mb-4 flex items-center justify-between gap-2">
          <div className="text-sm text-gray-600">Belum ada request produksi.</div>
          <button className="btn-primary btn-sm" onClick={createBrief}>Buat brief dari konten</button>
        </div>
      )}
      {f.isPromo && !gateOk && <div className="mb-3 rounded-lg bg-red-50 text-red-700 text-xs p-2">Promo menunggu Gate — status hanya bisa Idea sampai GO/GWC. <GateBadge gate={f.gateStatus} /></div>}

      <fieldset disabled={ro} className="grid grid-cols-2 gap-3">
        <Field label="Tanggal"><input type="date" className="inp" value={f.date} onChange={set("date")} /></Field>
        <Field label="Jam" hint={`Jam posting: ${(settings?.postingWindows || []).join(", ")}`}><input type="time" className="inp" value={f.time} onChange={set("time")} /></Field>
        <Field label="Platform"><Select value={f.platform} onChange={set("platform")} options={meta.platforms} /></Field>
        <Field label="Format"><Select value={f.format} onChange={set("format")} options={meta.formats} /></Field>
        <Field label="Pillar"><Select value={f.pillar} onChange={set("pillar")} options={meta.pillars} /></Field>
        <Field label="Tujuan"><Select value={f.goal} onChange={set("goal")} options={meta.contentGoals} placeholder="–" /></Field>
        <Field label="Status"><Select value={f.status} onChange={set("status")} options={statusOpts} /></Field>
        <Field label="PIC Socmed"><Select value={f.picSocmedId} onChange={set("picSocmedId")} options={socmed.map((m) => ({ value: m.id, label: m.name }))} placeholder="–" /></Field>
        <Field label="Tema" className="col-span-2"><input className="inp" value={f.theme} onChange={set("theme")} /></Field>
        <Field label="Ide" className="col-span-2"><input className="inp" value={f.idea} onChange={set("idea")} /></Field>
        <Field label="Hook" className="col-span-2"><input className="inp" value={f.hook} onChange={set("hook")} /></Field>
        <Field label="CTA"><input className="inp" value={f.cta} onChange={set("cta")} /></Field>
        <Field label="Kode tracking"><input className="inp" list="tc" value={f.trackingCode} onChange={set("trackingCode")} /></Field>
        <datalist id="tc">{(settings?.trackingCodes || []).map((t) => <option key={t} value={t} />)}</datalist>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.isPromo} onChange={set("isPromo")} /> Konten promo</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.isReactiveSlot} onChange={set("isReactiveSlot")} /> Slot reaktif (trend/UGC)</label>
        {f.isPromo && <>
          <Field label="Status Gate"><Select value={f.gateStatus} onChange={set("gateStatus")} options={meta.gateStatuses} /></Field>
          <Field label="Kode Gate"><input className="inp" value={f.gateRef} onChange={set("gateRef")} placeholder="mis. N12" /></Field>
        </>}
        <Field label={`Caption final (${(f.captionFinal || "").length}/2.200)`} className="col-span-2">
          <textarea className="inp" rows={5} maxLength={2200} value={f.captionFinal} onChange={set("captionFinal")} />
        </Field>
        <Field label="Link postingan" className="col-span-2" hint="Wajib saat status Posted"><input className="inp" value={f.postedUrl} onChange={set("postedUrl")} placeholder="https://…" /></Field>
        <Field label="Catatan" className="col-span-2"><textarea className="inp" rows={2} value={f.notes} onChange={set("notes")} /></Field>
      </fieldset>

      {item?.log?.length > 0 && (
        <section className="mt-5">
          <h3 className="font-bold text-sm text-brand-deep mb-2">Riwayat</h3>
          <div className="text-xs space-y-1">
            {item.log.map((l, i) => <div key={i}><span className="text-gray-500">{fmtTime(l.at)}</span> · <b>{l.byId === "system" ? "Sistem" : name(l.byId)}</b> {l.action} {l.from ? `${l.from} → ${l.to}` : ""} {l.note && `(${l.note})`}</div>)}
          </div>
        </section>
      )}
    </Drawer>
  );
}
