from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from .. import clock, rules, services
from ..constants import QC_KEYS, REQUEST_STATUSES, CLOSED_STATUSES
from ..core import NOPROJ, Actor, err, get_db, get_settings, log, require_actor, require_approver

router = APIRouter(prefix="/api/requests")


class OutputIn(BaseModel):
    format: str = ""
    ratio: str = ""
    size: str = ""
    duration: str = ""
    platform: str = "IG"
    done: bool = False
    fileLink: str = ""
    finalFileName: str = ""


class RequestIn(BaseModel):
    title: str | None = None
    source: str | None = None
    funnelGoal: str | None = None
    assetType: str | None = None
    outputs: list[OutputIn] | None = None
    keyMessage: str | None = None
    hook: str | None = None
    heroProduct: str | None = None
    supportingSkus: str | None = None
    talent: str | None = None
    props: str | None = None
    location: str | None = None
    shootDate: str | None = None
    shootTime: str | None = None
    mood: str | None = None
    referenceLinks: list[str] | None = None
    mandatoryText: str | None = None
    mandatoryTextSource: str | None = None
    cta: str | None = None
    trackingCode: str | None = None
    isPromo: bool | None = None
    isBudgeted: bool | None = None
    budget: int | None = None
    gateStatus: str | None = None
    gateRef: str | None = None
    priority: str | None = None
    picShootId: str | None = None
    picDesignId: str | None = None
    picEditId: str | None = None
    reviewerId: str | None = None
    requestedDeadline: str | None = None
    driveFolderLink: str | None = None
    finalFileNames: list[str] | None = None
    notes: str | None = None
    deadlineDraft: str | None = None
    deadlineFinal: str | None = None
    deadlineChangeReason: str | None = None


class TransitionIn(BaseModel):
    to: str
    note: str = ""
    confirm: bool = False


class NoteIn(BaseModel):
    text: str
    timecodes: str = ""


class QcIn(BaseModel):
    as_: Literal["maker", "reviewer"] = Field(alias="as")
    items: dict[str, bool] | None = None

    model_config = {"populate_by_name": True}


class ApproveIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = ""


class OutputUpdate(BaseModel):
    done: bool | None = None
    fileLink: str | None = None
    finalFileName: str | None = None


def _dump(m: BaseModel) -> dict:
    d = m.model_dump(exclude_unset=True)
    if "outputs" in d and d["outputs"] is not None:
        d["outputs"] = [dict(o) for o in d["outputs"]]
    return d


@router.get("")
async def list_requests(status: str | None = None, pic: str | None = None, type: str | None = None,
                        source: str | None = None, location: str | None = None,
                        from_: str | None = Query(None, alias="from"), to: str | None = None,
                        overdue: bool = False, mine: str | None = None, includeClosed: bool = True,
                        db=Depends(get_db)):
    q: dict = {}
    if status:
        q["status"] = {"$in": status.split(",")}
    elif not includeClosed:
        q["status"] = {"$nin": ["Ditolak", "Batal"]}
    if pic:
        q["$or"] = [{k: pic} for k in services.PIC_FIELDS] + [{"reviewerId": pic}]
    if mine:
        q["$or"] = [{k: mine} for k in services.PIC_FIELDS] + [{"reviewerId": mine}, {"requesterId": mine}]
    if type:
        q["assetType"] = {"$in": type.split(",")}
    if source:
        q["source"] = source
    if location:
        q["location"] = location
    if from_ or to:
        rng = {}
        if from_:
            rng["$gte"] = from_
        if to:
            rng["$lte"] = to + "T99"
        q["createdAt"] = rng
    settings = await get_settings(db)
    out = []
    async for r in db.requests.find(q, NOPROJ).sort("createdAt", -1):
        d = services.decorate(r, settings)
        if overdue and not d["overdue"]:
            continue
        out.append(d)
    return out


@router.get("/summary")
async def summary(db=Depends(get_db)):
    settings = await get_settings(db)
    today = clock.today()
    week_start = clock.add_days(today, -(today.isoweekday() - 1)).isoformat()
    d30 = clock.add_days(today, -30).isoformat()
    reqs = [services.decorate(r, settings) async for r in db.requests.find({}, NOPROJ)]
    active = [r for r in reqs if r["status"] not in CLOSED_STATUSES and r["status"] not in {"Brief Masuk", "Ditahan Gate"}]
    delivered30 = [r for r in reqs if r.get("handoverAt") and r["handoverAt"][:10] >= d30]
    ontime = [r for r in delivered30 if r.get("deadlineFinal") and _local_date(r["handoverAt"]) <= r["deadlineFinal"]]
    closed30 = [r for r in reqs if r["status"] in {"Final", "Diserahkan"} and (r.get("finalAt") or r.get("updatedAt", ""))[:10] >= d30]
    return {
        "aktif": len(active),
        "overdue": sum(1 for r in reqs if r["overdue"]),
        "atRisk": sum(1 for r in reqs if r["atRisk"]),
        "review": sum(1 for r in reqs if r["status"] == "Review"),
        "approval": sum(1 for r in reqs if r["status"] == "Approval"),
        "ditahanGate": sum(1 for r in reqs if r["status"] == "Ditahan Gate"),
        "briefMasuk": sum(1 for r in reqs if r["status"] == "Brief Masuk"),
        "selesaiMingguIni": sum(1 for r in reqs if r.get("handoverAt") and _local_date(r["handoverAt"]) >= week_start),
        "onTimePct": round(len(ontime) * 100 / len(delivered30)) if delivered30 else None,
        "avgRevisi": round(sum(r.get("revisionRound", 0) for r in closed30) / len(closed30), 2) if closed30 else None,
    }


def _local_date(iso: str) -> str:
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso).astimezone(clock.WIB).date().isoformat()
    except ValueError:
        return iso[:10]


@router.post("")
async def create(body: RequestIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    req = await services.create_request(db, actor, _dump(body))
    return services.decorate(req, await get_settings(db))


@router.get("/{rid}")
async def detail(rid: str, db=Depends(get_db)):
    req = await services.get_request(db, rid)
    settings = await get_settings(db)
    notes = [n async for n in db.revisionnotes.find({"requestId": req["id"]}, NOPROJ).sort("createdAt", 1)]
    items = [i async for i in db.content.find({"id": {"$in": req.get("contentItemIds", [])}}, NOPROJ)]
    logs = [l async for l in db.activitylog.find({"entity": "request", "entityId": req["id"]}, NOPROJ).sort("at", -1)]
    children = [{"id": c["id"], "code": c["code"], "status": c["status"]}
                async for c in db.requests.find({"parentRequestId": req["id"]}, NOPROJ)]
    parent = None
    if req.get("parentRequestId"):
        p = await db.requests.find_one({"id": req["parentRequestId"]}, NOPROJ)
        parent = {"id": p["id"], "code": p["code"], "status": p["status"]} if p else None
    return {**services.decorate(req, settings), "revisionNotes": notes, "contentItems": items, "log": logs,
            "children": children, "parent": parent}


@router.put("/{rid}")
async def update(rid: str, body: RequestIn, confirm: bool = False, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    req = await services.update_request(db, actor, rid, _dump(body), confirm=confirm)
    return services.decorate(req, await get_settings(db))


@router.post("/{rid}/transition")
async def transition(rid: str, body: TransitionIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    if body.to not in REQUEST_STATUSES:
        raise err(400, "Status tidak dikenal")
    req = await services.transition(db, actor, rid, body.to, body.note, body.confirm)
    return services.decorate(req, await get_settings(db))


@router.post("/{rid}/revision-notes")
async def add_note(rid: str, body: NoteIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    req = await services.get_request(db, rid)
    return await services.add_revision_note(db, actor, req, body.text, body.timecodes)


@router.post("/{rid}/revision-notes/{nid}/resolve")
async def resolve_note(rid: str, nid: str, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    r = await db.revisionnotes.update_one({"id": nid, "requestId": rid}, {"$set": {"resolved": True, "resolvedBy": actor.id, "resolvedAt": clock.iso_utc()}})
    if not r.matched_count:
        raise err(404, "Catatan tidak ditemukan")
    return {"ok": True}


@router.put("/{rid}/qc")
async def qc(rid: str, body: QcIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    req = await services.get_request(db, rid)
    if req["status"] not in {"Produksi", "Review", "Revisi", "Approval"}:
        raise err(400, f"QC tidak bisa diubah saat status {req['status']}")
    qc_ = dict(req.get("qc") or {"items": {}})
    items = dict(qc_.get("items") or {})
    if body.as_ == "maker":
        if actor.id not in services.pics(req) and not actor.is_lead:
            raise err(403, "Hanya PIC pembuat aset yang mencentang QC pembuat")
        for k, v in (body.items or {}).items():
            if k in QC_KEYS:
                items[k] = bool(v)
        qc_["items"] = items
        qc_["qcByMaker"] = actor.id if rules.qc_complete(qc_) else None
        qc_["qcByReviewer"] = None
    else:
        if not (actor.id == req.get("reviewerId") or actor.is_lead):
            raise err(403, "Hanya reviewer atau Lead yang mengonfirmasi QC")
        if not rules.qc_complete(qc_) or not qc_.get("qcByMaker"):
            done = sum(1 for k in QC_KEYS if items.get(k))
            raise err(400, f"QC pembuat belum lengkap ({done}/9)")
        if qc_["qcByMaker"] == actor.id:
            raise err(400, "Reviewer QC harus berbeda dari pembuat")
        qc_["qcByReviewer"] = actor.id
        qc_["qcAt"] = clock.iso_utc()
    await db.requests.update_one({"id": req["id"]}, {"$set": {"qc": qc_, "updatedAt": clock.iso_utc()}})
    await log(db, "request", req["id"], f"qc-{body.as_}", actor.id, note=f"{sum(1 for k in QC_KEYS if items.get(k))}/9")
    return services.decorate(await services.get_request(db, req["id"]), await get_settings(db))


@router.post("/{rid}/approve")
async def approve(rid: str, body: ApproveIn, actor: Actor = Depends(require_approver), db=Depends(get_db)):
    req = await services.get_request(db, rid)
    if req["status"] != "Approval":
        raise err(400, "Request belum di tahap Approval")
    if body.decision == "approve":
        await db.requests.update_one({"id": req["id"]}, {"$set": {"approval": {
            **req["approval"], "by": actor.id, "byName": actor.get("name"), "at": clock.iso_utc(), "note": body.note}}})
        await log(db, "request", req["id"], "approve", actor.id, note=body.note)
        new = await services.transition(db, actor, req["id"], "Final", body.note)
    else:
        if not body.note.strip():
            raise err(400, "Alasan penolakan approval wajib diisi")
        await log(db, "request", req["id"], "reject-approval", actor.id, note=body.note)
        new = await services.transition(db, actor, req["id"], "Revisi", body.note)
    return services.decorate(new, await get_settings(db))


@router.post("/{rid}/clone-as-new-brief")
async def clone(rid: str, body: RequestIn | None = None, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    new = await services.clone_as_new_brief(db, actor, rid, _dump(body) if body else {})
    return services.decorate(new, await get_settings(db))


@router.put("/{rid}/outputs/{idx}")
async def update_output(rid: str, idx: int, body: OutputUpdate, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    req = await services.get_request(db, rid)
    if actor.id not in services.pics(req) and not actor.is_lead:
        raise err(403, "Hanya PIC atau Lead")
    outs = req.get("outputs") or []
    if not 0 <= idx < len(outs):
        raise err(404, "Output tidak ditemukan")
    o = dict(outs[idx])
    o.update(body.model_dump(exclude_unset=True))
    if o.get("done") and not (o.get("fileLink") or "").strip():
        raise err(400, "Output selesai wajib punya link file")
    outs[idx] = o
    await db.requests.update_one({"id": req["id"]}, {"$set": {"outputs": outs, "updatedAt": clock.iso_utc()}})
    await log(db, "request", req["id"], "output", actor.id, note=f"{o['format']}: {'selesai' if o.get('done') else 'belum'}")
    return services.decorate(await services.get_request(db, req["id"]), await get_settings(db))
