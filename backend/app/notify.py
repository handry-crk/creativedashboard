"""Email: Resend API, SMTP, atau hanya dicatat (emaillog) bila belum dikonfigurasi."""
import asyncio
import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from . import clock
from .config import config

log = logging.getLogger("crk.mail")
RED = "#D7191F"


def layout(title: str, body_html: str, button_text: str = "Buka Creative Hub", path: str = "") -> str:
    url = (config.APP_URL or "").rstrip("/") + path
    return f"""<div style="font-family:'Plus Jakarta Sans',Arial,sans-serif;max-width:620px;margin:auto;color:#1F1A1A">
<div style="background:{RED};color:#fff;padding:16px 20px;border-radius:12px 12px 0 0">
<b>Cimol Bojot AA</b> · CRK Creative Hub</div>
<div style="border:1px solid #EBD9DA;border-top:0;padding:20px;border-radius:0 0 12px 12px">
<h2 style="margin:0 0 12px;font-size:18px">{html.escape(title)}</h2>
{body_html}
<p style="margin-top:20px"><a href="{url}" style="background:{RED};color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">{html.escape(button_text)}</a></p>
</div></div>"""


def table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "<p style='color:#777'>Tidak ada.</p>"
    th = "".join(f"<th style='background:#B32E26;color:#fff;padding:6px 8px;text-align:left;font-size:12px'>{html.escape(str(h))}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td style='border-bottom:1px solid #EBD9DA;padding:6px 8px;font-size:13px'>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table style='border-collapse:collapse;width:100%;margin:8px 0'><tr>{th}</tr>{trs}</table>"


def _smtp_send(to: list[str], subject: str, body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, config.MAIL_FROM, ", ".join(to)
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
        s.starttls()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.sendmail(config.MAIL_FROM, to, msg.as_string())


async def _deliver(to: list[str], subject: str, body: str):
    try:
        if config.RESEND_API_KEY:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post("https://api.resend.com/emails",
                                 headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                                 json={"from": config.MAIL_FROM, "to": to, "subject": subject, "html": body})
                r.raise_for_status()
        elif config.SMTP_HOST:
            await asyncio.to_thread(_smtp_send, to, subject, body)
    except Exception as e:  # jangan sampai email gagal membuat API gagal
        log.warning("Email gagal: %s", e)


async def send(db, to: list[str], subject: str, body_html: str, kind: str = "event") -> int:
    to = sorted({t.strip() for t in to if t and "@" in t})
    if not to:
        return 0
    await db.emaillog.insert_one({"to": to, "subject": subject, "kind": kind, "at": clock.iso_utc(),
                                  "delivered": bool(config.RESEND_API_KEY or config.SMTP_HOST)})
    if config.RESEND_API_KEY or config.SMTP_HOST:
        asyncio.create_task(_deliver(to, subject, body_html))
    return len(to)


async def event(db, member_ids: list[str], subject: str, lines: list[str], path: str = ""):
    ids = [i for i in member_ids if i]
    if not ids:
        return
    emails = [m["email"] async for m in db.members.find({"id": {"$in": ids}, "active": True, "approval": {"$nin": ["pending", "rejected"]}}, {"email": 1, "_id": 0})]
    body = "".join(f"<p style='margin:6px 0'>{html.escape(l)}</p>" for l in lines)
    await send(db, emails, subject, layout(subject, body, path=path), kind="event")
