import os


class Config:
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "crk_creative_hub")
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    APP_URL = os.getenv("APP_URL", "http://localhost:5173")
    # Email: isi RESEND_API_KEY atau SMTP_*; bila kosong, email hanya dicatat di koleksi emaillog.
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "CRK Creative Hub <noreply@example.com>")
    BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")
    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
    SERVE_FRONTEND = os.getenv("SERVE_FRONTEND", "")  # path ke frontend/dist bila backend sekaligus menyajikan UI


config = Config()
