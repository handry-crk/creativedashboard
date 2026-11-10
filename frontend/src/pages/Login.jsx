import { useState } from "react";
import { auth, post } from "../api";
import { Field, Select, useApp } from "../components/ui";

export default function Login({ onDone, onViewOnly }) {
  const { members, meta, toast } = useApp();
  const [mode, setMode] = useState(members.length ? "login" : "register");
  const [f, setF] = useState({ memberId: "", pin: "", name: "", jobFunction: "", email: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: typeof v === "object" && v?.target ? v.target.value : v }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      let r;
      if (mode === "login") r = await post("/api/auth/login", { memberId: f.memberId, pin: f.pin });
      else if (mode === "register") r = await post("/api/auth/register", { name: f.name, jobFunction: f.jobFunction, email: f.email, pin: f.pin });
      else r = await post("/api/auth/panel-login", { pin: f.pin });
      auth.set(r.token);
      toast(`Selamat datang, ${r.member.name}`);
      onDone();
    } catch (err) {
      toast(err.message, "err");
    } finally {
      setBusy(false);
    }
  }

  const active = members.filter((m) => m.active !== false);
  return (
    <div className="min-h-screen bg-brand-cream flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-brand text-white rounded-t-2xl p-5 flex items-center gap-3">
          <img src="/logo.svg" className="h-12 w-12" alt="" />
          <div><div className="font-extrabold text-lg leading-tight">CRK Creative Hub</div><div className="text-xs opacity-90">Produksi & Kalender Konten · Cimol Bojot AA</div></div>
        </div>
        <form onSubmit={submit} className="bg-white rounded-b-2xl p-5 space-y-3 shadow">
          <div className="flex gap-1 text-xs">
            {[["login", "Masuk"], ["register", "Daftar"], ["panel", "PIN Panel"]].map(([k, l]) => (
              <button type="button" key={k} onClick={() => setMode(k)} className={`flex-1 btn-sm btn ${mode === k ? "bg-brand text-white" : "bg-gray-100"}`}>{l}</button>
            ))}
          </div>
          {mode === "login" && (
            <Field label="Nama"><Select value={f.memberId} onChange={set("memberId")} placeholder="Pilih nama…" options={active.map((m) => ({ value: m.id, label: `${m.name} — ${m.jobFunction}` }))} required /></Field>
          )}
          {mode === "register" && (
            <>
              <Field label="Nama"><input className="inp" value={f.name} onChange={set("name")} required minLength={2} /></Field>
              <Field label="Fungsi kerja"><Select value={f.jobFunction} onChange={set("jobFunction")} placeholder="Pilih…" options={meta.jobFunctions} required /></Field>
              <Field label="Email"><input className="inp" type="email" value={f.email} onChange={set("email")} required /></Field>
            </>
          )}
          <Field label={mode === "panel" ? "PIN panel" : "PIN (4–6 angka)"}>
            <input className="inp tracking-widest" inputMode="numeric" type="password" pattern="\d{4,6}" value={f.pin} onChange={set("pin")} required />
          </Field>
          <button className="btn-primary w-full" disabled={busy}>{mode === "register" ? "Daftar & masuk" : "Masuk"}</button>
          <button type="button" className="btn-ghost w-full" onClick={onViewOnly}>Lihat saja</button>
        </form>
      </div>
    </div>
  );
}
