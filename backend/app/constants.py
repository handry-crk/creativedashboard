"""Daftar tetap: fungsi kerja, role, status, QC, default settings."""

JOB_FUNCTIONS = {
    "Marketing Manager": "MM",
    "Brand Manager": "BM",
    "Marketing Lead": "ML",
    "Brand Lead": "BL",
    "Creative Lead": "CL",
    "Graphic Designer": "GD",
    "Videographer / Editor": "VE",
    "Socmed Specialist": "SM",
    "Admin Social Media": "ASM",
    "Advertiser": "ADV",
    "Promo & Partnership": "PP",
    "Event": "EV",
    "Marketplace": "MP",
    "KOL Lead": "KOLL",
    "KOL Officer": "KOLO",
    "CRM Lead": "CRML",
    "Lainnya": "LN",
}

APPROVER_FUNCTIONS = {"Brand Lead", "Marketing Lead", "Brand Manager", "Marketing Manager"}
CREATIVE_FUNCTIONS = {"Graphic Designer", "Videographer / Editor"}
SOCMED_FUNCTIONS = {"Socmed Specialist", "Admin Social Media"}


def role_for(job_function: str) -> str:
    if job_function in APPROVER_FUNCTIONS:
        return "approver"
    if job_function == "Creative Lead":
        return "creative_lead"
    if job_function in CREATIVE_FUNCTIONS:
        return "creative"
    if job_function in SOCMED_FUNCTIONS:
        return "socmed"
    return "requester"


SOURCES = ["Socmed", "Promo", "Event", "Marketplace", "KOL", "Ads", "Deck", "Lainnya"]
FUNNEL_GOALS = ["Reach", "Engagement", "Store Interest", "Conversion", "Retention", "Trust"]
ASSET_TYPES = ["REEL", "TIKTOK", "STORY", "FEED", "CAROUSEL", "POSM", "MKT", "ADS", "EVENTDOC", "DECK"]
GATE_STATUSES = ["NA", "PENDING", "GO", "GWC", "HOLD"]
GATE_OK = {"GO", "GWC"}
PRIORITIES = ["Normal", "Tinggi", "Urgent"]

REQUEST_STATUSES = [
    "Brief Masuk", "Ditahan Gate", "Brief OK", "Shoot", "Produksi", "Review",
    "Revisi", "Approval", "Final", "Diserahkan", "Ditolak", "Batal",
]
CLOSED_STATUSES = {"Final", "Diserahkan", "Ditolak", "Batal"}
ACTIVE_STATUSES = {"Brief OK", "Shoot", "Produksi", "Review", "Revisi"}
PRE_REVIEW = {"Brief OK", "Shoot", "Produksi"}
# status >= Shoot: brief terkunci
LOCKED_BRIEF = {"Shoot", "Produksi", "Review", "Revisi", "Approval", "Final", "Diserahkan"}

# Transisi normal (tanpa override approver)
TRANSITIONS = {
    "Brief Masuk": {"Brief OK", "Ditolak", "Batal"},
    "Ditahan Gate": {"Batal", "Ditolak"},
    "Brief OK": {"Shoot", "Produksi", "Batal"},
    "Shoot": {"Produksi", "Batal"},
    "Produksi": {"Review", "Batal"},
    "Review": {"Revisi", "Approval", "Final", "Batal"},
    "Revisi": {"Produksi", "Review", "Batal"},
    "Approval": {"Revisi", "Final", "Batal"},
    "Final": {"Diserahkan"},
    "Diserahkan": set(),
    "Ditolak": {"Brief Masuk"},
    "Batal": set(),
}

QC_LABELS = [
    "Produk terlihat jelas, panas, segar; porsi sesuai standar jual",
    "Pesan utama terbaca dalam 1 detik; satu pesan, satu CTA",
    "Angka promo, periode, kuota, outlet sama persis dengan mekanisme Gate / Promo Planner",
    "Brand system benar (warna, logo, checkerboard, strip, maskot, font; deck: sistem Brand Profile)",
    "Ukuran, safe zone, durasi, export spec sesuai platform",
    'Ejaan & Brand Voice benar; tanpa klaim "terenak"/kesehatan tanpa data; tidak menjelekkan kompetitor',
    "Izin talent & lisensi aset lengkap",
    "Kode tracking/identifier promo tercantum bila aset promo",
    "Nama file & folder sesuai konvensi; master editable tersimpan",
]
QC_KEYS = [f"q{i}" for i in range(1, 10)]

# Content
PLATFORMS = ["IG", "TT", "IG+TT"]
FORMATS = ["Reels", "TikTok", "Feed", "Carousel", "Story", "TikTok LIVE"]
PILLARS = ["Product Craving", "Promo & Urgency", "Behind the Kios", "Lokal & Komunitas", "UGC & Review", "Trend"]
CONTENT_GOALS = ["Reach", "Engagement", "Store Interest", "Conversion", "Retention"]
CONTENT_STATUSES = ["Idea", "Brief", "Shoot", "Edit", "Scheduled", "Posted", "Batal"]
FORMAT_TO_ASSET = {
    "Reels": "REEL", "TikTok": "TIKTOK", "Feed": "FEED", "Carousel": "CAROUSEL",
    "Story": "STORY", "TikTok LIVE": "TIKTOK",
}
OUTPUT_PLATFORM_CODES = ["IG", "TT", "FB", "MKT", "PRINT", "DECK"]

DEFAULT_SETTINGS = {
    "id": "settings",
    "appName": "CRK Creative Hub",
    "slaTable": {
        "REEL": {"draftDays": 1, "finalDays": 2, "basis": "shoot"},
        "TIKTOK": {"draftDays": 1, "finalDays": 2, "basis": "shoot"},
        "STORY": {"draftDays": 0, "finalDays": 0, "basis": "shoot"},
        "FEED": {"draftDays": 2, "finalDays": 3, "basis": "shoot"},
        "CAROUSEL": {"draftDays": 2, "finalDays": 3, "basis": "shoot"},
        "POSM": {"draftDays": 3, "finalDays": 5, "basis": "request", "note": "Proofing cetak sebelum produksi"},
        "ADS": {"draftDays": 3, "finalDays": 5, "basis": "shoot", "note": "Wajib storyboard & approval Brand Lead"},
        "EVENTDOC": {"draftDays": 1, "finalDays": 5, "basis": "shoot", "note": "Recap H+1, full H+5"},
        "MKT": {"draftDays": 3, "finalDays": 5, "basis": "shoot"},
        "DECK": {"draftDays": 1, "finalDays": 2, "basis": "request"},
    },
    "workDays": [1, 2, 3, 4, 5, 6],  # ISO weekday: 1=Senin
    "holidays": [],
    "pillarTargets": {
        "Product Craving": 30, "Promo & Urgency": 20, "Behind the Kios": 15,
        "Lokal & Komunitas": 15, "UGC & Review": 15, "Trend": 5,
    },
    "monthOverrides": {},
    "weekThemes": {},
    "postingWindows": ["11:00-13:00", "17:00-20:00"],
    "maxPromoPerDay": 1,
    "reactiveSlotPct": 20,
    "locations": ["Braga", "Studio", "Event", "Lainnya"],
    "trackingCodes": ["IG-MAPS", "TT-MAPS", "IG-MKT", "TT-MKT", "EVT-TEASER", "EVT-H1", "EVT-LIVE", "EVT-RECAP", "PROMO-TBD"],
    "equipmentChecklist": [
        "Kamera/HP 4K", "Lensa macro", "Tripod", "Mini tripod", "LED + diffuser", "Reflektor putih",
        "Mic clip-on", "Powerbank", "Alas merah/krem/checkerboard", "Properti brand (maskot, standee, kemasan)",
        "Tisu/lap", "Produk cadangan 3-5 porsi",
    ],
    "defaultCapacity": 6,
    "adminEmail": "",
    "creativeLeadFallback": "Brand Lead",
    "digestTime": "08:00",
    "deadlineTime": "15:00",
    "approvalTime": "10:00",
    "weeklyDay": 1,
    "weeklyTime": "08:30",
    "appUrl": "",
}
