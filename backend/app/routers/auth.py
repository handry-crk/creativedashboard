from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import clock, notify
from ..config import config
from ..constants import JOB_FUNCTIONS, MEMBER_APPROVER_FUNCTIONS, role_for
from ..core import (
    get_db, err, slugify, hash_pin, check_pin, valid_pin, valid_company_email, create_session, get_settings,
    require_actor, require_lead, require_member_approver, log, PRIVATE_MEMBER, Actor, lock_minutes,
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


def _domain_text() -> str:
    return " / ".join("@" + d for d in config.ALLOWED_EMAIL_DOMAINS)


async def _manager_emails(db) -> list[str]:
    return [m["email"] async for m in db.members.find(
        {"jobFunction": {"$in": list(MEMBER_APPROVER_FUNCTIONS)}, "active": True, "approval": "approved"}, {"email": 1, "_id": 0})]


@router.post("/auth/register")
async def register(body: RegisterIn, db=Depends(get_db)):
    if body.jobFunction not in JOB_FUNCTIONS:
        raise err(400, "Fungsi kerja tidak dikenal")
    if not valid_pin(body.pin):
        raise err(400, "PIN harus 4–6 angka")
    if not valid_company_email(body.email):
        raise err(400, f"Pendaftaran hanya untuk email kantor {_domain_text()}")
    email = body.email.strip().lower()
    mid = slugify(body.name)
    existing = await db.members.find_one({"id": mid})
    if existing and existing.get("approval") == "rejected":
        await db.members.delete_one({"id": mid})  # boleh daftar ulang setelah ditolak
    elif existing:
        raise err(409, "Nama sudah terdaftar. Pilih nama di daftar lalu masuk dengan PIN, atau tunggu persetujuan.")
    if await db.members.find_one({"email": email, "approval": {"$ne": "rejected"}}):
        raise err(409, "Email sudah terdaftar")
    settings = await get_settings(db)
    # Bootstrap: Marketing/Brand Manager pertama disetujui otomatis bila belum ada manager yang aktif.
    has_manager = await db.members.count_documents(
        {"jobFunction": {"$in": list(MEMBER_APPROVER_FUNCTIONS)}, "active": True, "approval": "approved"})
    auto = body.jobFunction in MEMBER_APPROVER_FUNCTIONS and has_manager == 0
    h, salt = hash_pin(body.pin)
    m = {"id": mid, "name": body.name.strip(), "jobFunction": body.jobFunction, "email": email,
         "pinHash": h, "pinSalt": salt, "active": True, "capacity": settings.get("defaultCapacity", 6),
         "failedAttempts": 0, "lockedUntil": None, "createdAt": clock.iso_utc(),
         "approval": "approved" if auto else "pending", "approvedBy": "bootstrap" if auto else None, "approvedAt": clock.iso_utc() if auto else None}
    await db.members.insert_one(dict(m))
    await log(db, "member", mid, "register", mid, to=m["approval"])
    if auto:
        token = await create_session(db, mid)
        return {"token": token, "member": _member_out(m), "pending": False}
    await notify.send(db, await _manager_emails(db), f"Pendaftaran baru menunggu persetujuan: {m['name']}",
                      notify.layout("Pendaftaran baru", f"<p><b>{m['name']}</b> ({m['jobFunction']}, {email}) mendaftar ke Creative Hub.</p>"
                                    "<p>Setujui atau tolak di menu Pengaturan → Persetujuan anggota.</p>", path="/?tab=pengaturan"), "member-approval")
    return {"pending": True, "message": "Pendaftaran terkirim. Akun aktif setelah disetujui Marketing Manager atau Brand Manager."}


@router.post("/auth/login")
async def login(body: LoginIn, db=Depends(get_db)):
    m = await db.members.find_one({"id": body.memberId})
    if not m or not m.get("active", True):
        raise err(404, "Anggota tidak ditemukan atau nonaktif")
    if m.get("approval", "approved") == "pending":
        raise err(403, "Akun menunggu persetujuan Marketing Manager / Brand Manager")
    if m.get("approval") == "rejected":
        raise err(403, "Pendaftaran ditolak. Hubungi Marketing Manager / Brand Manager.")
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
    async for m in db.members.find({"approval": {"$nin": ["pending", "rejected"]}}, PRIVATE_MEMBER).sort("name", 1):
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
    if "email" in upd:
        if not valid_company_email(upd["email"]):
            raise err(400, f"Email harus memakai domain kantor {_domain_text()}")
        upd["email"] = upd["email"].strip().lower()
    target = await db.members.find_one({"id": mid}, PRIVATE_MEMBER)
    if not target:
        raise err(404, "Anggota tidak ditemukan")
    # Ganti fungsi kerja = ganti hak akses -> hanya Marketing/Brand Manager
    if "jobFunction" in upd and upd["jobFunction"] != target["jobFunction"] and not actor.is_member_approver:
        raise err(403, "Perubahan fungsi kerja hanya oleh Marketing Manager / Brand Manager")
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


# ---------- Persetujuan pendaftaran (Marketing Manager / Brand Manager) ----------
class DecisionIn(BaseModel):
    note: str = ""


@router.get("/members/pending")
async def pending_members(actor: Actor = Depends(require_member_approver), db=Depends(get_db)):
    return [m async for m in db.members.find({"approval": "pending"}, PRIVATE_MEMBER).sort("createdAt", 1)]


async def _decide(db, actor: Actor, mid: str, decision: str, note: str):
    m = await db.members.find_one({"id": mid}, PRIVATE_MEMBER)
    if not m:
        raise err(404, "Anggota tidak ditemukan")
    if m.get("approval") != "pending":
        raise err(400, "Pendaftaran ini sudah diputuskan")
    await db.members.update_one({"id": mid}, {"$set": {"approval": decision, "approvedBy": actor.id,
                                                        "approvedAt": clock.iso_utc(), "approvalNote": note}})
    await log(db, "member", mid, f"member-{decision}", actor.id, note=note)
    ok = decision == "approved"
    await notify.send(db, [m["email"]], "Akun Creative Hub " + ("disetujui" if ok else "ditolak"),
                      notify.layout("Akun disetujui" if ok else "Pendaftaran ditolak",
                                    f"<p>Halo {m['name']}, " + ("akun Anda sudah aktif. Masuk dengan nama dan PIN Anda.</p>" if ok
                                                                 else f"pendaftaran Anda ditolak oleh {actor.get('name')}.</p><p>{note}</p>")),
                      "member-decision")
    m = await db.members.find_one({"id": mid}, PRIVATE_MEMBER)
    m["role"] = role_for(m["jobFunction"])
    return m


@router.post("/members/{mid}/approve")
async def approve_member(mid: str, body: DecisionIn | None = None, actor: Actor = Depends(require_member_approver), db=Depends(get_db)):
    return await _decide(db, actor, mid, "approved", body.note if body else "")


@router.post("/members/{mid}/reject")
async def reject_member(mid: str, body: DecisionIn | None = None, actor: Actor = Depends(require_member_approver), db=Depends(get_db)):
    return await _decide(db, actor, mid, "rejected", body.note if body else "")
