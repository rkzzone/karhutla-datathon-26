"""Endpoint hotspot FIRMS (Stage 11).

Kalau FIRMS tidak bisa dipakai, endpoint ini menjawab 503 dengan pesan persis
seperti DESIGN_BRIEF Bagian 6 — frontend menampilkannya apa adanya, bukan
menerjemahkan ulang jadi "Terjadi kesalahan".
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from ..services import firms_client

router = APIRouter(prefix="/api/firms", tags=["firms"])

PESAN_GAGAL = (
    "Data hotspot satelit tidak bisa dimuat. Coba lagi dalam beberapa menit, "
    "atau lanjutkan dengan sumber pemicu lain."
)


@router.get("/hotspots")
def hotspots(
    respons: Response,
    hari: int = Query(default=2, ge=1, le=7),
    sumber: str = Query(default="VIIRS_SNPP_NRT"),
    batas: int = Query(default=400, ge=1, le=5000),
    tanggal: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> dict:
    """Hotspot dalam AOI, dipangkas ke `batas` titik terkuat menurut FRP.

    Kenapa dipangkas: di puncak musim kemarau, AOI Sumatra-Kalimantan bisa
    mengembalikan >2.000 titik (313 KB). Merender sebanyak itu sebagai marker
    Leaflet membuat peta tersendat dan justru menyembunyikan alert model di
    baliknya. Titik dengan FRP tertinggi yang dipertahankan — itu yang paling
    relevan buat operator.

    `jumlah` tetap melaporkan TOTAL yang ditemukan satelit, bukan yang dikirim,
    supaya UI bisa jujur menyebut "menampilkan N dari M".

    KENAPA `hari` DEFAULTNYA 2, BUKAN 1.
    Diamati 27 Agustus 2026 pukul 05.30 WIB: `hari=1` mengembalikan **nol titik**
    di seluruh AOI Sumatra-Kalimantan, sementara `hari=2` mengembalikan 4.712 —
    semuanya bertanggal kemarin. Sebabnya bukan tidak ada api, melainkan data
    VIIRS NRT untuk hari berjalan belum terbit; lintasan satelit dan jeda
    publikasinya 3-6 jam.

    Itu persis jeda yang jadi alasan produk ini ada, dan dengan default 1 ia
    berbalik menyerang tampilannya sendiri: operator yang membuka konsol pagi
    hari melihat peta kosong dan menyimpulkan tidak ada apa-apa. Jendela dua
    hari menutupi jeda publikasi tanpa menambah kebisingan berarti.
    """
    try:
        hasil = firms_client.ambil_hotspot(hari=hari, sumber=sumber, tanggal=tanggal)
    except firms_client.FirmsUnavailable as galat:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"alasan": galat.alasan, "pesan": PESAN_GAGAL},
        ) from galat

    titik = hasil.get("titik", [])
    hasil["jumlah_total"] = len(titik)
    if len(titik) > batas:
        titik = sorted(titik, key=lambda t: (t.get("frp_mw") or 0.0), reverse=True)[:batas]
        hasil["titik"] = titik
        hasil["dipangkas"] = True
    else:
        hasil["dipangkas"] = False
    hasil["jumlah"] = len(titik)

    if hasil.get("is_fixture"):
        respons.headers["X-Data-Fixture"] = "true"
    else:
        # Cache di tingkat CDN, bukan cuma di proses.
        #
        # Cache dalam proses (firms_client._cache) tidak berguna di lingkungan
        # serverless: tiap invokasi dingin memulai proses baru dan cache-nya
        # kosong. Header ini memindahkan tanggung jawab itu ke CDN, yang justru
        # lebih baik daripada cache proses:
        #   s-maxage=300              → CDN menyajikan salinan 5 menit
        #   stale-while-revalidate    → kalau sudah basi, sajikan yang lama
        #                               SEKARANG lalu segarkan di latar belakang
        # Efeknya: setelah satu panggilan berhasil, pengunjung tidak pernah lagi
        # menunggu NASA — bahkan saat NASA sedang lambat atau tumbang.
        respons.headers["Cache-Control"] = (
            "public, s-maxage=300, stale-while-revalidate=3600"
        )
    return hasil
