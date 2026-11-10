"""Data contoh (tombol "Isi data contoh" di Pengaturan). Ditandai demo=True agar mudah dihapus."""
from . import clock
from .core import Actor


async def seed(db, actor: Actor) -> dict:
    if await db.content.count_documents({"demo": True}):
        return {"skipped": "data contoh sudah ada"}
    month = clock.today_str()[:7]
    rows = [
        ("03", "12:00", "IG+TT", "Reels", "Product Craving", "Reach", "ASMR Mozza tarik bumbu", "Posted"),
        ("05", "18:00", "IG", "Carousel", "Lokal & Komunitas", "Store Interest", "Menu & Harga Braga", "Posted"),
        ("12", "12:00", "TT", "TikTok", "Trend", "Reach", "POV pulang kerja hujan", "Scheduled"),
        ("13", "18:30", "IG+TT", "Reels", "Behind the Kios", "Engagement", "Jam 9 pagi di kios Aa", "Edit"),
        ("17", "12:00", "IG", "Feed", "UGC & Review", "Engagement", "Kompilasi UGC", "Idea"),
        ("19", "19:00", "IG+TT", "Reels", "Product Craving", "Reach", "Kuah Keju hujan", "Idea"),
        ("26", "12:00", "IG", "Carousel", "Promo & Urgency", "Conversion", "Promo gajian (menunggu Gate)", "Idea"),
    ]
    n = 0
    for d, t, p, f, pil, g, idea, st in rows:
        date = f"{month}-{d}"
        promo = pil == "Promo & Urgency"
        await db.content.insert_one({
            "id": f"cdemo{d}", "date": date, "time": t, "platform": p, "format": f, "pillar": pil, "goal": g,
            "theme": "", "idea": idea, "hook": idea, "cta": "Cek lokasi di bio", "trackingCode": "PROMO-TBD" if promo else "IG-MAPS",
            "isPromo": promo, "gateStatus": "PENDING" if promo else "NA", "gateRef": "", "isReactiveSlot": False,
            "picSocmedId": None, "requestId": None, "status": st, "captionFinal": "",
            "postedUrl": "https://instagram.com/p/demo" if st == "Posted" else "", "postedAt": None, "notes": "Data contoh",
            "assetReady": False, "demo": True, "createdAt": clock.iso_utc(), "updatedAt": clock.iso_utc()})
        n += 1
    return {"created": n}
