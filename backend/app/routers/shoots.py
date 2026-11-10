from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import clock, notify, services
from ..core import NOPROJ, Actor, err, get_db, log, new_id, require_actor

router = APIRouter(prefix="/api/shoots")


class ShootIn(BaseModel):
    date: str | None = None
    time: str | None = None
    location: str | None = None
    videographerId: str | None = None
    requestIds: list[str] | None = None
    equipmentChecklist: dict[str, bool] | None = None
    footageLog: str | None = None
    status: str | None = None
    notes: str | None = None


def _can_edit(actor: Actor, shoot: dict | None = None):
    if actor.is_lead or actor.role in {"creative", "socmed"}:
        return
    raise err(403, "Hanya tim kreatif / socmed / Lead")


async def _attach_requests(db, shoot: dict, actor: Actor):
    """Isi tanggal & lokasi shoot pada request yang ditautkan bila masih kosong."""
    for rid in shoot.get("requestIds") or []:
        r = await db.requests.find_one({"id": rid}, NOPROJ)
        if not r:
            raise err(400, f"Request tidak ditemukan: {rid}")
        upd = {}
        if not r.get("shootDate"):
            upd["shootDate"] = shoot["date"]
        if not r.get("picShootId") and shoot.get("videographerId"):
            upd["picShootId"] = shoot["videographerId"]
        if shoot.get("location") and not r.get("location"):
            upd["location"] = shoot["location"]
        if upd:
            await db.requests.update_one({"id": rid}, {"$set": upd})
            await log(db, "request", rid, "shoot-session", actor.id, note=shoot["date"])


@router.get("")
async def list_shoots(month: str | None = None, db=Depends(get_db)):
    q = {"date": {"$regex": f"^{month}"}} if month else {}
    out = []
    async for s in db.shoots.find(q, NOPROJ).sort([("date", 1), ("time", 1)]):
        s["requests"] = [{"id": r["id"], "code": r["code"], "title": r["title"], "status": r["status"], "assetType": r.get("assetType")}
                         async for r in db.requests.find({"id": {"$in": s.get("requestIds", [])}}, NOPROJ)]
        out.append(s)
    return out


@router.post("")
async def create(body: ShootIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _can_edit(actor)
    d = body.model_dump(exclude_unset=True)
    if not d.get("date"):
        raise err(400, "Tanggal shoot wajib diisi")
    shoot = {"id": new_id("s"), "date": d["date"], "time": d.get("time") or "", "location": d.get("location") or "",
             "videographerId": d.get("videographerId"), "requestIds": d.get("requestIds") or [],
             "equipmentChecklist": d.get("equipmentChecklist") or {}, "footageLog": d.get("footageLog") or "",
             "status": "Rencana", "notes": d.get("notes") or "", "createdAt": clock.iso_utc()}
    await _attach_requests(db, shoot, actor)
    await db.shoots.insert_one(dict(shoot))
    await log(db, "shoot", shoot["id"], "create", actor.id, note=shoot["date"])
    if shoot.get("videographerId"):
        await notify.event(db, [shoot["videographerId"]], f"Jadwal shoot {shoot['date']} di {shoot['location']}",
                           [f"{len(shoot['requestIds'])} request ditautkan."])
    return shoot


@router.put("/{sid}")
async def update(sid: str, body: ShootIn, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _can_edit(actor)
    s = await db.shoots.find_one({"id": sid}, NOPROJ)
    if not s:
        raise err(404, "Sesi shoot tidak ditemukan")
    upd = body.model_dump(exclude_unset=True)
    if upd.get("status") and upd["status"] not in {"Rencana", "Selesai", "Batal"}:
        raise err(400, "Status shoot tidak valid")
    s.update(upd)
    await _attach_requests(db, s, actor)
    await db.shoots.update_one({"id": sid}, {"$set": upd})
    await log(db, "shoot", sid, "update", actor.id)
    return await db.shoots.find_one({"id": sid}, NOPROJ)


@router.post("/{sid}/complete")
async def complete(sid: str, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    _can_edit(actor)
    s = await db.shoots.find_one({"id": sid}, NOPROJ)
    if not s:
        raise err(404, "Sesi shoot tidak ditemukan")
    moved = []
    for rid in s.get("requestIds", []):
        r = await db.requests.find_one({"id": rid}, NOPROJ)
        if r and r["status"] == "Shoot":
            await services.transition(db, actor, rid, "Produksi", f"Shoot {s['date']} selesai", _system=True)
            moved.append(r["code"])
    await db.shoots.update_one({"id": sid}, {"$set": {"status": "Selesai", "completedAt": clock.iso_utc()}})
    await log(db, "shoot", sid, "complete", actor.id, note=", ".join(moved))
    return {"ok": True, "moved": moved}
