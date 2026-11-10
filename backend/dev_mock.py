"""Jalankan backend tanpa MongoDB (data di memori, hilang saat dimatikan). Hanya untuk mencoba/demo.
    python dev_mock.py   -> http://localhost:8000
"""
import os
import uvicorn

os.environ.setdefault("SERVE_FRONTEND", os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
from mongomock_motor import AsyncMongoMockClient  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app(db=AsyncMongoMockClient()["demo"], start_scheduler=False)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
