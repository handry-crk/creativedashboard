"""Aturan bisnis murni (tanpa database) supaya mudah diuji."""
import re
from datetime import date, timedelta

from . import clock
from .constants import (
    GATE_OK, PRE_REVIEW, CLOSED_STATUSES, QC_KEYS, PILLARS, CONTENT_STATUSES,
)


# ---------- Hari kerja & SLA ----------
def is_workday(d: date, settings: dict) -> bool:
    return d.isoweekday() in settings.get("workDays", [1, 2, 3, 4, 5, 6]) and d.isoformat() not in settings.get("holidays", [])


def add_workdays(start: date, n: int, settings: dict) -> date:
    """H+n hari kerja. n=0 -> hari yang sama."""
    d = start
    added = 0
    while added < n:
        d += timedelta(days=1)
        if is_workday(d, settings):
            added += 1
    return d


def workdays_between(a: date, b: date, settings: dict) -> int:
    """Jumlah hari kerja dari a (eksklusif) sampai b (inklusif). Negatif bila b < a."""
    if b == a:
        return 0
    sign = 1 if b > a else -1
    lo, hi = (a, b) if b > a else (b, a)
    count, d = 0, lo
    while d < hi:
        d += timedelta(days=1)
        if is_workday(d, settings):
            count += 1
    return sign * count


def sla_dates(asset_type: str, shoot_date: str | None, base_date: date, settings: dict) -> tuple[str, str]:
    sla = settings["slaTable"].get(asset_type, {"draftDays": 2, "finalDays": 3, "basis": "request"})
    start = base_date
    if sla.get("basis") == "shoot" and shoot_date:
        start = clock.parse_date(shoot_date)
    return (add_workdays(start, int(sla["draftDays"]), settings).isoformat(),
            add_workdays(start, int(sla["finalDays"]), settings).isoformat())


def deadline_flags(req: dict, settings: dict, today: date | None = None) -> dict:
    today = today or clock.today()
    st = req.get("status")
    final = clock.parse_date(req.get("deadlineFinal"))
    draft = clock.parse_date(req.get("deadlineDraft"))
    open_ = st not in CLOSED_STATUSES and st not in {"Brief Masuk", "Ditahan Gate"}
    overdue = bool(final and open_ and today > final)
    at_risk = bool(final and not overdue and st in PRE_REVIEW and workdays_between(today, final, settings) <= 1)
    draft_late = bool(draft and st in PRE_REVIEW and today > draft)
    return {"overdue": overdue, "atRisk": at_risk, "draftLate": draft_late}


# ---------- Brief ----------
def brief_missing(req: dict) -> list[str]:
    missing = []
    if not (req.get("title") or "").strip():
        missing.append("judul")
    if not req.get("funnelGoal"):
        missing.append("tujuan funnel")
    if not req.get("assetType"):
        missing.append("tipe aset")
    if not req.get("outputs"):
        missing.append("minimal 1 output")
    km = (req.get("keyMessage") or "").strip()
    if not km:
        missing.append("key message")
    elif len(km) > 140:
        missing.append("key message maks. 140 karakter")
    if not (req.get("cta") or "").strip():
        missing.append("CTA")
    if not any(req.get(k) for k in ("picShootId", "picDesignId", "picEditId")):
        missing.append("minimal 1 PIC")
    return missing


def needs_gate_hold(req: dict) -> bool:
    return bool(req.get("isPromo") or req.get("isBudgeted")) and req.get("gateStatus") not in GATE_OK


def approval_required(req: dict) -> bool:
    return req.get("assetType") == "ADS" or bool(req.get("isBudgeted")) or (
        req.get("assetType") == "POSM" and bool(req.get("isPromo")))


def qc_complete(qc: dict | None) -> bool:
    items = (qc or {}).get("items") or {}
    return all(items.get(k) for k in QC_KEYS)


# ---------- Penamaan file ----------
_EXT = {"REEL": "mp4", "TIKTOK": "mp4", "ADS": "mp4", "EVENTDOC": "mp4", "STORY": "mp4",
        "DECK": "pptx", "POSM": "pdf"}
FILE_RE = re.compile(
    r"^CBAA_[A-Za-z0-9]+_\d{8}_(REEL|TIKTOK|STORY|FEED|CAROUSEL|POSM|MKT|ADS|EVENTDOC|DECK)_[A-Za-z0-9]+_v\d+_(IG|TT|FB|MKT|PRINT|DECK)(\.[A-Za-z0-9]+)?$"
)


def camel(s: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", s or "")
    return "".join(w[:1].upper() + w[1:] for w in words)[:40] or "Aset"


def output_platform_code(platform: str | None) -> str:
    p = (platform or "").upper()
    if p in {"IG", "TT", "FB", "MKT", "PRINT", "DECK"}:
        return p
    if "TIK" in p or p == "TT":
        return "TT"
    if "INSTA" in p or p.startswith("IG"):
        return "IG"
    if "MARKET" in p or "SHOPEE" in p or "TOKOPEDIA" in p:
        return "MKT"
    return "IG"


def suggest_filename(req: dict, output: dict) -> str:
    loc = camel(req.get("location") or "Braga")
    d = (req.get("shootDate") or req.get("briefOkAt") or req.get("createdAt") or clock.today_str())[:10].replace("-", "")
    t = req.get("assetType") or "FEED"
    v = (req.get("revisionRound") or 0) + 1
    ext = _EXT.get(t, "jpg")
    if output.get("format", "").lower() in {"foto", "photo", "feed foto", "png", "cutout"}:
        ext = "png" if "cut" in output.get("format", "").lower() else "jpg"
    return f"CBAA_{loc}_{d}_{t}_{camel(req.get('title', ''))}_v{v}_{output_platform_code(output.get('platform'))}.{ext}"


def filename_warnings(names: list[str]) -> list[str]:
    return [n for n in names if n and not FILE_RE.match(n.strip())]


# ---------- Request -> konten ----------
def content_status_for_request(req_status: str) -> tuple[str | None, bool]:
    """(status konten baru, aset siap?)."""
    if req_status == "Brief OK":
        return "Brief", False
    if req_status == "Shoot":
        return "Shoot", False
    if req_status in {"Produksi", "Review", "Revisi", "Approval"}:
        return "Edit", False
    if req_status in {"Final", "Diserahkan"}:
        return "Edit", True
    return None, False


def outputs_from_content(item: dict) -> list[dict]:
    fmt = item.get("format")
    plat = item.get("platform")
    if fmt in {"Reels", "TikTok"} and plat == "IG+TT":
        return [
            {"format": "IG Reels", "ratio": "9:16", "size": "1080x1920", "duration": "7-15 detik", "platform": "IG", "done": False, "fileLink": ""},
            {"format": "TikTok (tanpa watermark)", "ratio": "9:16", "size": "1080x1920", "duration": "7-15 detik", "platform": "TT", "done": False, "fileLink": ""},
        ]
    ratio, size = {
        "Reels": ("9:16", "1080x1920"), "TikTok": ("9:16", "1080x1920"), "TikTok LIVE": ("9:16", "1080x1920"),
        "Story": ("9:16", "1080x1920"), "Feed": ("4:5", "1080x1350"), "Carousel": ("4:5", "1080x1350"),
    }.get(fmt, ("4:5", "1080x1350"))
    p = "TT" if plat == "TT" else "IG"
    return [{"format": f"{'TikTok' if p == 'TT' and fmt != 'TikTok' else ''} {fmt}".strip(), "ratio": ratio, "size": size,
             "duration": "7-15 detik" if ratio == "9:16" else "", "platform": p, "done": False, "fileLink": ""}]


# ---------- Kalender ----------
def _in_windows(t: str, windows: list[str]) -> bool:
    for w in windows:
        try:
            a, b = w.split("-")
            if a.strip() <= t <= b.strip():
                return True
        except ValueError:
            continue
    return False


def month_targets(settings: dict, month: str) -> dict:
    return settings.get("monthOverrides", {}).get(month) or settings["pillarTargets"]


def pillar_mix(items: list[dict], settings: dict, month: str) -> dict:
    core = [i for i in items if i.get("format") != "Story" and i.get("status") != "Batal"]
    total = len(core)
    targets = month_targets(settings, month)
    rows = []
    for p in PILLARS:
        n = sum(1 for i in core if i.get("pillar") == p)
        pct = round(n * 100 / total, 1) if total else 0.0
        tgt = targets.get(p, 0)
        rows.append({"pillar": p, "count": n, "pct": pct, "target": tgt, "delta": round(pct - tgt, 1),
                     "flag": total > 0 and abs(pct - tgt) >= 5})
    reactive = sum(1 for i in core if i.get("isReactiveSlot"))
    reactive_pct = round(reactive * 100 / total, 1) if total else 0.0
    promo_days = len({i["date"] for i in items if i.get("isPromo") and i.get("status") != "Batal"})
    formats = {}
    for i in items:
        if i.get("status") == "Batal":
            continue
        formats[i.get("format")] = formats.get(i.get("format"), 0) + 1
    story_days = len({i["date"] for i in items if i.get("format") == "Story" and i.get("status") != "Batal"})
    return {"month": month, "total": total, "pillars": rows, "reactive": reactive, "reactivePct": reactive_pct,
            "reactiveTarget": settings.get("reactiveSlotPct", 20),
            "reactiveFlag": total > 0 and reactive_pct < settings.get("reactiveSlotPct", 20),
            "promoDays": promo_days, "formats": formats, "storyDays": story_days}


def content_warnings(items: list[dict], requests_by_id: dict, settings: dict, today: date | None = None) -> list[dict]:
    today = today or clock.today()
    out = []
    promo_per_day: dict[str, list] = {}
    sched_idx = CONTENT_STATUSES.index("Scheduled")
    for i in items:
        if i.get("status") == "Batal":
            continue
        iid, d = i["id"], clock.parse_date(i["date"])
        if i.get("isPromo"):
            promo_per_day.setdefault(i["date"], []).append(iid)
            if i.get("gateStatus") not in GATE_OK:
                out.append({"type": "promo_no_gate", "itemId": iid, "date": i["date"], "message": "Promo menunggu Gate (belum GO)"})
        req = requests_by_id.get(i.get("requestId") or "")
        if req and req.get("status") not in {"Final", "Diserahkan"}:
            df = clock.parse_date(req.get("deadlineFinal"))
            if df and df > d:
                out.append({"type": "asset_not_ready", "itemId": iid, "date": i["date"],
                            "message": f"Aset belum siap sebelum tanggal tayang ({req['code']} deadline {req['deadlineFinal']})"})
        if req and req.get("status") in {"Ditolak", "Batal"}:
            out.append({"type": "asset_cancelled", "itemId": iid, "date": i["date"], "message": f"Aset batal ({req['code']})"})
        st_idx = CONTENT_STATUSES.index(i.get("status", "Idea"))
        if today <= d <= today + timedelta(days=1) and st_idx < sched_idx:
            out.append({"type": "h1_not_scheduled", "itemId": iid, "date": i["date"], "message": "H-1 belum terjadwal"})
        if i.get("status") == "Posted" and not i.get("postedUrl"):
            out.append({"type": "posted_no_url", "itemId": iid, "date": i["date"], "message": "Posted tanpa link postingan"})
        if i.get("time") and i.get("format") != "Story" and not _in_windows(i["time"], settings.get("postingWindows", [])):
            out.append({"type": "outside_window", "itemId": iid, "date": i["date"], "message": f"Jam {i['time']} di luar jam posting"})
    for d, ids in promo_per_day.items():
        if len(ids) > settings.get("maxPromoPerDay", 1):
            for iid in ids:
                out.append({"type": "double_promo", "itemId": iid, "date": d, "message": "Lebih dari 1 promo di hari yang sama"})
    return sorted(out, key=lambda w: (w["date"], w["type"]))
