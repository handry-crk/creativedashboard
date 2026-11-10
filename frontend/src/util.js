const HARI = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
const BLN = BULAN.map((b) => b.slice(0, 3));

export function parseD(s) {
  if (!s) return null;
  const [y, m, d] = s.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}
export const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export function fmtDate(s, long = false) {
  const d = parseD(s);
  if (!d) return "–";
  return long ? `${HARI[d.getDay()]}, ${d.getDate()} ${BULAN[d.getMonth()]} ${d.getFullYear()}` : `${d.getDate()} ${BLN[d.getMonth()]}`;
}
export const monthLabel = (ym) => { const [y, m] = ym.split("-").map(Number); return `${BULAN[m - 1]} ${y}`; };
export function shiftMonth(ym, n) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
export function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
export const num = (n) => (n == null ? "–" : Number(n).toLocaleString("id-ID"));
export const initials = (name = "") => name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
export const isoWeek = (s) => {
  const d = parseD(s);
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  const w = Math.ceil(((t - y0) / 86400000 + 1) / 7);
  return `${t.getUTCFullYear()}-W${String(w).padStart(2, "0")}`;
};

export const STATUS_COLORS = {
  "Brief Masuk": "bg-gray-100 text-gray-700",
  "Ditahan Gate": "bg-red-100 text-red-700",
  "Brief OK": "bg-blue-100 text-blue-700",
  Shoot: "bg-purple-100 text-purple-700",
  Produksi: "bg-amber-100 text-amber-800",
  Review: "bg-cyan-100 text-cyan-800",
  Revisi: "bg-orange-100 text-orange-800",
  Approval: "bg-pink-100 text-pink-800",
  Final: "bg-emerald-100 text-emerald-800",
  Diserahkan: "bg-green-600 text-white",
  Ditolak: "bg-gray-200 text-gray-500 line-through",
  Batal: "bg-gray-200 text-gray-500 line-through",
};
export const CONTENT_COLORS = {
  Idea: "bg-gray-100 text-gray-700 border-gray-300",
  Brief: "bg-blue-50 text-blue-800 border-blue-300",
  Shoot: "bg-purple-50 text-purple-800 border-purple-300",
  Edit: "bg-amber-50 text-amber-900 border-amber-300",
  Scheduled: "bg-teal-50 text-teal-800 border-teal-300",
  Posted: "bg-green-50 text-green-800 border-green-400",
  Batal: "bg-gray-50 text-gray-400 border-gray-200 line-through",
};
export const PLATFORM_ICON = { IG: "IG", TT: "TT", "IG+TT": "IG·TT" };
