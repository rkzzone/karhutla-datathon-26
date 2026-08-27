"""FastAPI — Dashboard Operator Deteksi Dini Karhutla Gambut (tim produk).

Jalankan: `cd backend && uvicorn app.main:app --reload`
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import alerts, firms, inference, iot_simulation, sizeup
from .services import model_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Deteksi Dini Karhutla Gambut — API Operator",
    version="0.9.0",
    description=(
        "Backend dashboard operator. Bentuk respons alert dikunci oleh "
        "API_CONTRACT.md — jangan tambah/kurangi field tanpa menyalin perubahan "
        "kontrak ke direktori tim model."
    ),
)

# CORS terbuka — disengaja, dan wajib begitu karena respons di-cache CDN.
#
# Semula memakai daftar origin + regex *.vercel.app. Itu membuat respons
# bergantung pada header `Origin`, sehingga Starlette menambahkan `Vary: Origin`.
# Vercel CDN TIDAK menghormati Vary itu: salinan pertama yang tersimpan berasal
# dari permintaan tanpa `Origin` (mis. curl atau health check), sehingga tidak
# membawa `Access-Control-Allow-Origin` sama sekali — lalu salinan buta-CORS itu
# disajikan ke semua browser dan fetch-nya diblokir. Gejalanya menyesatkan:
# preflight OPTIONS lolos, GET-nya gagal, dan di UI muncul "kode: jaringan".
#
# Membuka ke `*` menghilangkan ketergantungan pada Origin, sehingga satu salinan
# cache sah untuk semua pemanggil.
#
# Aman di sini, dan bukan sekadar jalan pintas:
#   - `allow_credentials=False` — tidak ada cookie/kredensial yang ikut
#   - Respons hanya berisi data publik: hotspot NASA, keluaran model, sensor
#     simulasi. Tidak ada data pengguna.
#   - MAP_KEY tetap di server dan tidak pernah masuk respons
# CORS memang tidak pernah jadi batas keamanan untuk PATCH — server mana pun
# bisa memanggilnya. Perlindungan sesungguhnya, kalau nanti dibutuhkan, harus
# berupa autentikasi, bukan daftar origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Data-Simulated", "X-Data-Fixture"],
)

@app.middleware("http")
async def cors_tanpa_syarat(permintaan, panggil_berikutnya):
    """Pastikan `Access-Control-Allow-Origin: *` ADA di setiap respons.

    CORSMiddleware Starlette hanya menambahkan header itu kalau permintaan
    membawa `Origin`. Health check, curl, dan crawler tidak membawanya — dan
    justru respons dari permintaan seperti itulah yang sering lebih dulu masuk
    CDN. Salinan tanpa header CORS lalu disajikan ke browser dan diblokir.

    Menyetelnya tanpa syarat membuat SEMUA salinan cache identik dan sah untuk
    siapa pun. Ini yang membuat `s-maxage` di endpoint FIRMS aman dipakai.
    """
    respons = await panggil_berikutnya(permintaan)
    respons.headers.setdefault("Access-Control-Allow-Origin", "*")
    return respons


app.include_router(alerts.router)
app.include_router(inference.router)
app.include_router(firms.router)
app.include_router(iot_simulation.router)
app.include_router(sizeup.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Ringkasan jujur soal dari mana tiap bagian data berasal saat ini."""
    alert = model_client.status_sumber()
    # Stage 10 tercapai begitu alert berasal dari model sungguhan — lewat layanan
    # hidup ATAU lewat batch offline. Sebelumnya baris ini cuma mengecek
    # MODEL_SERVICE_URL, sehingga tetap melapor "9" padahal seluruh angkanya
    # sudah keluaran fusion_v3_localization.pth.
    return {
        "status": "ok",
        "stage": "9" if alert["sumber"] == "mock" else "10",
        "alert": alert,
        "firms": {
            "map_key_terpasang": bool(settings.map_key),
            "mode_fixture": settings.firms_fixture and not settings.map_key,
        },
        "iot": {"simulasi": True},
        # Lapisan size-up tidak menyentuh model sama sekali — ia aturan
        # deterministik di atas cuaca dan peta terbuka. Dilaporkan di sini
        # supaya pemisahan itu terlihat dari luar, bukan cuma di slide.
        "sizeup": {
            "lapisan": "aturan_deterministik",
            "sumber": ["Open-Meteo", "OpenStreetMap"],
            "butuh_kunci_api": False,
            "masuk_ke_model": False,
        },
    }
