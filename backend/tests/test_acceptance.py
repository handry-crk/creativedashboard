"""Acceptance tests dari spec (mongomock, jam dibekukan Selasa 10 Nov 2026 10.00 WIB)."""
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app import clock
from app.main import create_app

pytestmark = pytest.mark.asyncio


class Ctx:
    def __init__(self, client):
        self.c = client
        self.tok = {}

    def h(self, who):
        return {"Authorization": f"Bearer {self.tok[who]}"}

    async def post(self, who, url, json=None, **kw):
        return await self.c.post(url, json=json, headers=self.h(who) if who else {}, **kw)

    async def put(self, who, url, json=None, **kw):
        return await self.c.put(url, json=json, headers=self.h(who), **kw)

    async def get(self, url, **kw):
        return await self.c.get(url, **kw)

    async def tr(self, who, rid, to, note="", confirm=False):
        return await self.post(who, f"/api/requests/{rid}/transition", {"to": to, "note": note, "confirm": confirm})


@pytest_asyncio.fixture
async def ctx():
    clock.set_now(datetime(2026, 11, 10, 10, 0, tzinfo=clock.WIB))
    db = AsyncMongoMockClient()["test"]
    app = create_app(db=db, start_scheduler=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        x = Ctx(c)
        for name, fn in [("Dina", "Graphic Designer"), ("Raka", "Videographer / Editor"),
                         ("Sinta", "Socmed Specialist"), ("Agoy", "Brand Lead")]:
            r = await c.post("/api/auth/register", json={"name": name, "jobFunction": fn, "email": f"{name.lower()}@x.id", "pin": "1234"})
            assert r.status_code == 200, r.text
            x.tok[name.lower()] = r.json()["token"]
        x.db = db
        yield x
    clock.set_now(None)


def brief(**kw):
    b = {"title": "Aset uji", "funnelGoal": "Reach", "assetType": "FEED", "keyMessage": "Cimol panas", "cta": "Cek lokasi",
         "outputs": [{"format": "Feed", "ratio": "4:5", "platform": "IG"}], "picDesignId": "dina"}
    b.update(kw)
    return b


async def new_req(x, who="sinta", **kw):
    r = await x.post(who, "/api/requests", brief(**kw))
    assert r.status_code == 200, r.text
    return r.json()


async def to_review(x, rid, pic="dina"):
    for st in ("Brief OK",):
        assert (await x.tr("agoy", rid, st)).status_code == 200
    assert (await x.tr(pic, rid, "Produksi")).status_code == 200
    r = await x.tr(pic, rid, "Review")
    assert r.status_code == 200, r.text


async def qc_all(x, rid, maker="dina", reviewer="agoy"):
    items = {f"q{i}": True for i in range(1, 10)}
    assert (await x.put(maker, f"/api/requests/{rid}/qc", {"as": "maker", "items": items})).status_code == 200
    r = await x.put(reviewer, f"/api/requests/{rid}/qc", {"as": "reviewer"})
    assert r.status_code == 200, r.text


async def test_roles(ctx):
    st = (await ctx.get("/api/state", headers=ctx.h("agoy"))).json()
    roles = {m["id"]: m["role"] for m in st["members"]}
    assert roles == {"dina": "creative", "raka": "creative", "sinta": "socmed", "agoy": "approver"}
    assert "panelPinHash" not in st["settings"]


async def test_content_to_brief_and_sla(ctx):
    r = await ctx.post("sinta", "/api/content", {"date": "2026-11-13", "time": "12:00", "platform": "IG+TT", "format": "Reels",
                                                  "pillar": "Product Craving", "goal": "Reach", "idea": "ASMR Mozza",
                                                  "hook": "Tarik bumbu", "cta": "Cek lokasi di bio"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = await ctx.post("sinta", f"/api/content/{cid}/create-brief")
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["code"] == "CR-2611-001"
    assert len(req["outputs"]) == 2 and {o["platform"] for o in req["outputs"]} == {"IG", "TT"}
    item = (await ctx.get(f"/api/content/{cid}")).json()
    assert item["status"] == "Idea" and item["requestId"] == req["id"]

    r = await ctx.put("agoy", f"/api/requests/{req['id']}", {"shootDate": "2026-11-16", "picShootId": "raka", "picEditId": "raka"})
    assert r.status_code == 200, r.text
    r = await ctx.tr("agoy", req["id"], "Brief OK")
    assert r.status_code == 200, r.text
    assert r.json()["deadlineDraft"] == "2026-11-17" and r.json()["deadlineFinal"] == "2026-11-18"
    item = (await ctx.get(f"/api/content/{cid}")).json()
    assert item["status"] == "Brief"
    warns = (await ctx.get("/api/content/warnings?month=2026-11")).json()
    assert any(w["type"] == "asset_not_ready" and w["itemId"] == cid for w in warns)


async def test_gate_lock(ctx):
    r = await ctx.post("sinta", "/api/requests", brief(title="Gajian 26–27 Nov", isPromo=True, gateStatus="PENDING"))
    assert r.status_code == 400  # tanpa teks wajib & sumber
    r = await ctx.post("sinta", "/api/requests", brief(title="Gajian 26–27 Nov", isPromo=True, gateStatus="PENDING",
                                                         mandatoryText="Diskon 20% 26–27 Nov Braga"))
    assert r.status_code == 400 and "sumber" in r.json()["detail"]["message"]
    req = await new_req(ctx, title="Gajian 26–27 Nov", isPromo=True, gateStatus="PENDING",
                        mandatoryText="Diskon 20% 26–27 Nov Braga", mandatoryTextSource="Promo Planner")
    assert req["status"] == "Ditahan Gate"
    assert (await ctx.tr("agoy", req["id"], "Brief OK")).status_code == 400
    assert (await ctx.put("sinta", f"/api/requests/{req['id']}", {"gateStatus": "GO", "gateRef": "N12"})).status_code == 403
    r = await ctx.put("agoy", f"/api/requests/{req['id']}", {"gateStatus": "GO", "gateRef": "N12"})
    assert r.status_code == 200 and r.json()["status"] == "Brief Masuk"


async def test_revision_limit_and_clone(ctx):
    req = await new_req(ctx)
    rid = req["id"]
    await to_review(ctx, rid)
    assert (await ctx.tr("agoy", rid, "Revisi")).status_code == 400  # tanpa catatan
    assert (await ctx.post("agoy", f"/api/requests/{rid}/revision-notes", {"text": "Hook kurang cepat", "timecodes": "00:03"})).status_code == 200
    r = await ctx.tr("agoy", rid, "Revisi")
    assert r.status_code == 200 and r.json()["revisionRound"] == 1
    assert (await ctx.tr("dina", rid, "Review")).status_code == 200
    r = await ctx.tr("agoy", rid, "Revisi", note="Warna merah kurang")
    assert r.status_code == 200 and r.json()["revisionRound"] == 2
    assert (await ctx.tr("dina", rid, "Review")).status_code == 200
    r = await ctx.tr("agoy", rid, "Revisi", note="Satu lagi")
    assert r.status_code == 400 and "Maks. 2 ronde revisi" in r.json()["detail"]["message"]
    r = await ctx.post("agoy", f"/api/requests/{rid}/clone-as-new-brief")
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["parentRequestId"] == rid and new["code"] != req["code"] and new["revisionRound"] == 0
    old = (await ctx.get(f"/api/requests/{rid}")).json()
    assert old["status"] == "Final" and new["code"] in old["closedNote"]


async def test_brief_locked_after_shoot(ctx):
    req = await new_req(ctx)
    await ctx.tr("agoy", req["id"], "Brief OK")
    await ctx.tr("dina", req["id"], "Produksi")
    r = await ctx.put("sinta", f"/api/requests/{req['id']}", {"keyMessage": "Pesan baru"})
    assert r.status_code == 409 and r.json()["detail"]["offer"] == "clone"


async def test_qc_and_approval(ctx):
    req = await new_req(ctx)
    rid = req["id"]
    await to_review(ctx, rid)
    items8 = {f"q{i}": True for i in range(1, 9)}
    await ctx.put("dina", f"/api/requests/{rid}/qc", {"as": "maker", "items": items8})
    assert (await ctx.tr("agoy", rid, "Final")).status_code == 400
    await ctx.put("dina", f"/api/requests/{rid}/qc", {"as": "maker", "items": {"q9": True}})
    assert (await ctx.put("dina", f"/api/requests/{rid}/qc", {"as": "reviewer"})).status_code in (400, 403)
    assert (await ctx.put("agoy", f"/api/requests/{rid}/qc", {"as": "reviewer"})).status_code == 200
    r = await ctx.tr("agoy", rid, "Final")
    assert r.status_code == 200, r.text
    # Diserahkan butuh semua output selesai + link
    r = await ctx.tr("dina", rid, "Diserahkan")
    assert r.status_code == 400
    await ctx.put("dina", f"/api/requests/{rid}", {"driveFolderLink": "https://drive.google.com/x"})
    r = await ctx.put("dina", f"/api/requests/{rid}/outputs/0", {"done": True, "fileLink": "https://drive.google.com/f"})
    assert r.status_code == 200
    assert (await ctx.tr("dina", rid, "Diserahkan")).status_code == 200

    ads = await new_req(ctx, title="Iklan gajian", assetType="ADS")
    await to_review(ctx, ads["id"])
    await qc_all(ctx, ads["id"])
    assert (await ctx.tr("agoy", ads["id"], "Final")).status_code == 400  # wajib approval
    assert (await ctx.tr("dina", ads["id"], "Approval")).status_code == 200
    assert (await ctx.post("dina", f"/api/requests/{ads['id']}/approve", {"decision": "approve"})).status_code == 403
    r = await ctx.post("agoy", f"/api/requests/{ads['id']}/approve", {"decision": "approve", "note": "OK"})
    assert r.status_code == 200 and r.json()["status"] == "Final"


async def test_calendar_rules(ctx):
    base = {"platform": "IG", "format": "Feed", "pillar": "Promo & Urgency", "isPromo": True, "idea": "Promo"}
    assert (await ctx.post("sinta", "/api/content", {**base, "date": "2026-11-26"})).status_code == 200
    r = await ctx.post("sinta", "/api/content", {**base, "date": "2026-11-26"})
    assert r.status_code == 400 and "Maksimal" in r.json()["detail"]["message"]
    r = await ctx.post("sinta", "/api/content", {**base, "date": "2026-11-27"})
    cid = r.json()["id"]
    assert (await ctx.put("sinta", f"/api/content/{cid}", {"status": "Scheduled"})).status_code == 400
    r = await ctx.post("sinta", "/api/content", {"date": "2026-11-20", "platform": "IG", "format": "Feed", "pillar": "Trend"})
    cid = r.json()["id"]
    assert (await ctx.put("sinta", f"/api/content/{cid}", {"status": "Posted"})).status_code == 400
    assert (await ctx.put("sinta", f"/api/content/{cid}", {"status": "Posted", "postedUrl": "https://ig/p/1"})).status_code == 200
    assert (await ctx.post("dina", "/api/content", {"date": "2026-11-20", "platform": "IG", "format": "Feed", "pillar": "Trend"})).status_code == 403


async def test_capacity(ctx):
    for i in range(6):
        req = await new_req(ctx, title=f"Tugas {i}")
        assert (await ctx.tr("agoy", req["id"], "Brief OK")).status_code == 200
    req = await new_req(ctx, title="Tugas 7")
    r = await ctx.tr("agoy", req["id"], "Brief OK")
    assert r.status_code == 409 and r.json()["detail"]["needConfirm"]
    assert (await ctx.tr("agoy", req["id"], "Brief OK", confirm=True)).status_code == 200
    wl = {w["memberId"]: w for w in (await ctx.get("/api/workload")).json()}
    assert wl["dina"]["active"] == 7 and wl["dina"]["over"]


async def test_mix(ctx):
    pillars = ["Product Craving"] * 10 + ["Behind the Kios"] * 10 + ["Lokal & Komunitas"] * 8 + ["UGC & Review"] * 6 + ["Trend"] * 6
    for n, p in enumerate(pillars):
        r = await ctx.post("sinta", "/api/content", {"date": f"2026-12-{(n % 28) + 1:02d}", "platform": "IG", "format": "Reels", "pillar": p})
        assert r.status_code == 200, r.text
    await ctx.post("sinta", "/api/content", {"date": "2026-12-01", "platform": "IG", "format": "Story", "pillar": "Product Craving"})
    mix = (await ctx.get("/api/content/mix?month=2026-12")).json()
    pc = next(p for p in mix["pillars"] if p["pillar"] == "Product Craving")
    assert mix["total"] == 40 and pc["pct"] == 25.0 and pc["target"] == 30 and pc["flag"]


async def test_weekly_and_lockout(ctx):
    await ctx.post("agoy", "/api/shoots", {"date": "2026-11-12", "location": "Braga", "videographerId": "raka"})
    r = await ctx.post("agoy", "/api/jobs/weekly/run")
    assert r.status_code == 200, r.text
    from app.jobs import weekly_data
    d = await weekly_data(ctx.db)
    for k in ("onTimePct", "avgRevisi", "mix", "nextShoots"):
        assert k in d
    assert d["nextShoots"] and d["nextShoots"][0][0] == "2026-11-12"
    logs = (await ctx.get("/api/emaillog", headers=ctx.h("agoy"))).json()
    assert any("Rekap mingguan" in e["subject"] for e in logs)
    for _ in range(4):
        assert (await ctx.c.post("/api/auth/login", json={"memberId": "dina", "pin": "0000"})).status_code == 401
    assert (await ctx.c.post("/api/auth/login", json={"memberId": "dina", "pin": "0000"})).status_code == 423
    assert (await ctx.c.post("/api/auth/login", json={"memberId": "dina", "pin": "1234"})).status_code == 423
    assert (await ctx.post("agoy", "/api/members/dina/reset-pin", {"pin": "5678"})).status_code == 200
    assert (await ctx.c.post("/api/auth/login", json={"memberId": "dina", "pin": "5678"})).status_code == 200


async def test_import_csv(ctx):
    csv_text = ("date;time;platform;format;pillar;goal;theme;idea;hook;cta;trackingCode;isPromo;gateStatus;picSocmed;status;notes\n"
                "2026-11-03;12:00;IG + TikTok;Reels;Product Craving;Reach;M1;ASMR Mozza;;;IG-MAPS;;;Sinta;Posted;\n"
                "2026-11-26;12:00;IG;Carousel;Promo & Urgency;Conversion;M4;Gajian;;;PROMO-TBD;;;Sinta;Scheduled;\n"
                "2026-11-27;12:00;IG;Feed;Salah;Reach;;x;;;;;;;Idea;\n")
    r = await ctx.c.post("/api/content/import", files={"file": ("k.csv", csv_text.encode(), "text/csv")}, headers=ctx.h("sinta"))
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["created"] == 2 and len(res["errors"]) == 1  # pillar salah; Posted tanpa URL boleh saat impor (muncul di peringatan)
    items = (await ctx.get("/api/content?month=2026-11")).json()
    promo = next(i for i in items if i["date"] == "2026-11-26")
    assert promo["isPromo"] and promo["gateStatus"] == "PENDING" and promo["status"] == "Idea" and promo["platform"] == "IG"
