from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from .. import clock
from ..constants import JOB_FUNCTIONS, role_for
from ..core import (
    get_db, err, slugify, hash_pin, check_pin, valid_pin, create_session, get_settings,
    require_actor, require_lead, require_approver, log, PRIVATE_MEMBER, Actor, lock_minutes,
)

router = APIRouter(prefix="/api")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    jobFunction: str
    email: str
    pin: str


class LoginIn(BaseModel):
    memberId: str
    pin: str


class PanelIn(BaseModel):
    pin: str


def _member_out(m: dict) -> dict:
    m = {k: v for k, v in m.items() if k not in {"_id", "pinHash", "pinSalt", "failedAttempts", "lockedUntil"}}
    m["role"] = role_for(m["jobFunction"])
    return m


@router.post("/auth/register")
async def register(body: RegisterIn, db=Depends(get_db)):
    if body.jobFunction not in JOB_FUNCTIONS:
        raise err(400, "Fungsi kerja tidak dikenal")
    if not valid_pin(body.pin):
        raise err(400, "PIN harus 4–6 angka")
    if "@" not in body.email:
        raise err(400, "Email tidak valid")
    mid = slugify(body.name)
    if await db.members.find_one({"id": mid}):
        raise err(409, "Nama sudah terdaftar. Pilih nama di daftar lalu masuk dengan PIN.")
    settings = await get_settings(db)
    h, salt = hash_pin(body.pin)
    m = {"id": mid, "name": body.name.strip(), "jobFunction": body.jobFunction, "email": body.email.strip(),
         "pinHash": h, "pinSalt": salt, "active": True, "capacity": settings.get("defaultCapacity", 6),
         "failedAttempts": 0, "lockedUntil": None, "createdAt": clock.iso_utc()}
    await db.members.insert_one(dict(m))
    token = await create_session(db, mid)
    await log(db, "member", mid, "register", mid)
    return {"token": token, "member": _member_out(m)}


@router.post("/auth/login")
async def login(body: LoginIn, db=Depends(get_db)):
    m = await db.members.find_one({"id": body.memberId})
    if not m or not m.get("active", True):
        raise err(404, "Anggota tidak ditemukan atau nonaktif")
    now = clock.now()
    if m.get("lockedUntil"):
        until = datetime.fromisoformat(m["lockedUntil"])
        if until > now:
            mins = int((until - now).total_seconds() // 60) + 1
            raise err(423, f"Terkunci karena 5x PIN salah. Coba lagi {mins} menit lagi atau minta Lead mereset PIN.")
    if not check_pin(body.pin, m["pinHash"], m["pinSalt"]):
        fails = int(m.get("failedAttempts", 0)) + 1
        upd = {"failedAttempts": fails}
        if fails >= 5:
            upd = {"failedAttempts": 0, "lockedUntil": (now + lock_minutes()).isoformat()}
            await db.members.update_one({"id": m["id"]}, {"$set": upd})
            raise err(423, "Terkunci 15 menit karena 5x PIN salah.")
        await db.members.update_one({"id": m["id"]}, {"$set": upd})
        raise err(401, f"PIN salah. Sisa percobaan: {5 - fails}", remaining=5 - fails)
    await db.members.update_one({"id": m["id"]}, {"$set": {"failedAttempts": 0, "lockedUntil": None}})
    token = await create_session(db, m["id"])
    return {"token": token, "member": _member_out(m)}


@router.post("/auth/panel-login")
async def panel_login(body: PanelIn, db=Depends(get_db)):
    s = await get_settings(db)
    if not check_pin(body.pin, s["panelPinHash"], s["panelPinSalt"]):
        raise err(401, "PIN panel salah")
    token = await create_session(db, "panel", panel=True)
    return {"token": token, "member": {"id": "panel", "name": "Panel Admin", "jobFunction": "Panel", "role": "approver"}}


@router.post("/auth/logout")
async def logout(actor: Actor = Depends(require_actor), db=Depends(get_db)):
    await db.sessions.delete_many({"memberId": actor.id})
    return {"ok": True}


@router.get("/auth/me")
async def me(actor: Actor = Depends(require_actor)):
    return dict(actor)


# ---------- Anggota ----------
class MemberUpdate(BaseModel):
    name: str | None = None
    jobFunction: str | None = None
    email: str | None = None
    capacity: int | None = Field(default=None, ge=1, le=30)
    active: bool | None = None


class ResetPin(BaseModel):
    pin: str


@router.get("/members")
async def list_members(db=Depends(get_db)):
    out = []
    async for m in db.members.find({}, PRIVATE_MEMBER).sort("name", 1):
        m["role"] = role_for(m["jobFunction"])
        out.append(m)
    return out


@router.put("/members/{mid}")
async def update_member(mid: str, body: MemberUpdate, actor: Actor = Depends(require_actor), db=Depends(get_db)):
    if not actor.is_lead and actor.id != mid:
        raise err(403, "Hanya Lead atau pemilik akun")
    upd = body.model_dump(exclude_unset=True)
    if "jobFunction" in upd and upd["jobFunction"] not in JOB_FUNCTIONS:
        raise err(400, "Fungsi kerja tidak dikenal")
    if not actor.is_lead:
        upd.pop("active", None)
        upd.pop("capacity", None)
        upd.pop("jobFunction", None)
    if not upd:
        raise err(400, "Tidak ada perubahan")
    r = await db.members.update_one({"id": mid}, {"$set": upd})
    if not r.matched_count:
        raise err(404, "Anggota tidak ditemukan")
    await log(db, "member", mid, "update", actor.id, to=upd)
    return await db.members.find_one({"id": mid}, PRIVATE_MEMBER)


@router.post("/members/{mid}/reset-pin")
async def reset_pin(mid: str, body: ResetPin, actor: Actor = Depends(require_lead), db=Depends(get_db)):
    if not valid_pin(body.pin):
        raise err(400, "PIN harus 4–6 angka")
    h, salt = hash_pin(body.pin)
    r = await db.members.update_one({"id": mid}, {"$set": {"pinHash": h, "pinSalt": salt, "failedAttempts": 0, "lockedUntil": None}})
    if not r.matched_count:
        raise err(404, "Anggota tidak ditemukan")
    await db.sessions.delete_many({"memberId": mid})
    await log(db, "member", mid, "reset-pin", actor.id)
    return {"ok": True}
