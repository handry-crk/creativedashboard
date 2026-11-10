# CRK Creative Hub

Sistem kerja tim **Graphic Designer, Videographer/Editor, dan Social Media Specialist** Cimol Bojot AA. App ini mengikuti spec `CRK-creative-hub-emergent-build-spec.md` dan punya dua tab utama:

- **Produksi**: brief masuk → Brief OK → Shoot → Produksi → Review → Revisi → Approval → Final → Diserahkan. Di tab ini juga ada board kanban, daftar, beban kerja, dan jadwal shoot.
- **Kalender**: kalender konten IG/TikTok yang statusnya ikut berubah mengikuti produksi. Dilengkapi panel mix pillar dan peringatan.

Stack: FastAPI + MongoDB (backend), React + Tailwind (frontend), APScheduler (email terjadwal). Semua waktu memakai WIB.

## Isi folder

```
backend/    API FastAPI (app/), tes acceptance (tests/), dev_mock.py
frontend/   React + Vite + Tailwind
templates/  Template CSV impor kalender
Dockerfile, docker-compose.yml, .env.example
```

## Mencoba cepat di laptop (tanpa MongoDB)

Data disimpan di memori dan hilang saat server dimatikan, jadi cara ini hanya untuk mencoba.

```bash
cd frontend && npm install && npm run build && cd ..
cd backend && pip install -r requirements-dev.txt && python dev_mock.py
# buka http://localhost:8000
```

Setelah itu: daftar sebagai Brand Lead, buka **Pengaturan → Isi data contoh**, lalu daftarkan anggota lain dari halaman login.

## Deploy (pilih salah satu)

### A. Railway / Render + MongoDB Atlas (paling mudah)
1. Buat database gratis di **MongoDB Atlas** (cluster M0). Salin connection string `mongodb+srv://…`, lalu di Network Access izinkan `0.0.0.0/0` atau IP server.
2. Upload folder ini ke repo GitHub (privat).
3. Di **Railway** (New Project → Deploy from GitHub) atau **Render** (New → Web Service → Docker), pilih repo tersebut. Keduanya otomatis membaca `Dockerfile`.
4. Isi environment variables sesuai `.env.example`. Minimal: `MONGO_URL`, `DB_NAME`, `APP_URL` (URL app setelah deploy), dan `RESEND_API_KEY` + `MAIL_FROM` bila ingin email benar-benar terkirim.
5. Deploy. Buka URL-nya, lalu daftar sebagai Brand Lead / Creative Lead terlebih dulu.

> Scheduler email berjalan di dalam proses app. Di Render paket gratis, app "tidur" saat tidak dipakai sehingga email jadwal bisa terlewat. Pakai paket berbayar paling kecil atau Railway.

### B. Server sendiri (VPS) dengan Docker
```bash
cp .env.example .env   # isi APP_URL & email; MONGO_URL di-override ke container mongo
docker compose up -d --build
# app di http://SERVER:8000 — pasang reverse proxy (Caddy/Nginx) untuk HTTPS
```
Backup otomatis tiap Minggu 02.00 ke folder `./backups` (8 file terakhir disimpan).

### Email
- **Resend** (disarankan): daftar di resend.com, verifikasi domain, lalu isi `RESEND_API_KEY` dan `MAIL_FROM`.
- **SMTP** (Gmail Workspace dll.): isi `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.
- Kalau keduanya kosong, email tidak dikirim tetapi tetap tercatat di **Pengaturan → Email terakhir**, sehingga bisa dicek.

Jadwal default (bisa diubah di Pengaturan):

| Jadwal | Waktu |
|---|---|
| Digest pagi | 08.00 |
| Approval menunggu | 10.00 |
| Pengingat deadline | 15.00 |
| Rekap mingguan | Senin 08.30 |
| Backup | Minggu 02.00 |

Scheduler mengecek tiap 15 menit dan setiap slot hanya dikirim sekali per hari.

## Role

| Fungsi kerja | Role | Bisa apa |
|---|---|---|
| Brand Lead, Marketing Lead, Brand/Marketing Manager | Approver | Semua; ubah status Gate; approve aset ads/berbudget; pengaturan |
| Creative Lead | Creative Lead | Terima/tolak brief, tugaskan PIC, review & QC, pengaturan |
| Graphic Designer, Videographer / Editor | Creative | Kerjakan tugas, isi link output, centang QC pembuat |
| Socmed Specialist, Admin Social Media | Socmed | Kelola kalender, buat brief, caption final |
| Lainnya | Requester | Buat brief, lihat kalender |

Kalau tim belum punya Creative Lead, Brand Lead otomatis mengambil perannya (bisa diubah di Pengaturan). PIN panel default **1234**; ganti di Pengaturan.

## Aturan yang dikunci server

- **Promo / berbudget tanpa Gate GO/GWC** otomatis **Ditahan Gate**. Angka promo wajib punya sumber.
- **Brief OK** butuh brief lengkap: judul, tujuan, tipe, output, key message ≤140 karakter, CTA, dan PIC. Deadline dihitung dari tabel SLA (hari kerja).
- **Maksimal 2 ronde revisi.** Setiap ronde wajib punya catatan. Ronde ke-3 = **Buat brief baru**.
- **Brief terkunci setelah Shoot.** Mengubah key message, output, atau teks wajib = brief baru.
- **Final** butuh QC 9/9, dengan pembuat dan reviewer orang yang berbeda. ADS, aset berbudget, dan POSM promo wajib **approval** Approver.
- **Diserahkan** butuh semua output selesai dengan link file, plus link folder Drive.
- **Kapasitas PIC** (default 6 tugas aktif). Kalau terlampaui, sistem meminta konfirmasi.
- **Kalender:**
  - Maksimal 1 promo per hari.
  - Promo tanpa GO hanya boleh berstatus Idea.
  - Status Posted wajib punya link postingan.
  - Promo yang tayang wajib punya kode tracking.

## Memuat Content Plan November

1. Buka `CBAA_Content_Plan_November_2026.xlsx`, sheet **Kalender November**. Susun kolom seperti `templates/import-kalender-template.csv`, lalu simpan sebagai CSV (pemisah `;` atau `,`).
2. **Kalender → Impor CSV.** Baris yang gagal ditampilkan beserta alasannya.
   - Platform "IG + TikTok" otomatis dibaca sebagai `IG+TT`.
   - `PROMO-TBD` otomatis dijadikan promo dengan Gate PENDING.
   - Status Posted tanpa link tetap diterima, tetapi muncul di peringatan.
3. Buat sesi shoot (Senin 16 & 23 Nov) di **Produksi → Jadwal Shoot**. Request dibuat dari item kalender lewat **Buat brief dari konten**.
4. **Pengaturan → Target pillar**: pilih bulan 2026-11, lalu isi PC 30 · BtK 20 · Lokal 15 · UGC 15 · Promo 10 · Trend 10. Tema mingguan diisi di kolom **Tema** pada tampilan bulan.

## Menjalankan tes

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q
```
Ada 11 tes yang mencakup seluruh acceptance test di spec:
- role
- alur kalender → brief → SLA
- kunci Gate
- batas revisi & brief baru
- brief terkunci setelah shoot
- QC & approval
- aturan kalender
- kapasitas
- mix pillar
- rekap mingguan & kunci PIN
- impor CSV

## Pengembangan lokal (hot reload)

```bash
# terminal 1 (butuh MongoDB lokal di localhost:27017)
cd backend && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev   # http://localhost:5173, /api diteruskan ke :8000
```

## Belum termasuk (iterasi berikutnya di spec)

Fitur berikut sengaja belum dibuat:
- Asset Library
- input performa konten
- Community Log
- integrasi Daily Tracker
- sinkron Gate dari Alignment Board
- notifikasi WhatsApp
- PWA

Realtime saat ini memakai polling 8 detik, yang berhenti otomatis saat tab browser tidak aktif.
