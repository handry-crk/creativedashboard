import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from .config import config
from .core import get_settings
from .routers import auth, content, misc, requests, shoots

logging.basicConfig(level=logging.INFO)


async def ensure_indexes(db):
    await db.members.create_index("id", unique=True)
    await db.requests.create_index("id", unique=True)
    await db.requests.create_index("code", unique=True)
    await db.content.create_index("id", unique=True)
    await db.content.create_index("date")
    await db.sessions.create_index("token", unique=True)
    await db.activitylog.create_index([("entity", 1), ("entityId", 1)])


def create_app(db=None, start_scheduler: bool | None = None) -> FastAPI:
    scheduler = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal scheduler
        if db is None:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(config.MONGO_URL)
            app.state.db = client[config.DB_NAME]
        else:
            app.state.db = db
        try:
            await ensure_indexes(app.state.db)
        except Exception as e:  # mongomock dapat menolak sebagian opsi index
            logging.warning("Index: %s", e)
        await get_settings(app.state.db)
        run_sched = config.ENABLE_SCHEDULER if start_scheduler is None else start_scheduler
        if run_sched:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from . import jobs
            scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
            scheduler.add_job(jobs.tick, "cron", minute="*/15", args=[app.state.db], id="tick", max_instances=1, coalesce=True)
            scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="CRK Creative Hub", lifespan=lifespan)
    if db is not None:
        app.state.db = db
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        msgs = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e.get("loc", []) if x != "body")
            msgs.append(f"{loc}: {e.get('msg')}")
        return JSONResponse(status_code=422, content={"detail": {"message": "Data tidak valid — " + "; ".join(msgs)}})

    for r in (auth.router, requests.router, content.router, shoots.router, misc.router):
        app.include_router(r)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    dist = config.SERVE_FRONTEND
    if dist and os.path.isdir(dist):
        app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")

        @app.get("/{path:path}")
        async def spa(path: str):
            f = os.path.join(dist, path)
            if path and os.path.isfile(f):
                return FileResponse(f)
            return FileResponse(os.path.join(dist, "index.html"))

    return app


app = create_app()
