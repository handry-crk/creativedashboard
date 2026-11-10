from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import clock, jobs, services
from ..constants import (
    ASSET_TYPES, CONTENT_GOALS, CONTENT_STATUSES, FORMATS, FUNNEL_GOALS, GATE_STATUSES, JOB_FUNCTIONS, PILLARS,
    PLATFORMS, PRIORITIES, QC_KEYS, QC_LABELS, REQUEST_STATUSES, SOURCES,
)
from ..core import (
    NOPROJ, Actor, err, get_db, get_settings, hash_pin, log, optional_actor, public_settings, require_lead, valid_pin,
)

router = APIRouter(prefix="/api")


@router.get("/meta")
async def meta():
    return {
        "jobFunctions": list(JOB_FUNCTIONS), "sources": SOURCES, "funnelGoals": FUNNEL_GOALS, "assetTypes": ASSET_TYPES,
        "gateStatuses": GATE_STATUSES, "priorities": PRIORITIES, "requestStatuses": REQUEST_STATUSES,
        "qc": [{"key": k, "label": l} for k, l in zip(QC_KEYS, QC_LABELS)], "platforms": PLATFORMS, "formats": FORMATS,
        "pillars": PILLARS, "contentGoals": CONTENT_GOALS, "contentStatuses": CONTENT_STATUSES,
    }


@router.get("/state")
async def state(actor: Actor | None = Depends(optional_actor), db=Depends(get_db)):
    s = await get_settings(db)
    members = []
    async for m in db.members.find({"approval": {"$nin": ["pending", "rejected"]}}, {"_id": 0, "pinHash": 0, "pinSalt": 0, "failedAttempts": 0, "lockedUntil": 0}).sort("name", 1):
        from ..constants import role_for
        m["role"] = role_for(m["jobFunction"])
        members.append(m)
    pending = await db.members.count_documents({"approval": "pending"}) if actor and actor.is_member_approver else 0
    from ..config import config
    return {"me": {**dict(actor), "canApproveMembers": actor.is_member_approver} if actor else None, "settings": public_settings(s),
            "members": members, "pendingMembers": pending, "allowedDomains": config.ALLOWED_EMAIL_DOMAINS,
            "today": clock.today_str(), "now": clock.now().isoformat()}


@router.get("/workload")
async def workload(db=Depends(get_db)):
    return await services.workload(db)


@router.get("/log")
async def activity_log(entity: str | None = None, id: str | None = None, limit: int = 100, db=Depends(get_db)):
    q = {}
    if entity:
        q["entity"] = entity
    if id:
        q["entityId"] = id
    return [l async for l in db.activitylog.find(q, NOPROJ).sort("at", -1).limit(min(limit, 500))]


class SettingsIn(BaseModel):
    slaTable: dict | None = None
    workDays: list[int] | None = None
    holidays: list[str] | None = None
    pillarTargets: dict[str, float] | None = None
    monthOverrides: dict | None = None
    weekThemes: dict[str, str] | None = None
    postingWindows: list[str] | None = None
    maxPromoPerDay: int | None = None
    reactiveSlotPct: int | None = None
    locations: list[str] | None = None
    trackingCodes: list[str] | None = None
    equipmentChecklist: list[str] | None = None
    defaultCapacity: int | None = None
    adminEmail: str | None = None
    creativeLeadFallback: str | None = None
    digestTime: str | None = None
    deadlineTime: str | None = None
    approvalTime: str | None = None
    weeklyDay: int | None = None
    weeklyTime: str | None = None
    appUrl: str | None = None
    newPanelPin: str | None = None


@router.put("/settings")
async def put_settings(body: SettingsIn, actor: Actor = Depends(require_lead), db=Depends(get_db)):
    await get_settings(db)
    upd = body.model_dump(exclude_unset=True)
    pin = upd.pop("newPanelPin", None)
    if pin:
        if not valid_pin(pin):
            raise err(400, "PIN panel harus 4–6 angka")
        upd["panelPinHash"], upd["panelPinSalt"] = hash_pin(pin)
    if "pillarTargets" in upd and round(sum(upd["pillarTargets"].values())) != 100:
        raise err(400, "Total target pillar harus 100%")
    for m, t in (upd.get("monthOverrides") or {}).items():
        if t and round(sum(t.values())) != 100:
            raise err(400, f"Total target pillar {m} harus 100%")
    if not upd:
        raise err(400, "Tidak ada perubahan")
    await db.settings.update_one({"id": "settings"}, {"$set": upd})
    await log(db, "settings", "settings", "update", actor.id, note=", ".join(upd))
    return public_settings(await get_settings(db))


@router.post("/jobs/{name}/run")
async def run_job(name: str, actor: Actor = Depends(require_lead), db=Depends(get_db)):
    fn = {"digest": jobs.digest, "deadline": jobs.deadline_reminder, "approval": jobs.approval_reminder,
          "weekly": jobs.weekly_recap, "backup": jobs.backup}.get(name)
    if not fn:
        raise err(404, "Job tidak dikenal")
    result = await fn(db, force=True)
    await log(db, "job", name, "run-manual", actor.id, note=str(result))
    return {"ok": True, "result": result}


@router.get("/emaillog")
async def email_log(limit: int = 50, actor: Actor = Depends(require_lead), db=Depends(get_db)):
    return [e async for e in db.emaillog.find({}, NOPROJ).sort("at", -1).limit(min(limit, 200))]


@router.post("/demo-data")
async def demo_data(actor: Actor = Depends(require_lead), db=Depends(get_db)):
    from ..demo import seed
    return await seed(db, actor)
