import csv
import io

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .. import clock, rules, services
from ..constants import (
    CONTENT_GOALS, CONTENT_STATUSES, FORMATS, FORMAT_TO_ASSET, GATE_OK, GATE_STATUSES, PILLARS, PLATFORMS,
)
from ..core import NOPROJ, Actor, err, get_db, get_settings, log, new_id, require_actor

router = APIRouter(prefix="/api/content")

FIELDS = ["date", "time", "platform", "format", "pillar", "goal", "theme", "idea", "hook", "cta", "trackingCode",
          "isPromo", "gateStatus", "gateRef", "isReactiveSlot", "picSocmedId", "requestId", "status", "captionFinal",
          "postedUrl", "postedAt", "notes"]
CSV_COLS = ["date", "time", "platform", "format", "pillar", "goal", "theme", "idea", "hook", "cta", "trackingCode",
            "isPromo", "gateStatus", "picSocmed", "status", "notes"]


class ContentIn(BaseModel):
    date: str | None = None
    time: str | None = None
    platform: str | None = None
    format: str | None = None
    pillar: str | None = None
    goal: str | None = None
    theme: str | None = None
    idea: str | None = None
    hook: str | None = None
    cta: str | None = None
    trackingCode: str | None = None
    isPromo: bool | None = None
    gateStatus: str | None = None
    gateRef: str | None = None
    isReactiveSlot: bool | None = None
    picSocmedId: str | None = None
    requestId: str | None = None
    status: str | None = None
    captionFinal: str | None = None
    postedUrl: str | None = None
    postedAt: str | None = None
    notes: str | None = None


class BriefFromContent(BaseModel):
    mandatoryText: str | None = None
    mandatoryTextSource: str | None = None
    keyMessage: str | None = None
    assetType: str | None = None
    location: str | None = None
    shootDate: str | None = None


def _require_socmed(actor: Actor):
    if not actor.is_socmed:
        raise err(403, "Kalender dikelola Socmed / Lead")


async def _validate(db, item: dict, settings: dict, exclude_id: str | None = None, strict_posted: bool = True):
    checks = [("platform", PLATFORMS), ("format", FORMATS), ("pillar", PILLARS), ("goal", CONTENT_GOALS),
              ("status", CONTENT_STATUSES), ("gateStatus", GATE_STATUSES)]
    for f, allowed in checks:
        if item.get(f) not in (None, "") and item[f] not in allowed:
            raise err(400, f"Nilai {f} tidak valid: {item[f]}")
    if not item.get("date"):
        raise err(400, "Tanggal wajib diisi")
    try:
        clock.parse_date(item["date"])
    except ValueError:
        raise err(400, "Format tanggal harus YYYY-MM-DD")
    for f in ("platform", "format", "pillar"):
        if not item.get(f):
            raise err(400, f"{f} wajib diisi")
    if item.get("isPromo") and item.get("status") != "Batal":
        q = {"date": item["date"], "isPromo": True, "status": {"$ne": "Batal"}}
        if exclude_id:
            q["id"] = {"$ne": exclude_id}
        n = await db.content.count_documents(q)
        if n >= settings.get("maxPromoPerDay", 1):
            raise err(400, f"Maksimal {settings.get('maxPromoPerDay', 1)} konten promo per hari ({item['date']})")
        if item.get("gateStatus") not in GATE_OK and item.get("status") not in ("Idea", None, ""):
            raise err(400, "Promo menunggu Gate — status hanya boleh Idea sampai GO/GWC")
    if item.get("status") == "Posted" and strict_posted:
        if not (item.get("postedUrl") or "").strip():
            raise err(400, "Status Posted wajib mengisi link postingan")
        if item.get("isPromo") and not (item.get("trackingCode") or "").strip():
            raise err(400, "Konten promo yang tayang wajib punya kode tracking")


async def _decorate_all(db, items: list[dict]) -> list[dict]:
    rids = [i["requestId"] for i in items if i.get("requestId")]
    reqs = {r["id"]: r async for r in db.requests.find({"id": {"$in": rids}}, NOPROJ)}
    out = []
    for i in items:
        r = reqs.get(i.get("requestId") or "")
        i = dict(i)
        if r:
            i["request"] = {"id": r["id"], "code": r["code"], "status": r["status"],
                            "deadlineFinal": r.get("deadlineFinal"), "title": r["title"]}
        out.append(i)
    return out


async def _month_items(db, month: str, platform: str | None = None, pic: str | None = None) -> list[dict]:
    q: dict = {"date": {"$regex": f"^{month}"}}
    if platform and platform != "semua":
        q["platform"] = {"$in": [platform, "IG+TT"]} if platform in ("IG", "TT") else platform
    if pic:
        q["picSocmedId"] = pic
    return [i async for i in db.content.find(q, NOPROJ).sort([("date", 1), ("time", 1)])]


@router.get("")
async def list_content(month: str | None = None, platform: str | None = None, pic: str | None = None, db=Depends(get_db)):
    month = month or clock.today_str()[:7]
    return await _decorate_all(db, await _month_items(db, month, platform, pic))


@router.get("/mix")
async def mix(month: str | None = None, db=Depends(get_db)):
    month = month or clock.today_str()[:7]
    settings = await get_settings(db)
    return rules.pillar_mix(await _month_items(db, month), settings, month)


@router.get("/warnings")
async def warnings(month: str | None = None, db=Depends(get_db)):
    month = month or clock.today_str()[:7]
    settings = await get_settings(db)
    items = await _month_items(db, month)
    rids = [i["requestId"] for i in items if i.get("requestId")]
    reqs = {r["id"]: r async for r in db.requests.find({"id": {"$in": rids}}, NOPROJ)}
    return rules.content_warnings(items, reqs, settings)


@router.get("/export")
async def export(month: str | None = None, db=Depends(get_db)):
    month = month or clock.today_str()[:7]
    members = {m["id"]: m["name"] async for m in db.members.find({}, {"id": 1, "name": 1})}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(CSV_COLS + ["requestCode", "postedUrl", "captionFinal"])
    for i in await _decorate_all(db, await _month_items(db, month)):
        w.writerow([i.get("date"), i.get("time") or "", i.get("platform"), i.get("format"), i.get("pillar"), i.get("goal") or "",
                    i.get("theme") or "", i.get("idea") or "", i.get("hook") or "", i.get("cta") or "", i.get("trackingCode") or "",
                    "ya" if i.get("isPromo") else "tidak", i.get("gateStatus") or "", members.get(i.get("picSocmedId"), ""),
                    i.get("status"), i.get("notes") or "", (i.get("request") or {}).get("code", ""), i.get("postedUrl") or "",
                    (i.get("captionFinal") or "").replace("\n", " ")])
    data = "﻿" + buf.getvalue()
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="kalender-konten-{month}.csv"'})


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in {"1", "ya", "yes", "true", "y", "promo"}


def _map_platform(v: str) -> str:
    v = (v or "").strip().upper().replace(" ", "")
    if v in {"IG+TT", "IG+TIKTOK", "IG/TT", "INSTAGRAM+TIKTOK"}:
        return "IG+TT"
    if v.startswith("TT") or v.startswith("TIKTOK"):
        return "TT"
    return "IG"


@router.post("/import")
async def import_csv(file: UploadFile = File(...), actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _require_socmed(actor)
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    delim = ";" if raw.splitlines()[0].count(";") >= raw.splitlines()[0].count(",") else ","
    rows = list(csv.DictReader(io.StringIO(raw), delimiter=delim))
    settings = await get_settings(db)
    members = {m["name"].lower(): m["id"] async for m in db.members.find({}, {"id": 1, "name": 1})}
    created, errors = 0, []
    for n, row in enumerate(rows, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        tracking = row.get("trackingCode", "")
        is_promo = _truthy(row.get("isPromo", "")) or tracking == "PROMO-TBD"
        gate = row.get("gateStatus") or ("PENDING" if is_promo else "NA")
        status = row.get("status") or "Idea"
        if is_promo and gate not in GATE_OK and status not in ("Posted", "Batal"):
            status = "Idea"
        item = {"date": row.get("date", ""), "time": row.get("time", ""), "platform": _map_platform(row.get("platform", "")),
                "format": row.get("format", ""), "pillar": row.get("pillar", ""), "goal": row.get("goal") or None,
                "theme": row.get("theme", ""), "idea": row.get("idea", ""), "hook": row.get("hook", ""), "cta": row.get("cta", ""),
                "trackingCode": tracking, "isPromo": is_promo, "gateStatus": gate, "gateRef": "",
                "isReactiveSlot": _truthy(row.get("isReactiveSlot", "")),
                "picSocmedId": members.get(row.get("picSocmed", "").lower()), "status": status,
                "notes": row.get("notes", ""), "postedUrl": row.get("postedUrl", "")}
        try:
            await _validate(db, item, settings, strict_posted=False)
        except Exception as e:  # catat dan lanjut
            detail = getattr(e, "detail", {"message": str(e)})
            errors.append({"row": n, "message": detail.get("message") if isinstance(detail, dict) else str(detail)})
            continue
        item.update({"id": new_id("c"), "requestId": None, "captionFinal": "",
                     "assetReady": False, "createdAt": clock.iso_utc(), "updatedAt": clock.iso_utc()})
        await db.content.insert_one(dict(item))
        created += 1
    await log(db, "content", "-", "import", actor.id, note=f"{created} baris, {len(errors)} gagal")
    return {"created": created, "errors": errors}


@router.post("")
async def create(body: ContentIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _require_socmed(actor)
    settings = await get_settings(db)
    item = {k: None for k in FIELDS}
    item.update({"status": "Idea", "isPromo": False, "isReactiveSlot": False, "gateStatus": "NA", "captionFinal": ""})
    item.update(body.model_dump(exclude_unset=True))
    if item.get("isPromo") and item.get("gateStatus") == "NA":
        item["gateStatus"] = "PENDING"
    if not item.get("picSocmedId") and actor.role == "socmed":
        item["picSocmedId"] = actor.id
    await _validate(db, item, settings)
    item.update({"id": new_id("c"), "assetReady": False, "createdAt": clock.iso_utc(), "updatedAt": clock.iso_utc()})
    if item.get("requestId"):
        await _link(db, item["id"], item["requestId"])
    await db.content.insert_one(dict(item))
    await log(db, "content", item["id"], "create", actor.id, to=item["status"])
    item.pop("_id", None)
    return item


async def _link(db, cid: str, rid: str | None, old_rid: str | None = None):
    if old_rid and old_rid != rid:
        await db.requests.update_one({"id": old_rid}, {"$pull": {"contentItemIds": cid}})
    if rid:
        r = await db.requests.find_one({"id": rid})
        if not r:
            raise err(400, "Request tidak ditemukan")
        await db.requests.update_one({"id": rid}, {"$addToSet": {"contentItemIds": cid}})


@router.get("/{cid}")
async def detail(cid: str, db=Depends(get_db)):
    i = await db.content.find_one({"id": cid}, NOPROJ)
    if not i:
        raise err(404, "Konten tidak ditemukan")
    i = (await _decorate_all(db, [i]))[0]
    i["log"] = [l async for l in db.activitylog.find({"entity": "content", "entityId": cid}, NOPROJ).sort("at", -1)]
    return i


@router.put("/{cid}")
async def update(cid: str, body: ContentIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _require_socmed(actor)
    old = await db.content.find_one({"id": cid}, NOPROJ)
    if not old:
        raise err(404, "Konten tidak ditemukan")
    upd = body.model_dump(exclude_unset=True)
    merged = {**old, **upd}
    if merged.get("isPromo") and merged.get("gateStatus") == "NA":
        merged["gateStatus"] = upd["gateStatus"] = "PENDING"
    if upd.get("status") == "Posted" and not merged.get("postedAt"):
        merged["postedAt"] = upd["postedAt"] = clock.iso_utc()
    await _validate(db, merged, await get_settings(db), exclude_id=cid)
    if "requestId" in upd:
        await _link(db, cid, upd["requestId"], old.get("requestId"))
    upd["updatedAt"] = clock.iso_utc()
    await db.content.update_one({"id": cid}, {"$set": upd})
    if upd.get("status") and upd["status"] != old.get("status"):
        await log(db, "content", cid, "status", actor.id, old.get("status"), upd["status"])
    else:
        await log(db, "content", cid, "update", actor.id, note=", ".join(k for k in upd if k != "updatedAt"))
    if upd.get("requestId"):
        await services.sync_content(db, await services.get_request(db, upd["requestId"]))
    return await db.content.find_one({"id": cid}, NOPROJ)


@router.delete("/{cid}")
async def delete(cid: str, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _require_socmed(actor)
    old = await db.content.find_one({"id": cid}, NOPROJ)
    if not old:
        raise err(404, "Konten tidak ditemukan")
    if old.get("requestId"):
        await db.requests.update_one({"id": old["requestId"]}, {"$pull": {"contentItemIds": cid}})
    await db.content.delete_one({"id": cid})
    await log(db, "content", cid, "delete", actor.id, old.get("status"), None, old.get("idea") or "")
    return {"ok": True}


@router.post("/{cid}/create-brief")
async def create_brief(cid: str, body: BriefFromContent | None = None, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    item = await db.content.find_one({"id": cid}, NOPROJ)
    if not item:
        raise err(404, "Konten tidak ditemukan")
    if item.get("requestId"):
        raise err(400, "Konten ini sudah punya request produksi")
    extra = body.model_dump(exclude_unset=True) if body else {}
    goal = item.get("goal") if item.get("goal") in {"Reach", "Engagement", "Store Interest", "Conversion", "Retention"} else None
    data = {
        "title": (item.get("idea") or item.get("hook") or "Konten")[:80],
        "source": "Socmed",
        "funnelGoal": goal,
        "assetType": FORMAT_TO_ASSET.get(item.get("format"), "FEED"),
        "outputs": rules.outputs_from_content(item),
        "keyMessage": (item.get("idea") or "")[:140],
        "hook": item.get("hook") or "",
        "cta": item.get("cta") or "",
        "trackingCode": item.get("trackingCode") or "",
        "isPromo": bool(item.get("isPromo")),
        "gateStatus": item.get("gateStatus") or "NA",
        "gateRef": item.get("gateRef") or "",
        "notes": f"Dari kalender {item['date']} {item.get('platform')} {item.get('format')} · pillar {item.get('pillar')}",
    }
    data.update({k: v for k, v in extra.items() if v is not None})
    req = await services.create_request(db, actor, data)
    await db.requests.update_one({"id": req["id"]}, {"$set": {"contentItemIds": [cid]}})
    await db.content.update_one({"id": cid}, {"$set": {"requestId": req["id"], "updatedAt": clock.iso_utc()}})
    await log(db, "content", cid, "create-brief", actor.id, note=req["code"])
    return services.decorate(await services.get_request(db, req["id"]), await get_settings(db))
