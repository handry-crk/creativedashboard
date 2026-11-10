"""Logika request produksi yang dipakai beberapa router."""
from . import clock, notify, rules
from .constants import (
    ACTIVE_STATUSES, ASSET_TYPES, CLOSED_STATUSES, FUNNEL_GOALS, GATE_OK, GATE_STATUSES, LOCKED_BRIEF,
    PRIORITIES, SOURCES, TRANSITIONS, CONTENT_STATUSES, QC_KEYS,
)
from .core import NOPROJ, Actor, err, get_settings, log, members_map, new_id

BRIEF_FIELDS = [
    "title", "source", "funnelGoal", "assetType", "outputs", "keyMessage", "hook", "heroProduct", "supportingSkus",
    "talent", "props", "location", "shootDate", "shootTime", "mood", "referenceLinks", "mandatoryText",
    "mandatoryTextSource", "cta", "trackingCode", "isPromo", "isBudgeted", "budget", "gateStatus", "gateRef",
    "priority", "picShootId", "picDesignId", "picEditId", "reviewerId", "requestedDeadline", "driveFolderLink",
    "finalFileNames", "notes",
]
LOCKED_FIELDS = ["keyMessage", "outputs", "mandatoryText"]
PIC_FIELDS = ["picShootId", "picDesignId", "picEditId"]


def pics(req: dict) -> list[str]:
    return sorted({req.get(k) for k in PIC_FIELDS if req.get(k)})


def validate_enums(d: dict):
    checks = [("source", SOURCES), ("funnelGoal", FUNNEL_GOALS), ("assetType", ASSET_TYPES),
              ("gateStatus", GATE_STATUSES), ("priority", PRIORITIES)]
    for f, allowed in checks:
        if d.get(f) not in (None, "") and d[f] not in allowed:
            raise err(400, f"Nilai {f} tidak valid: {d[f]}")
    if d.get("keyMessage") and len(d["keyMessage"].strip()) > 140:
        raise err(400, "Key message maks. 140 karakter")


def normalize_outputs(outputs) -> list[dict]:
    out = []
    for o in outputs or []:
        o = dict(o)
        out.append({"format": o.get("format", ""), "ratio": o.get("ratio", ""), "size": o.get("size", ""),
                    "duration": o.get("duration", ""), "platform": o.get("platform", "IG"),
                    "done": bool(o.get("done", False)), "fileLink": o.get("fileLink", ""),
                    "finalFileName": o.get("finalFileName", "")})
    return out


def check_promo_text(req: dict):
    if req.get("isPromo"):
        if not (req.get("mandatoryText") or "").strip():
            raise err(400, "Aset promo wajib mengisi teks wajib (harga, periode, kuota, outlet, syarat)")
        if not (req.get("mandatoryTextSource") or "").strip():
            raise err(400, "Angka promo wajib punya sumber (kode Gate / dokumen)")


async def next_code(db) -> str:
    n = clock.now()
    prefix = f"CR-{n:%y%m}-"
    last = 0
    async for r in db.requests.find({"code": {"$regex": f"^{prefix}"}}, {"code": 1}):
        try:
            last = max(last, int(r["code"].split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


async def lead_ids(db) -> list[str]:
    s = await get_settings(db)
    cls = [m["id"] async for m in db.members.find({"jobFunction": "Creative Lead", "active": True, "approval": {"$nin": ["pending", "rejected"]}}, {"id": 1})]
    if cls:
        return cls
    return [m["id"] async for m in db.members.find({"jobFunction": s.get("creativeLeadFallback", "Brand Lead"), "active": True, "approval": {"$nin": ["pending", "rejected"]}}, {"id": 1})]


async def approver_ids(db) -> list[str]:
    from .constants import APPROVER_FUNCTIONS
    return [m["id"] async for m in db.members.find({"jobFunction": {"$in": list(APPROVER_FUNCTIONS)}, "active": True, "approval": {"$nin": ["pending", "rejected"]}}, {"id": 1})]


async def active_count(db, member_id: str, exclude_id: str | None = None) -> int:
    q = {"status": {"$in": list(ACTIVE_STATUSES)}, "$or": [{k: member_id} for k in PIC_FIELDS]}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    return await db.requests.count_documents(q)


async def capacity_warnings(db, req: dict, pic_ids: list[str]) -> list[dict]:
    mm = await members_map(db)
    s = await get_settings(db)
    out = []
    for pid in pic_ids:
        m = mm.get(pid)
        if not m:
            raise err(400, f"PIC tidak ditemukan: {pid}")
        cap = m.get("capacity") or s.get("defaultCapacity", 6)
        n = await active_count(db, pid, exclude_id=req.get("id"))
        if n >= cap:
            out.append({"memberId": pid, "name": m["name"], "active": n, "capacity": cap,
                        "message": f"{m['name']} sudah memegang {n} tugas aktif (kapasitas {cap})"})
    return out


def decorate(req: dict, settings: dict) -> dict:
    req = dict(req)
    req.pop("_id", None)
    req.update(rules.deadline_flags(req, settings))
    req["approvalRequired"] = rules.approval_required(req)
    req["qcComplete"] = rules.qc_complete(req.get("qc"))
    req["suggestedFileNames"] = [rules.suggest_filename(req, o) for o in req.get("outputs", [])]
    names = [o.get("finalFileName", "") for o in req.get("outputs", [])] + (req.get("finalFileNames") or [])
    req["fileNameWarnings"] = rules.filename_warnings([n for n in names if n])
    req["outputsDone"] = sum(1 for o in req.get("outputs", []) if o.get("done"))
    req["missing"] = rules.brief_missing(req) if req.get("status") in {"Brief Masuk", "Ditahan Gate", "Ditolak"} else []
    return req


async def get_request(db, rid: str) -> dict:
    r = await db.requests.find_one({"$or": [{"id": rid}, {"code": rid}]}, NOPROJ)
    if not r:
        raise err(404, "Request tidak ditemukan")
    return r


# ---------- Sinkron ke kalender ----------
async def sync_content(db, req: dict):
    ids = req.get("contentItemIds") or []
    if not ids:
        return
    new_status, ready = rules.content_status_for_request(req["status"])
    cancelled = req["status"] in {"Ditolak", "Batal"}
    async for item in db.content.find({"id": {"$in": ids}}, NOPROJ):
        upd = {"assetReady": ready, "assetCancelled": cancelled, "requestStatus": req["status"]}
        if req.get("gateStatus") in GATE_OK and item.get("isPromo"):
            upd["gateStatus"] = req["gateStatus"]
            upd["gateRef"] = req.get("gateRef")
        promo_locked = item.get("isPromo") and (upd.get("gateStatus") or item.get("gateStatus")) not in GATE_OK
        if new_status and item.get("status") not in {"Scheduled", "Posted", "Batal"} and not promo_locked:
            if item.get("status") != new_status:
                upd["status"] = new_status
                await log(db, "content", item["id"], "sync-status", "system", item.get("status"), new_status, req["code"])
        upd["updatedAt"] = clock.iso_utc()
        await db.content.update_one({"id": item["id"]}, {"$set": upd})


# ---------- Buat ----------
async def create_request(db, actor: Actor, data: dict) -> dict:
    validate_enums(data)
    data = {k: v for k, v in data.items() if k in BRIEF_FIELDS}
    data["outputs"] = normalize_outputs(data.get("outputs"))
    data.setdefault("gateStatus", "NA")
    if (data.get("isPromo") or data.get("isBudgeted")) and data["gateStatus"] == "NA":
        data["gateStatus"] = "PENDING"
    check_promo_text(data)
    if not (data.get("title") or "").strip():
        raise err(400, "Judul wajib diisi")
    if data.get("gateStatus") in GATE_OK and not actor.is_approver:
        # requester boleh menyalin status Gate yang sudah GO, tetapi harus menyertakan kode Gate
        if not data.get("gateRef"):
            raise err(400, "Status Gate GO/GWC wajib menyertakan kode Gate (gateRef)")
    settings = await get_settings(db)
    rid = new_id("r")
    req = {
        "id": rid, "code": await next_code(db), "requesterId": actor.id,
        "title": "", "source": "Socmed", "funnelGoal": None, "assetType": None, "keyMessage": "", "hook": "",
        "heroProduct": "", "supportingSkus": "", "talent": "", "props": "", "location": settings["locations"][0] if settings.get("locations") else "Braga",
        "shootDate": None, "shootTime": "", "mood": "", "referenceLinks": [], "mandatoryText": "", "mandatoryTextSource": "",
        "cta": "", "trackingCode": "", "isPromo": False, "isBudgeted": False, "budget": 0, "gateRef": "",
        "priority": "Normal", "picShootId": None, "picDesignId": None, "picEditId": None, "reviewerId": None,
        "requestedDeadline": None, "driveFolderLink": "", "finalFileNames": [], "notes": "",
        "revisionRound": 0, "deadlineDraft": None, "deadlineFinal": None,
        "qc": {"items": {}, "qcByMaker": None, "qcByReviewer": None, "qcAt": None},
        "approval": {"required": False, "by": None, "at": None, "note": ""},
        "contentItemIds": [], "parentRequestId": None, "rejectReason": "", "holdReason": "", "closedNote": "",
        "createdAt": clock.iso_utc(), "updatedAt": clock.iso_utc(),
    }
    req.update(data)
    req["approval"]["required"] = rules.approval_required(req)
    if rules.needs_gate_hold(req):
        req["status"] = "Ditahan Gate"
        req["holdReason"] = "Menunggu status GO/GWC dari Activity Gate"
    else:
        req["status"] = "Brief Masuk"
    await db.requests.insert_one(dict(req))
    await log(db, "request", rid, "create", actor.id, to=req["status"])
    await notify.event(db, await lead_ids(db), f"Brief baru {req['code']}: {req['title']}",
                       [f"Dari: {actor.get('name')}", f"Status: {req['status']}", f"Tipe: {req.get('assetType') or '-'}"],
                       path=f"/?req={rid}")
    return req


# ---------- Ubah ----------
async def update_request(db, actor: Actor, rid: str, data: dict, confirm: bool = False) -> dict:
    req = await get_request(db, rid)
    validate_enums(data)
    data = {k: v for k, v in data.items() if k in BRIEF_FIELDS or k in {"deadlineDraft", "deadlineFinal", "deadlineChangeReason"}}
    is_requester = actor.id == req["requesterId"]
    is_pic = actor.id in pics(req) or actor.id == req.get("reviewerId")
    if not (actor.is_lead or is_requester or is_pic):
        raise err(403, "Hanya peminta, PIC, atau Lead yang bisa mengubah request ini")
    if req["status"] in {"Diserahkan", "Batal"}:
        raise err(400, f"Request berstatus {req['status']} tidak bisa diubah")
    if "outputs" in data:
        data["outputs"] = normalize_outputs(data["outputs"])

    # Brief terkunci setelah shoot
    if req["status"] in LOCKED_BRIEF:
        changed = []
        for f in LOCKED_FIELDS:
            if f not in data:
                continue
            old, new = req.get(f), data[f]
            if f == "outputs":
                strip = lambda os_: [{k: o.get(k) for k in ("format", "ratio", "size", "duration", "platform")} for o in os_ or []]
                old, new = strip(old), strip(new)
            if (old or "") != (new or ""):
                changed.append(f)
        if changed:
            raise err(409, "Brief berubah setelah shoot = brief baru. Gunakan \"Buat brief baru\".",
                      offer="clone", fields=changed)
        for f in LOCKED_FIELDS:
            data.pop(f, None)

    # Gate hanya oleh Approver
    gate_changed = any(f in data and data[f] != req.get(f) for f in ("gateStatus", "gateRef"))
    if gate_changed and not actor.is_approver:
        raise err(403, "Status Gate hanya bisa diubah Approver")

    # Deadline manual
    for f in ("deadlineDraft", "deadlineFinal"):
        if f in data and data[f] != req.get(f):
            if not actor.is_lead:
                raise err(403, "Deadline hanya bisa diubah Creative Lead")
            if not (data.get("deadlineChangeReason") or "").strip():
                raise err(400, "Perubahan deadline wajib disertai alasan")
            await log(db, "request", req["id"], "deadline", actor.id, req.get(f), data[f], data["deadlineChangeReason"])
    data.pop("deadlineChangeReason", None)

    merged = {**req, **data}
    if (merged.get("isPromo") or merged.get("isBudgeted")) and merged.get("gateStatus") == "NA":
        merged["gateStatus"] = data["gateStatus"] = "PENDING"
    if merged.get("gateStatus") in GATE_OK and gate_changed and not (merged.get("gateRef") or "").strip():
        raise err(400, "Status GO/GWC wajib menyertakan kode Gate (gateRef)")
    check_promo_text(merged)

    # Kapasitas saat PIC berubah dan request aktif
    new_pics = [merged.get(k) for k in PIC_FIELDS if merged.get(k) and merged.get(k) != req.get(k)]
    if new_pics and req["status"] in ACTIVE_STATUSES:
        warns = await capacity_warnings(db, req, new_pics)
        if warns and not confirm:
            raise err(409, "PIC melebihi kapasitas. Kirim ulang dengan confirm=true untuk tetap menugaskan.",
                      needConfirm=True, warnings=warns)

    # Status otomatis karena Gate
    status = req["status"]
    if status == "Ditahan Gate" and not rules.needs_gate_hold(merged):
        data["status"], data["holdReason"] = "Brief Masuk", ""
    elif status == "Brief Masuk" and rules.needs_gate_hold(merged):
        data["status"], data["holdReason"] = "Ditahan Gate", "Menunggu status GO/GWC dari Activity Gate"
    merged.update(data)
    data["approval"] = {**req.get("approval", {}), "required": rules.approval_required(merged)}
    data["updatedAt"] = clock.iso_utc()
    await db.requests.update_one({"id": req["id"]}, {"$set": data})
    new = await get_request(db, req["id"])
    await log(db, "request", req["id"], "update", actor.id, note=", ".join(sorted(k for k in data if k != "updatedAt")))
    if data.get("status") and data["status"] != status:
        await log(db, "request", req["id"], "status", actor.id, status, data["status"], "otomatis dari Gate")
        if data["status"] == "Brief Masuk":
            await notify.event(db, [req["requesterId"], *await lead_ids(db)], f"{req['code']} lolos Gate ({merged['gateStatus']})",
                               [f"{req['title']} kembali ke Brief Masuk dan siap diproses.", f"Kode Gate: {merged.get('gateRef')}"],
                               path=f"/?req={req['id']}")
    if new_pics:
        await notify.event(db, new_pics, f"Anda ditugaskan: {req['code']} {req['title']}",
                           [f"Status: {new['status']}", f"Deadline final: {new.get('deadlineFinal') or '-'}"], path=f"/?req={req['id']}")
    await sync_content(db, new)
    return new


# ---------- Transisi ----------
async def _start_revision(db, actor: Actor, req: dict, note_text: str | None) -> dict:
    nxt = int(req.get("revisionRound", 0)) + 1
    if nxt > 2:
        raise err(400, "Maks. 2 ronde revisi — buat brief baru", offer="clone")
    if note_text:
        await add_revision_note(db, actor, req, note_text, "", round_=nxt)
    has_note = await db.revisionnotes.count_documents({"requestId": req["id"], "round": nxt})
    if not has_note:
        raise err(400, f"Tambahkan catatan revisi untuk ronde {nxt} terlebih dahulu")
    return {"revisionRound": nxt, "qc": {"items": {}, "qcByMaker": None, "qcByReviewer": None, "qcAt": None},
            "approval": {**req.get("approval", {}), "by": None, "at": None}}


async def transition(db, actor: Actor, rid: str, to: str, note: str = "", confirm: bool = False, _system: bool = False) -> dict:
    req = await get_request(db, rid)
    cur = req["status"]
    if to == cur:
        raise err(400, f"Status sudah {cur}")
    allowed = TRANSITIONS.get(cur, set())
    if to not in allowed:
        override_ok = actor.is_approver and to not in {"Ditahan Gate", "Brief Masuk", "Approval", "Final"} and cur not in {"Ditahan Gate", "Diserahkan", "Batal"}
        if not (override_ok or _system):
            raise err(400, f"Transisi {cur} → {to} tidak diizinkan")
    is_pic = actor.id in pics(req)
    is_requester = actor.id == req["requesterId"]
    is_reviewer = actor.id == req.get("reviewerId")
    upd: dict = {}
    settings = await get_settings(db)

    if to in {"Brief OK", "Ditolak"} and not actor.is_lead:
        raise err(403, "Hanya Creative Lead yang menerima/menolak brief")
    if to == "Batal" and not (actor.is_lead or (is_requester and cur in {"Brief Masuk", "Ditahan Gate", "Ditolak"})):
        raise err(403, "Pembatalan hanya oleh Lead (atau peminta sebelum brief diterima)")
    if to in {"Shoot", "Produksi", "Review", "Diserahkan"} and not (is_pic or actor.is_lead or _system):
        raise err(403, "Hanya PIC atau Creative Lead")

    if to == "Brief OK":
        if rules.needs_gate_hold(req):
            raise err(400, "Masih menunggu Gate (GO/GWC)")
        missing = rules.brief_missing(req)
        if missing:
            raise err(400, "Brief belum lengkap: " + ", ".join(missing), missing=missing)
        warns = await capacity_warnings(db, req, pics(req))
        if warns and not confirm:
            raise err(409, "PIC melebihi kapasitas. Kirim ulang dengan confirm=true untuk tetap menugaskan.",
                      needConfirm=True, warnings=warns)
        base = clock.today()
        d, f = rules.sla_dates(req["assetType"], req.get("shootDate"), base, settings)
        upd.update({"deadlineDraft": d, "deadlineFinal": f, "briefOkAt": clock.today_str()})
        if not req.get("reviewerId") and actor.id != "panel":
            upd["reviewerId"] = actor.id
    elif to == "Ditolak":
        if not note.strip():
            raise err(400, "Alasan penolakan wajib diisi")
        upd["rejectReason"] = note
    elif to == "Brief Masuk":  # dari Ditolak (ajukan ulang)
        if not (is_requester or actor.is_lead):
            raise err(403, "Hanya peminta atau Lead")
        if rules.needs_gate_hold(req):
            to = "Ditahan Gate"
    elif to == "Shoot":
        if not (req.get("picShootId") or req.get("shootDate")):
            raise err(400, "Isi PIC shoot atau tanggal shoot dulu")
    elif to == "Revisi":
        if not (actor.is_lead or is_reviewer or actor.is_approver or is_requester):
            raise err(403, "Hanya reviewer, peminta, atau Lead yang meminta revisi")
        if cur == "Approval" and not actor.is_approver:
            raise err(403, "Revisi dari tahap Approval hanya oleh Approver")
        upd.update(await _start_revision(db, actor, req, note or None))
    elif to == "Approval":
        if not rules.approval_required(req):
            raise err(400, "Request ini tidak memerlukan approval; lanjut ke Final")
        if not rules.qc_complete(req.get("qc")) or not req["qc"].get("qcByReviewer"):
            raise err(400, "QC 9 poin harus lengkap dan dikonfirmasi reviewer sebelum approval")
        if not (is_pic or is_reviewer or actor.is_lead):
            raise err(403, "Hanya PIC, reviewer, atau Lead")
        upd["approvalRequestedAt"] = clock.today_str()
    elif to == "Final":
        if rules.approval_required(req) and not (req.get("approval") or {}).get("by"):
            raise err(400, "Aset ini wajib approval Brand Lead / Marketing Lead sebelum Final")
        qc = req.get("qc") or {}
        if not rules.qc_complete(qc):
            done = sum(1 for k in QC_KEYS if (qc.get("items") or {}).get(k))
            raise err(400, f"QC belum lengkap ({done}/9)")
        if not qc.get("qcByMaker") or not qc.get("qcByReviewer"):
            raise err(400, "QC harus dicentang pembuat dan dikonfirmasi reviewer")
        if qc["qcByMaker"] == qc["qcByReviewer"]:
            raise err(400, "Reviewer QC harus berbeda dari pembuat")
        if not (is_reviewer or actor.is_lead or _system):
            raise err(403, "Hanya reviewer atau Lead yang menandai Final")
    elif to == "Diserahkan":
        outs = req.get("outputs") or []
        missing = [o["format"] for o in outs if not (o.get("done") and o.get("fileLink"))]
        if missing:
            raise err(400, "Semua output harus selesai dan punya link file: " + ", ".join(missing))
        if not (req.get("driveFolderLink") or "").strip():
            raise err(400, "Isi link folder Drive dulu")

    upd["status"] = to
    upd["updatedAt"] = clock.iso_utc()
    if to in {"Final", "Diserahkan"}:
        upd[f"{'final' if to == 'Final' else 'handover'}At"] = clock.iso_utc()
    await db.requests.update_one({"id": req["id"]}, {"$set": upd})
    await log(db, "request", req["id"], "status", actor.id, cur, to, note)
    new = await get_request(db, req["id"])
    await sync_content(db, new)
    await _notify_transition(db, actor, new, cur, to, note)
    return new


async def _notify_transition(db, actor, req, frm, to, note):
    code = f"{req['code']} {req['title']}"
    path = f"/?req={req['id']}"
    if to == "Brief OK":
        await notify.event(db, pics(req), f"Anda ditugaskan: {code}",
                           [f"Deadline draft: {req.get('deadlineDraft')}", f"Deadline final: {req.get('deadlineFinal')}"], path)
    elif to == "Review":
        await notify.event(db, [req.get("reviewerId")] if req.get("reviewerId") else await lead_ids(db),
                           f"Perlu review: {code}", [f"Dikirim oleh {actor.get('name')}"], path)
    elif to == "Revisi":
        await notify.event(db, pics(req), f"Revisi ronde {req['revisionRound']}: {code}", [note or "Lihat catatan revisi."], path)
    elif to == "Approval":
        await notify.event(db, await approver_ids(db), f"Menunggu approval: {code}", ["Aset sudah lolos QC."], path)
    elif to in {"Final", "Diserahkan"}:
        socmed = [i["picSocmedId"] async for i in db.content.find({"id": {"$in": req.get("contentItemIds", [])}}, {"picSocmedId": 1}) if i.get("picSocmedId")]
        await notify.event(db, [req["requesterId"], *socmed], f"Aset {to.lower()}: {code}", ["Aset siap dijadwalkan."], path)
    elif to == "Ditolak":
        await notify.event(db, [req["requesterId"]], f"Brief ditolak: {code}", [note], path)


async def add_revision_note(db, actor: Actor, req: dict, text: str, timecodes: str, round_: int | None = None) -> dict:
    if not text.strip():
        raise err(400, "Catatan revisi kosong")
    if round_ is None:
        cur = int(req.get("revisionRound", 0))
        round_ = cur + 1 if req["status"] in {"Review", "Approval", "Produksi", "Final"} else max(cur, 1)
    if round_ > 2:
        raise err(400, "Maks. 2 ronde revisi — buat brief baru", offer="clone")
    note = {"id": new_id("n"), "requestId": req["id"], "round": round_, "authorId": actor.id,
            "authorName": actor.get("name"), "text": text.strip(), "timecodes": timecodes or "", "resolved": False,
            "createdAt": clock.iso_utc()}
    await db.revisionnotes.insert_one(dict(note))
    await log(db, "request", req["id"], "revision-note", actor.id, note=f"R{round_}")
    if req["status"] == "Revisi":
        await notify.event(db, pics(req), f"Catatan revisi baru: {req['code']}", [text], f"/?req={req['id']}")
    return note


async def clone_as_new_brief(db, actor: Actor, rid: str, overrides: dict) -> dict:
    req = await get_request(db, rid)
    if not (actor.is_lead or actor.id == req["requesterId"] or actor.id in pics(req)):
        raise err(403, "Hanya peminta, PIC, atau Lead")
    data = {k: req.get(k) for k in BRIEF_FIELDS}
    data["outputs"] = [{**o, "done": False, "fileLink": "", "finalFileName": ""} for o in req.get("outputs", [])]
    data.update({k: v for k, v in (overrides or {}).items() if k in BRIEF_FIELDS})
    if not actor.is_approver and data.get("gateStatus") in GATE_OK and not data.get("gateRef"):
        data["gateStatus"] = "PENDING"
    new = await create_request(db, actor, data)
    links = req.get("contentItemIds", [])
    await db.requests.update_one({"id": new["id"]}, {"$set": {"parentRequestId": req["id"], "contentItemIds": links}})
    await db.content.update_many({"id": {"$in": links}}, {"$set": {"requestId": new["id"]}})
    if req["status"] not in CLOSED_STATUSES:
        await db.requests.update_one({"id": req["id"]}, {"$set": {
            "status": "Final", "closedNote": f"lanjut ke {new['code']}", "contentItemIds": [], "updatedAt": clock.iso_utc()}})
        await log(db, "request", req["id"], "status", actor.id, req["status"], "Final", f"lanjut ke {new['code']}")
    new = await get_request(db, new["id"])
    await sync_content(db, new)
    return new


async def workload(db) -> list[dict]:
    settings = await get_settings(db)
    mm = await members_map(db)
    today = clock.today()
    week = clock.add_days(today, 7).isoformat()
    out = []
    reqs = [r async for r in db.requests.find({"status": {"$in": list(ACTIVE_STATUSES)}}, NOPROJ)]
    for m in mm.values():
        if not m.get("active", True) or m["role"] not in {"creative", "creative_lead"}:
            if not any(m["id"] in pics(r) for r in reqs):
                continue
        mine = [r for r in reqs if m["id"] in pics(r)]
        by_status = {}
        for r in mine:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        cap = m.get("capacity") or settings.get("defaultCapacity", 6)
        upcoming = sorted([{"code": r["code"], "title": r["title"], "deadlineFinal": r["deadlineFinal"], "id": r["id"]}
                           for r in mine if r.get("deadlineFinal") and r["deadlineFinal"] <= week], key=lambda x: x["deadlineFinal"])
        out.append({"memberId": m["id"], "name": m["name"], "jobFunction": m["jobFunction"], "active": len(mine),
                    "capacity": cap, "over": len(mine) >= cap, "byStatus": by_status, "next7": upcoming})
    return sorted(out, key=lambda x: (-x["active"], x["name"]))
