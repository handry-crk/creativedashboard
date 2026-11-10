import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { STATUS_COLORS, initials } from "../util";

export const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function useToast() {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((msg, kind = "ok") => {
    const id = Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "err" ? 6000 : 3500);
  }, []);
  const view = (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[80] flex flex-col gap-2 w-[92vw] max-w-md">
      {toasts.map((t) => (
        <div key={t.id} className={`rounded-lg px-4 py-3 text-sm shadow-lg ${t.kind === "err" ? "bg-brand text-white" : "bg-brand-ink text-white"}`}>{t.msg}</div>
      ))}
    </div>
  );
  return [push, view];
}

export function Drawer({ open, onClose, title, children, wide, footer }) {
  useEffect(() => {
    if (!open) return;
    const k = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className={`relative bg-white h-full w-full ${wide ? "md:max-w-3xl" : "md:max-w-xl"} flex flex-col shadow-2xl`}>
        <div className="flex items-start justify-between gap-2 border-b border-brand-line px-4 py-3">
          <div className="font-bold text-base min-w-0">{title}</div>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Tutup">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer && <div className="border-t border-brand-line px-4 py-3 bg-white">{footer}</div>}
      </div>
    </div>
  );
}

export function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-3">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative card w-full max-w-md p-4 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="font-bold mb-3">{title}</div>
        {children}
      </div>
    </div>
  );
}

export const Field = ({ label, children, hint, className = "" }) => (
  <label className={`block ${className}`}>
    {label && <span className="lbl">{label}</span>}
    {children}
    {hint && <span className="block text-[11px] text-gray-500 mt-1">{hint}</span>}
  </label>
);

export function Select({ value, onChange, options, placeholder, className = "", ...rest }) {
  return (
    <select className={`inp ${className}`} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (typeof o === "string" ? <option key={o} value={o}>{o}</option> : <option key={o.value} value={o.value}>{o.label}</option>))}
    </select>
  );
}

export const StatusPill = ({ s }) => <span className={`chip ${STATUS_COLORS[s] || "bg-gray-100"}`}>{s}</span>;

export function Avatar({ name, title }) {
  if (!name) return null;
  return <span title={title || name} className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-tint text-brand-deep text-[10px] font-bold border border-white">{initials(name)}</span>;
}

export function Tile({ label, value, tone, onClick, active }) {
  const tones = { red: "text-brand", amber: "text-amber-600", green: "text-green-700", default: "text-brand-ink" };
  return (
    <button onClick={onClick} className={`card p-3 text-left hover:border-brand transition ${active ? "ring-2 ring-brand" : ""}`}>
      <div className={`text-2xl font-extrabold ${tones[tone || "default"]}`}>{value ?? "–"}</div>
      <div className="text-[11px] text-gray-600 leading-tight mt-1">{label}</div>
    </button>
  );
}

export function Empty({ children }) {
  return <div className="text-center text-sm text-gray-500 py-8">{children}</div>;
}

export function GateBadge({ gate, gateRef }) {
  if (!gate || gate === "NA") return null;
  const ok = gate === "GO" || gate === "GWC";
  return <span className={`chip ${ok ? "bg-green-100 text-green-800" : "bg-red-100 text-red-700"}`}>Gate {gate}{gateRef ? ` · ${gateRef}` : ""}</span>;
}

/** Jalankan aksi API; tangani 409 needConfirm (kapasitas) dengan konfirmasi. */
export function useRunner() {
  const { toast, reload } = useApp();
  return useCallback(async (fn, okMsg, { retryConfirm } = {}) => {
    try {
      const r = await fn(false);
      if (okMsg) toast(okMsg);
      reload();
      return r;
    } catch (e) {
      if (e.status === 409 && e.detail?.needConfirm && retryConfirm !== false) {
        const list = (e.detail.warnings || []).map((w) => "• " + w.message).join("\n");
        if (window.confirm(`${e.message}\n\n${list}\n\nTetap tugaskan?`)) {
          try { const r = await fn(true); if (okMsg) toast(okMsg); reload(); return r; } catch (e2) { toast(e2.message, "err"); }
        }
        return null;
      }
      toast(e.message, "err");
      return undefined;
    }
  }, [toast, reload]);
}
