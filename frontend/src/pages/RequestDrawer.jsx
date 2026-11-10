import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Drawer, Field, GateBadge, Select, StatusPill, useApp, useRunner } from "../components/ui";
import { CONTENT_COLORS, fmtDate, fmtTime, parseD } from "../util";
import BriefForm from "./BriefForm";

function countdown(deadline, today) {
  if (!deadline) return "";
  const d = (parseD(deadline) - parseD(today)) / 86400000;
  if (d < 0) return `terlambat ${-d} hari`;
  if (d === 0) return "hari ini";
  return `${d} hari lagi`;
}

export default function RequestDrawer({ id, onClose }) {
  const app = useApp();
  const { me, isLead, isApprover, name, meta, tick, today } = app;
  const run = useRunner();
  const [r, setR] = useState(null);
  const [edit, setEdit] = useState(false);
  const [note, setNote] = useState({ text: "", timecodes: "" });
  const [gate, setGate] = useState(null);
  const [drive, setDrive] = useState(null);
  const [qcLocal, setQcLocal] = useState({});

  useEffect(() => {
    if (!id) return;
    get(`/api/requests/${id}`).then((x) => { setR(x); setQcLocal({}); }).catch((e) => app.toast(e.message, "err"));
  }, [id, tick]); // eslint-disable-line

  if (!id) return null;
  if (!r) return <Drawer open onClose={onClose} title="Memuat…"><div /></Drawer>;

  const pics = [r.picShootId, r.picDesignId, r.picEditId].filter(Boolean);
  const isPic = me && pics.includes(me.id);
  const isReq = me && me.id === r.requesterId;
  const isReviewer = me && me.id === r.reviewerId;
  const canAct = !!me;

  const tr = (to, msg, needNote) => async () => {
    let n = "";
    if (needNote) {
      n = window.prompt(needNote);
      if (n === null) return;
    }
    await run((confirm) => post(`/api/requests/${r.id}/transition`, { to, note: n, confirm }), msg || `Status → ${to}`);
  };

  const actions = [];
  const A = (label, fn, primary) => actions.push(<button key={label} className={primary ? "btn-primary" : "btn-ghost"} onClick={fn}>{label}</button>);
  if (canAct) {
    const s = r.status;
    if (s === "Brief Masuk" && isLead) { A("Terima (Brief OK)", tr("Brief OK", "Brief diterima"), true); A("Tolak", tr("Ditolak", "Brief ditolak", "Alasan penolakan:")); }
    if (s === "Brief OK" && (isPic || isLead)) { A("Mulai shoot", tr("Shoot"), true); A("Mulai produksi", tr("Produksi")); }
    if (s === "Shoot" && (isPic || isLead)) A("Shoot selesai → Produksi", tr("Produksi"), true);
    if (s === "Produksi" && (isPic || isLead)) A("Kirim ke Review", tr("Review"), true);
    if (s === "Review" && (isReviewer || isLead || isReq)) A("Minta revisi", tr("Revisi", "Revisi diminta", r.revisionRound >= 2 ? null : "Catatan revisi (boleh kosong bila sudah menambah catatan di bawah):"));
    if (s === "Review" && r.approvalRequired && (isPic || isReviewer || isLead)) A("Ajukan approval", tr("Approval"), true);
    if (s === "Review" && !r.approvalRequired && (isReviewer || isLead)) A("Tandai Final", tr("Final", "Aset Final"), true);
    if (s === "Revisi" && (isPic || isLead)) A("Kirim Review lagi", tr("Review"), true);
    if (s === "Approval" && isApprover) {
      A("Setujui", async () => { const n = window.prompt("Catatan approval (opsional):", ""); if (n === null) return; await run(() => post(`/api/requests/${r.id}/approve`, { decision: "approve", note: n }), "Disetujui"); }, true);
      A("Tolak → Revisi", async () => { const n = window.prompt("Alasan (masuk catatan revisi):"); if (!n) return; await run(() => post(`/api/requests/${r.id}/approve`, { decision: "reject", note: n }), "Dikembalikan ke Revisi"); });
    }
    if (s === "Final" && (isPic || isLead)) A("Serahkan", tr("Diserahkan", "Aset diserahkan"), true);
    if (s === "Ditolak" && (isReq || isLead)) A("Ajukan ulang", tr("Brief Masuk"));
    if (["Brief Masuk", "Ditahan Gate", "Ditolak"].includes(s) && (isReq || isLead)) A("Batalkan", tr("Batal", "Dibatalkan", "Alasan pembatalan:"));
    else if (!["Final", "Diserahkan", "Batal"].includes(s) && isLead) A("Batalkan", tr("Batal", "Dibatalkan", "Alasan pembatalan:"));
    const lockedish = ["Shoot", "Produksi", "Review", "Revisi", "Approval"].includes(s);
    if ((r.revisionRound >= 2 || lockedish) && (isPic || isReq || isLead))
      A("Buat brief baru", async () => {
        if (!window.confirm("Buat brief baru dari request ini? Request ini akan ditutup sebagai Final dengan catatan lanjutan.")) return;
        const n = await run(() => post(`/api/requests/${r.id}/clone-as-new-brief`), "Brief baru dibuat");
        if (n) onClose(n.id);
      });
  }

  const editable = canAct && (isLead || isReq || isPic) && !["Diserahkan", "Batal"].includes(r.status);
  const items = { ...(r.qc?.items || {}), ...qcLocal };
  const qcCount = meta.qc.filter((q) => items[q.key]).length;
  const rounds = [1, 2].map((n) => ({ n, notes: r.revisionNotes.filter((x) => x.round === n) })).filter((x) => x.notes.length || r.revisionRound + 1 >= x.n);

  return (
    <Drawer open onClose={() => onClose()} wide title={
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm text-gray-500">{r.code}</span><StatusPill s={r.status} />
          <GateBadge gate={r.gateStatus} gateRef={r.gateRef} />
          {r.overdue && <span className="chip bg-brand text-white">Overdue</span>}
          {r.atRisk && <span className="chip bg-amber-100 text-amber-800">At risk</span>}
          {r.draftLate && <span className="chip bg-orange-100 text-orange-800">Draft telat</span>}
          <span className="chip bg-gray-100">R{r.revisionRound}/2</span>
        </div>
        <div className="text-base">{r.title}</div>
        {r.deadlineFinal && <div className="text-xs font-normal text-gray-600">Draft {fmtDate(r.deadlineDraft)} · Final {fmtDate(r.deadlineFinal)} · <b>{countdown(r.deadlineFinal, today)}</b></div>}
      </div>
    } footer={actions.length ? <div className="flex flex-wrap gap-2">{actions}</div> : null}>

      {r.status === "Ditahan Gate" && (
        <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">
          <b>Ditahan Gate.</b> {r.holdReason}
          {isApprover && (
            <div className="mt-2 flex flex-wrap gap-2 items-end">
              <Field label="Status Gate"><Select value={gate?.gateStatus ?? r.gateStatus} onChange={(v) => setGate((g) => ({ ...g, gateStatus: v }))} options={meta.gateStatuses} /></Field>
              <Field label="Kode Gate"><input className="inp" value={gate?.gateRef ?? r.gateRef} onChange={(e) => setGate((g) => ({ ...g, gateRef: e.target.value }))} /></Field>
              <button className="btn-primary" onClick={() => run(() => put(`/api/requests/${r.id}`, { gateStatus: gate?.gateStatus ?? r.gateStatus, gateRef: gate?.gateRef ?? r.gateRef }), "Status Gate disimpan")}>Simpan</button>
            </div>
          )}
        </div>
      )}
      {r.status === "Ditolak" && <div className="mb-4 rounded-lg bg-gray-100 p-3 text-sm">Ditolak: {r.rejectReason}</div>}
      {r.closedNote && <div className="mb-4 rounded-lg bg-brand-cream p-3 text-sm">Ditutup: {r.closedNote}</div>}
      {r.parent && <div className="mb-2 text-xs">Lanjutan dari <b>{r.parent.code}</b></div>}
      {r.children?.length > 0 && <div className="mb-2 text-xs">Dilanjutkan oleh {r.children.map((c) => <b key={c.id}>{c.code} </b>)}</div>}
      {r.missing?.length > 0 && <div className="mb-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-900">Brief belum lengkap: {r.missing.join(", ")}</div>}

      <section className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-sm text-brand-deep">Brief</h3>
          {editable && <button className="btn-ghost btn-sm" onClick={() => setEdit(true)}>Ubah</button>}
        </div>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
          {[["Peminta", `${name(r.requesterId)} · ${r.source}`], ["Tujuan funnel", r.funnelGoal], ["Tipe aset", r.assetType], ["Prioritas", r.priority],
            ["Key message", r.keyMessage], ["Hook", r.hook], ["CTA", r.cta], ["Kode tracking", r.trackingCode],
            ["Produk hero", r.heroProduct], ["SKU pendukung", r.supportingSkus], ["Talent", r.talent], ["Props", r.props],
            ["Lokasi", r.location], ["Shoot", r.shootDate ? `${fmtDate(r.shootDate)} ${r.shootTime || ""}` : ""], ["Mood", r.mood],
            ["Teks wajib", r.mandatoryText], ["Sumber angka", r.mandatoryTextSource],
            ["PIC", [["Shoot", r.picShootId], ["Design", r.picDesignId], ["Edit", r.picEditId]].filter((x) => x[1]).map(([k, v]) => `${k}: ${name(v)}`).join(" · ")],
            ["Reviewer", r.reviewerId ? name(r.reviewerId) : ""], ["Budget", r.isBudgeted ? `Rp${Number(r.budget || 0).toLocaleString("id-ID")}` : ""], ["Catatan", r.notes]]
            .filter(([, v]) => v).map(([k, v]) => (
              <div key={k} className={["Key message", "Hook", "Teks wajib", "Catatan"].includes(k) ? "sm:col-span-2" : ""}><dt className="text-[11px] text-gray-500">{k}</dt><dd className="whitespace-pre-wrap">{v}</dd></div>
            ))}
          {r.referenceLinks?.length > 0 && <div className="sm:col-span-2"><dt className="text-[11px] text-gray-500">Referensi</dt>
            {r.referenceLinks.map((l) => <dd key={l}><a className="text-brand underline break-all" href={l} target="_blank" rel="noreferrer">{l}</a></dd>)}</div>}
        </dl>
      </section>

      <section className="mb-5">
        <h3 className="font-bold text-sm text-brand-deep mb-2">Output ({r.outputsDone}/{r.outputs.length})</h3>
        <div className="space-y-2">
          {r.outputs.map((o, i) => <OutputRow key={i} r={r} o={o} i={i} canEdit={canAct && (isPic || isLead)} run={run} suggested={r.suggestedFileNames[i]} />)}
        </div>
        <div className="mt-3 flex gap-2 items-end">
          <Field label="Folder Google Drive" className="flex-1"><input className="inp" value={drive ?? r.driveFolderLink ?? ""} onChange={(e) => setDrive(e.target.value)} placeholder="https://drive.google.com/…" disabled={!(canAct && (isPic || isLead))} /></Field>
          {canAct && (isPic || isLead) && drive !== null && <button className="btn-ghost" onClick={async () => { if (await run(() => put(`/api/requests/${r.id}`, { driveFolderLink: drive }), "Link folder disimpan")) setDrive(null); }}>Simpan</button>}
        </div>
        {r.fileNameWarnings?.length > 0 && <div className="mt-2 text-xs text-amber-800">Nama file tidak sesuai konvensi: {r.fileNameWarnings.join(", ")}</div>}
      </section>

      <section className="mb-5">
        <h3 className="font-bold text-sm text-brand-deep mb-2">Catatan revisi</h3>
        {rounds.map(({ n, notes }) => (
          <div key={n} className="mb-2">
            <div className="text-xs font-semibold text-gray-600 mb-1">Ronde {n}</div>
            {notes.length === 0 && <div className="text-xs text-gray-400">Belum ada catatan.</div>}
            {notes.map((x) => (
              <div key={x.id} className={`rounded-lg border border-brand-line p-2 mb-1 text-sm ${x.resolved ? "opacity-60" : ""}`}>
                <div className="flex justify-between gap-2 text-[11px] text-gray-500"><span>{x.authorName || name(x.authorId)} · {fmtTime(x.createdAt)}</span>
                  {!x.resolved && (isPic || isLead) && <button className="text-brand font-semibold" onClick={() => run(() => post(`/api/requests/${r.id}/revision-notes/${x.id}/resolve`), "Ditandai selesai")}>Tandai selesai</button>}
                  {x.resolved && <span>✓ selesai</span>}</div>
                {x.timecodes && <div className="font-mono text-xs text-brand-deep">{x.timecodes}</div>}
                <div className="whitespace-pre-wrap">{x.text}</div>
              </div>
            ))}
          </div>
        ))}
        {canAct && r.revisionRound < 2 && ["Produksi", "Review", "Revisi", "Approval"].includes(r.status) && (
          <div className="grid grid-cols-1 sm:grid-cols-6 gap-2 mt-2">
            <input className="inp sm:col-span-1" placeholder="00:03" value={note.timecodes} onChange={(e) => setNote({ ...note, timecodes: e.target.value })} />
            <input className="inp sm:col-span-4" placeholder="Catatan revisi…" value={note.text} onChange={(e) => setNote({ ...note, text: e.target.value })} />
            <button className="btn-ghost sm:col-span-1" onClick={async () => { if (await run(() => post(`/api/requests/${r.id}/revision-notes`, note), "Catatan ditambahkan")) setNote({ text: "", timecodes: "" }); }}>Tambah</button>
          </div>
        )}
        {r.revisionRound >= 2 && <div className="text-xs text-brand mt-1">Sudah 2 ronde revisi. Perubahan lanjutan = brief baru.</div>}
      </section>

      <section className="mb-5">
        <h3 className="font-bold text-sm text-brand-deep mb-2">QC ({qcCount}/9)</h3>
        <div className="space-y-1">
          {meta.qc.map((q, i) => (
            <label key={q.key} className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1" checked={!!items[q.key]} disabled={!(canAct && (isPic || isLead)) || !["Produksi", "Review", "Revisi", "Approval"].includes(r.status)}
                onChange={(e) => { const v = e.target.checked; setQcLocal((x) => ({ ...x, [q.key]: v })); run(() => put(`/api/requests/${r.id}/qc`, { as: "maker", items: { [q.key]: v } })); }} />
              <span><b>{i + 1}.</b> {q.label}</span>
            </label>
          ))}
        </div>
        <div className="mt-2 text-xs text-gray-600">
          Pembuat: <b>{r.qc?.qcByMaker ? name(r.qc.qcByMaker) : "–"}</b> · Reviewer: <b>{r.qc?.qcByReviewer ? name(r.qc.qcByReviewer) : "–"}</b>
        </div>
        {canAct && (isReviewer || isLead) && r.qcComplete && r.qc?.qcByMaker && r.qc.qcByMaker !== me.id && !r.qc?.qcByReviewer && (
          <button className="btn-primary btn-sm mt-2" onClick={() => run(() => put(`/api/requests/${r.id}/qc`, { as: "reviewer" }), "QC dikonfirmasi")}>Konfirmasi QC sebagai reviewer</button>
        )}
      </section>

      {r.approvalRequired && (
        <section className="mb-5">
          <h3 className="font-bold text-sm text-brand-deep mb-2">Approval</h3>
          <div className="text-sm">{r.approval?.by ? <>Disetujui <b>{name(r.approval.by)}</b> · {fmtTime(r.approval.at)} {r.approval.note && `· ${r.approval.note}`}</> : "Wajib approval Brand Lead / Marketing Lead sebelum Final."}</div>
        </section>
      )}

      {r.contentItems?.length > 0 && (
        <section className="mb-5">
          <h3 className="font-bold text-sm text-brand-deep mb-2">Konten terkait</h3>
          {r.contentItems.map((c) => (
            <div key={c.id} className={`rounded-lg border p-2 mb-1 text-sm ${CONTENT_COLORS[c.status]}`}>{fmtDate(c.date)} · {c.platform} {c.format} · {c.idea || c.hook} · <b>{c.status}</b></div>
          ))}
        </section>
      )}

      <section>
        <h3 className="font-bold text-sm text-brand-deep mb-2">Riwayat</h3>
        <div className="text-xs space-y-1 max-h-64 overflow-y-auto">
          {r.log.map((l, i) => (
            <div key={i} className="flex gap-2"><span className="text-gray-500 w-28 shrink-0">{fmtTime(l.at)}</span>
              <span><b>{name(l.byId)}</b> {l.action}{l.from || l.to ? ` ${l.from ?? ""} → ${typeof l.to === "object" ? "" : l.to ?? ""}` : ""} {l.note && <span className="text-gray-500">({l.note})</span>}</span></div>
          ))}
        </div>
      </section>

      {edit && <BriefForm open onClose={() => setEdit(false)} initial={r} />}
    </Drawer>
  );
}

function OutputRow({ r, o, i, canEdit, run, suggested }) {
  const [link, setLink] = useState(o.fileLink || "");
  const [fname, setFname] = useState(o.finalFileName || "");
  const dirty = link !== (o.fileLink || "") || fname !== (o.finalFileName || "");
  return (
    <div className={`rounded-lg border p-2 ${o.done ? "border-green-300 bg-green-50" : "border-brand-line"}`}>
      <div className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={o.done} disabled={!canEdit}
          onChange={(e) => run(() => put(`/api/requests/${r.id}/outputs/${i}`, { done: e.target.checked, fileLink: link, finalFileName: fname }), e.target.checked ? "Output selesai" : "Output dibuka lagi")} />
        <b>{o.format || "Output"}</b><span className="text-gray-500 text-xs">{o.ratio} {o.size} {o.duration} · {o.platform}</span>
      </div>
      <div className="mt-1 flex items-center gap-1 text-[11px] text-gray-600">
        <span className="font-mono break-all">{suggested}</span>
        <button className="text-brand font-semibold shrink-0" onClick={() => { navigator.clipboard?.writeText(suggested); setFname(suggested); }}>Salin</button>
      </div>
      {canEdit && (
        <div className="mt-1 grid grid-cols-1 sm:grid-cols-5 gap-1">
          <input className="inp sm:col-span-2" placeholder="Link file" value={link} onChange={(e) => setLink(e.target.value)} />
          <input className="inp sm:col-span-2" placeholder="Nama file final" value={fname} onChange={(e) => setFname(e.target.value)} />
          <button className="btn-ghost" disabled={!dirty} onClick={() => run(() => put(`/api/requests/${r.id}/outputs/${i}`, { fileLink: link, finalFileName: fname }), "Output disimpan")}>Simpan</button>
        </div>
      )}
      {!canEdit && o.fileLink && <a className="text-xs text-brand underline break-all" href={o.fileLink} target="_blank" rel="noreferrer">{o.fileLink}</a>}
    </div>
  );
}
