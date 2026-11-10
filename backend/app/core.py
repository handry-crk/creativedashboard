"""Akses database, sesi login, izin, settings, log, dan helper umum."""
import hashlib
import secrets
import re
from datetime import timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request

from . import clock
from .constants import DEFAULT_SETTINGS, role_for

NOPROJ = {"_id": 0}
PRIVATE_MEMBER = {"_id": 0, "pinHash": 0, "pinSalt": 0, "failedAttempts": 0, "lockedUntil": 0}


def get_db(request: Request):
    return request.app.state.db


def err(status: int, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"message": message, **extra})


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or secrets.token_hex(3)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{secrets.token_hex(6)}"


# ---------- PIN ----------
def hash_pin(pin: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 100_000).hex()
    return h, salt


def check_pin(pin: str, h: str, salt: str) -> bool:
    return secrets.compare_digest(hash_pin(pin, salt)[0], h or "")


def valid_company_email(email: str) -> bool:
    from .config import config
    e = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", e):
        return False
    return e.rsplit("@", 1)[1] in config.ALLOWED_EMAIL_DOMAINS


def valid_pin(pin: str) -> bool:
    return bool(re.fullmatch(r"\d{4,6}", pin or ""))


# ---------- Settings ----------
async def get_settings(db) -> dict:
    s = await db.settings.find_one({"id": "settings"}, NOPROJ)
    if not s:
        s = dict(DEFAULT_SETTINGS)
        h, salt = hash_pin("1234")
        s["panelPinHash"], s["panelPinSalt"] = h, salt
        await db.settings.insert_one(dict(s))
        s.pop("_id", None)
    else:
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, v)
    return s


def public_settings(s: dict) -> dict:
    return {k: v for k, v in s.items() if k not in {"panelPinHash", "panelPinSalt"}}


# ---------- Sesi ----------
class Actor(dict):
    @property
    def id(self) -> str:
        return self["id"]

    @property
    def role(self) -> str:
        return self["role"]

    @property
    def is_approver(self) -> bool:
        return self["role"] == "approver"

    @property
    def is_member_approver(self) -> bool:
        """Marketing Manager / Brand Manager (akun sungguhan, bukan PIN panel)."""
        from .constants import MEMBER_APPROVER_FUNCTIONS
        return self["id"] != "panel" and self.get("jobFunction") in MEMBER_APPROVER_FUNCTIONS

    @property
    def is_lead(self) -> bool:
        """Creative Lead, Approver (override), atau panel."""
        return self["role"] in {"approver", "creative_lead"}

    @property
    def is_socmed(self) -> bool:
        return self["role"] == "socmed" or self.is_lead


async def create_session(db, member_id: str, panel: bool = False) -> str:
    token = secrets.token_urlsafe(32)
    await db.sessions.insert_one({"token": token, "memberId": member_id, "panel": panel,
                                  "createdAt": clock.iso_utc()})
    return token


async def actor_from_request(request: Request) -> Actor | None:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token:
        return None
    db = request.app.state.db
    s = await db.sessions.find_one({"token": token})
    if not s:
        return None
    if s.get("panel"):
        return Actor(id="panel", name="Panel Admin", jobFunction="Panel", role="approver", email="")
    m = await db.members.find_one({"id": s["memberId"]}, PRIVATE_MEMBER)
    if not m or not m.get("active", True) or m.get("approval", "approved") != "approved":
        return None
    m["role"] = role_for(m["jobFunction"])
    return Actor(m)


async def optional_actor(request: Request) -> Actor | None:
    return await actor_from_request(request)


async def require_actor(request: Request) -> Actor:
    a = await actor_from_request(request)
    if not a:
        raise err(401, "Silakan masuk dulu (mode Lihat saja tidak bisa mengubah data)")
    return a


async def require_member_approver(actor: Actor = Depends(require_actor)) -> Actor:
    if not actor.is_member_approver:
        raise err(403, "Hanya Marketing Manager / Brand Manager")
    return actor


async def require_lead(actor: Actor = Depends(require_actor)) -> Actor:
    if not actor.is_lead:
        raise err(403, "Hanya Creative Lead / Approver")
    return actor


async def require_approver(actor: Actor = Depends(require_actor)) -> Actor:
    if not actor.is_approver:
        raise err(403, "Hanya Approver (Brand Lead / Marketing Lead / Manager)")
    return actor


# ---------- Log ----------
async def log(db, entity: str, entity_id: str, action: str, by: str, frm: Any = None, to: Any = None, note: str = ""):
    await db.activitylog.insert_one({"entity": entity, "entityId": entity_id, "action": action, "from": frm,
                                     "to": to, "byId": by, "note": note, "at": clock.iso_utc()})


async def members_map(db) -> dict:
    out = {}
    async for m in db.members.find({"approval": {"$nin": ["pending", "rejected"]}}, PRIVATE_MEMBER):
        m["role"] = role_for(m["jobFunction"])
        out[m["id"]] = m
    return out


def lock_minutes() -> timedelta:
    return timedelta(minutes=15)
