"""Job terjadwal: digest pagi, pengingat deadline, approval menunggu, rekap mingguan, backup."""
import json
import logging
import os
from datetime import datetime, timedelta

from . import clock, notify, rules
from .config import config
from .constants import ACTIVE_STATUSES, APPROVER_FUNCTIONS, CLOSED_STATUSES, PILLARS
from .core import NOPROJ, get_settings, members_map
from .services import decorate, pics

log = logging.getLogger("crk.jobs")
COLLECTIONS = ["members", "requests", "content", "shoots", "revisionnotes", "activitylog", "settings", "emaillog", "joblog"]


async def _once(db, slot: str, force: bool) -> bool:
    """True bila slot hari ini belum dijalankan (lalu ditandai)."""
    if force:
        return True
    key = {"date": clock.today_str(), "slot": slot}
    if await db.joblog.find_one(key):
        return False
    await db.joblog.insert_one({**key, "at": clock.iso_utc()})
    return True


async def _all_requests(db, settings):
    return [decorate(r, settings) async for r in db.requests.find({}, NOPROJ)]


def _row(r):
    return [r["code"], r["title"][:50], r["status"], r.get("deadlineFinal") or "-"]


async def digest(db, force: bool = False) -> dict:
    settings = await get_settings(db)
    if not force and not rules.is_workday(clock.today(), settings):
        return {"skipped": "bukan hari kerja"}
    if not await _once(db, "digest", force):
        return {"skipped": "sudah terkirim"}
    today, tomorrow = clock.today_str(), clock.add_days(clock.today(), 1).isoformat()
    reqs = await _all_requests(db, settings)
    content_today = [c async for c in db.content.find({"date": today, "status": {"$ne": "Batal"}}, NOPROJ)]
    mm = await members_map(db)
    sent = 0
    for m in mm.values():
        if not m.get("active", True) or m["role"] not in {"creative", "creative_lead", "socmed"}:
            continue
        mine = [r for r in reqs if m["id"] in pics(r) and r["status"] not in CLOSED_STATUSES]
        due = [r for r in mine if r.get("deadlineFinal") in (today, tomorrow) or r.get("deadlineDraft") in (today, tomorrow)]
        overdue = [r for r in mine if r["overdue"]]
        revisi = [r for r in mine if r["status"] == "Revisi"]
        review = [r for r in reqs if r.get("reviewerId") == m["id"] and r["status"] == "Review"]
        cont = [c for c in content_today if m["role"] != "socmed" or c.get("picSocmedId") in (m["id"], None)]
        if not (due or overdue or revisi or review or (m["role"] == "socmed" and cont)):
            continue
        h = ["Deadline hari ini / besok", notify.table(["Kode", "Judul", "Status", "Deadline"], [_row(r) for r in due]),
             "Overdue", notify.table(["Kode", "Judul", "Status", "Deadline"], [_row(r) for r in overdue]),
             "Revisi menunggu Anda", notify.table(["Kode", "Judul", "Status", "Deadline"], [_row(r) for r in revisi]),
             "Perlu Anda review", notify.table(["Kode", "Judul", "Status", "Deadline"], [_row(r) for r in review])]
        if m["role"] == "socmed":
            h += ["Tayang hari ini", notify.table(["Jam", "Platform", "Format", "Konten", "Status"],
                                                  [[c.get("time") or "-", c["platform"], c["format"], (c.get("idea") or "")[:50], c["status"]] for c in cont])]
        body = "".join(f"<h3 style='font-size:14px;margin:14px 0 4px'>{x}</h3>" if i % 2 == 0 else x for i, x in enumerate(h))
        sent += await notify.send(db, [m["email"]], f"Digest Creative Hub {today}", notify.layout(f"Halo {m['name']}, ini tugas Anda", body), "digest")
    # ringkasan tim untuk Lead & Approver
    leads = [m["email"] for m in mm.values() if m.get("active", True) and (m["role"] in {"creative_lead"} or m["jobFunction"] in APPROVER_FUNCTIONS)]
    active = [r for r in reqs if r["status"] in ACTIVE_STATUSES]
    summary = (f"<p>Aktif: <b>{len(active)}</b> · Overdue: <b>{sum(r['overdue'] for r in reqs)}</b> · At risk: <b>{sum(r['atRisk'] for r in reqs)}</b>"
               f" · Review: <b>{sum(r['status']=='Review' for r in reqs)}</b> · Approval: <b>{sum(r['status']=='Approval' for r in reqs)}</b>"
               f" · Ditahan Gate: <b>{sum(r['status']=='Ditahan Gate' for r in reqs)}</b> · Konten tayang hari ini: <b>{len(content_today)}</b></p>")
    summary += notify.table(["Kode", "Judul", "Status", "Deadline"], [_row(r) for r in reqs if r["overdue"]])
    sent += await notify.send(db, leads + [settings.get("adminEmail", "")], f"Ringkasan tim Creative Hub {today}",
                              notify.layout("Ringkasan tim hari ini", summary), "digest-team")
    return {"sent": sent}


async def deadline_reminder(db, force: bool = False) -> dict:
    settings = await get_settings(db)
    if not force and not rules.is_workday(clock.today(), settings):
        return {"skipped": "bukan hari kerja"}
    if not await _once(db, "deadline", force):
        return {"skipped": "sudah terkirim"}
    reqs = [r for r in await _all_requests(db, settings) if r["atRisk"] or r["draftLate"]]
    mm = await members_map(db)
    sent = 0
    for pid in {p for r in reqs for p in pics(r)}:
        m = mm.get(pid)
        if not m:
            continue
        mine = [r for r in reqs if pid in pics(r)]
        rows = [[r["code"], r["title"][:50], r["status"], r.get("deadlineDraft") or "-", r.get("deadlineFinal") or "-",
                 "draft telat" if r["draftLate"] else "at risk"] for r in mine]
        sent += await notify.send(db, [m["email"]], "Pengingat deadline Creative Hub",
                                  notify.layout("Deadline mendekat", notify.table(["Kode", "Judul", "Status", "Draft", "Final", "Catatan"], rows)), "deadline")
    return {"sent": sent, "requests": len(reqs)}


async def approval_reminder(db, force: bool = False) -> dict:
    settings = await get_settings(db)
    if not force and not rules.is_workday(clock.today(), settings):
        return {"skipped": "bukan hari kerja"}
    if not await _once(db, "approval", force):
        return {"skipped": "sudah terkirim"}
    today = clock.today()
    waiting = []
    async for r in db.requests.find({"status": "Approval"}, NOPROJ):
        since = clock.parse_date(r.get("approvalRequestedAt") or r["updatedAt"][:10])
        if rules.workdays_between(since, today, settings) > 1:
            waiting.append(r)
    if not waiting:
        return {"sent": 0}
    mm = await members_map(db)
    emails = [m["email"] for m in mm.values() if m.get("active", True) and m["jobFunction"] in APPROVER_FUNCTIONS]
    rows = [[r["code"], r["title"][:50], r.get("assetType"), r.get("approvalRequestedAt") or "-"] for r in waiting]
    sent = await notify.send(db, emails, f"{len(waiting)} aset menunggu approval",
                             notify.layout("Aset menunggu approval > 1 hari kerja", notify.table(["Kode", "Judul", "Tipe", "Sejak"], rows)), "approval")
    return {"sent": sent, "requests": len(waiting)}


def _local(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).astimezone(clock.WIB).date().isoformat()
    except ValueError:
        return iso[:10]


async def weekly_data(db) -> dict:
    settings = await get_settings(db)
    today = clock.today()
    this_mon = today - timedelta(days=today.isoweekday() - 1)
    start, end = this_mon - timedelta(days=7), this_mon - timedelta(days=1)
    s, e = start.isoformat(), end.isoformat()
    reqs = await _all_requests(db, settings)
    delivered = [r for r in reqs if s <= _local(r.get("handoverAt")) <= e]
    planned = [r for r in reqs if r.get("deadlineFinal") and s <= r["deadlineFinal"] <= e and r["status"] not in {"Batal", "Ditolak"}]
    ontime = [r for r in delivered if r.get("deadlineFinal") and _local(r["handoverAt"]) <= r["deadlineFinal"]]
    by_type = {}
    for r in planned:
        t = by_type.setdefault(r.get("assetType") or "-", {"rencana": 0, "selesai": 0})
        t["rencana"] += 1
    for r in delivered:
        t = by_type.setdefault(r.get("assetType") or "-", {"rencana": 0, "selesai": 0})
        t["selesai"] += 1
    closed = [r for r in reqs if s <= _local(r.get("finalAt")) <= e]
    avg_rev = round(sum(r.get("revisionRound", 0) for r in closed) / len(closed), 2) if closed else None
    items = [c async for c in db.content.find({"date": {"$gte": s, "$lte": e}}, NOPROJ)]
    posted = sum(1 for c in items if c["status"] == "Posted")
    planned_c = sum(1 for c in items if c["status"] != "Batal")
    month = clock.today_str()[:7]
    month_items = [c async for c in db.content.find({"date": {"$regex": f"^{month}"}}, NOPROJ)]
    mix = rules.pillar_mix(month_items, settings, month)
    promo_no_gate = [c for c in month_items if c.get("isPromo") and c.get("gateStatus") not in {"GO", "GWC"} and c["status"] != "Batal"]
    ns, ne = this_mon.isoformat(), (this_mon + timedelta(days=6)).isoformat()
    shoots = [x async for x in db.shoots.find({"date": {"$gte": ns, "$lte": ne}}, NOPROJ).sort("date", 1)]
    from .services import workload
    return {"from": s, "to": e, "byType": by_type, "delivered": len(delivered), "planned": len(planned),
            "onTimePct": round(len(ontime) * 100 / len(delivered)) if delivered else None, "avgRevisi": avg_rev,
            "overdue": [_row(r) for r in reqs if r["overdue"]], "workload": await workload(db),
            "contentPosted": posted, "contentPlanned": planned_c, "mix": mix,
            "promoNoGate": [[c["date"], c["platform"], c["format"], (c.get("idea") or "")[:50]] for c in promo_no_gate],
            "nextShoots": [[x["date"], x.get("time") or "-", x.get("location") or "-", len(x.get("requestIds", []))] for x in shoots]}


async def weekly_recap(db, force: bool = False) -> dict:
    if not await _once(db, "weekly", force):
        return {"skipped": "sudah terkirim"}
    settings = await get_settings(db)
    d = await weekly_data(db)
    body = (f"<p>Periode <b>{d['from']}</b> s/d <b>{d['to']}</b></p>"
            f"<p>Aset diserahkan <b>{d['delivered']}</b> dari rencana {d['planned']} · On time <b>{d['onTimePct'] if d['onTimePct'] is not None else '-'}%</b>"
            f" · Rata-rata ronde revisi <b>{d['avgRevisi'] if d['avgRevisi'] is not None else '-'}</b></p>"
            + notify.table(["Tipe", "Rencana", "Selesai"], [[k, v["rencana"], v["selesai"]] for k, v in sorted(d["byType"].items())])
            + "<h3 style='font-size:14px'>Overdue</h3>" + notify.table(["Kode", "Judul", "Status", "Deadline"], d["overdue"])
            + "<h3 style='font-size:14px'>Beban kerja</h3>" + notify.table(["Nama", "Aktif", "Kapasitas"], [[w["name"], w["active"], w["capacity"]] for w in d["workload"]])
            + f"<h3 style='font-size:14px'>Kalender</h3><p>Posted {d['contentPosted']} dari {d['contentPlanned']} rencana minggu lalu.</p>"
            + notify.table(["Pillar", "Aktual %", "Target %", "Delta"], [[p["pillar"], p["pct"], p["target"], p["delta"]] for p in d["mix"]["pillars"]])
            + "<h3 style='font-size:14px'>Promo belum GO</h3>" + notify.table(["Tanggal", "Platform", "Format", "Konten"], d["promoNoGate"])
            + "<h3 style='font-size:14px'>Shoot minggu ini</h3>" + notify.table(["Tanggal", "Jam", "Lokasi", "Request"], d["nextShoots"]))
    mm = await members_map(db)
    emails = [m["email"] for m in mm.values() if m.get("active", True) and m["role"] in {"creative_lead", "socmed", "approver"}]
    sent = await notify.send(db, emails + [settings.get("adminEmail", "")], f"Rekap mingguan Creative Hub {d['from']}–{d['to']}",
                             notify.layout("Rekap mingguan", body), "weekly")
    return {"sent": sent, "data": {k: d[k] for k in ("delivered", "planned", "onTimePct", "avgRevisi")}}


async def backup(db, force: bool = False) -> dict:
    if not await _once(db, "backup", force):
        return {"skipped": "sudah dijalankan"}
    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    dump = {}
    for c in COLLECTIONS:
        dump[c] = [d async for d in db[c].find({}, NOPROJ)]
    dump.pop("sessions", None)
    for s in dump.get("settings", []):
        s.pop("panelPinHash", None)
        s.pop("panelPinSalt", None)
    name = os.path.join(config.BACKUP_DIR, f"backup-{clock.now():%Y%m%d-%H%M}.json")
    with open(name, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, default=str)
    files = sorted(x for x in os.listdir(config.BACKUP_DIR) if x.startswith("backup-") and x.endswith(".json"))
    for old in files[:-8]:
        os.remove(os.path.join(config.BACKUP_DIR, old))
    return {"file": os.path.basename(name), "kept": min(len(files), 8)}


async def tick(db):
    """Dipanggil tiap 15 menit; menjalankan slot yang jatuh tempo (sekali per hari)."""
    try:
        s = await get_settings(db)
        hm = clock.now().strftime("%H:%M")
        wd = clock.today().isoweekday()
        if hm >= s.get("digestTime", "08:00"):
            await digest(db)
        if hm >= s.get("approvalTime", "10:00"):
            await approval_reminder(db)
        if hm >= s.get("deadlineTime", "15:00"):
            await deadline_reminder(db)
        if wd == int(s.get("weeklyDay", 1)) and hm >= s.get("weeklyTime", "08:30"):
            await weekly_recap(db)
        if wd == 7 and hm >= "02:00":
            await backup(db)
    except Exception:
        log.exception("tick gagal")
