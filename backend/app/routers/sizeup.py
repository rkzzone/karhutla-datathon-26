"""Endpoint lapisan size-up.

Sengaja TERPISAH dari `/api/alerts`, dan itu keputusan arsitektur, bukan
kebetulan penataan berkas:

  - `API_CONTRACT.md` mengunci bentuk objek alert dan wajib identik byte-per-byte
    dengan salinan tim model. Menempelkan blok size-up ke dalam objek itu berarti
    memaksa perubahan kontrak sehari sebelum pembekuan, untuk data yang tim model
    tidak menghasilkan dan tidak mengonsumsi.
  - Size-up adalah lapisan SETELAH deteksi. Memisahkan endpoint membuat batas
    itu terlihat di permukaan HTTP, bukan cuma di diagram slide.

Objek alert tidak bertambah satu field pun karena berkas ini ada. Bentuk respons
di sini didokumentasikan di `SIZEUP_CONTRACT.md`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from ..services import sizeup

router = APIRouter(prefix="/api/sizeup", tags=["sizeup"])


@router.get("")
def ambil_sizeup(
    respons: Response,
    lat: float = Query(ge=-90.0, le=90.0),
    lon: float = Query(ge=-180.0, le=180.0),
    alert_id: str | None = Query(default=None),
) -> dict:
    """Konteks size-up untuk satu koordinat.

    Selalu 200, tidak pernah 503. Alasannya berbeda dari endpoint FIRMS: di sana
    kegagalan berarti seluruh lapisan hilang, jadi 503 + copy galat sudah tepat.
    Di sini kartu terdiri dari blok-blok independen, dan cuaca tetap berguna
    walau Overpass tumbang. Status kegagalan ada di `blok.<nama>.status`, dan UI
    merender blok gagal itu dengan pesannya sendiri — bukan menyembunyikan
    seluruh kartu.
    """
    hasil = sizeup.rakit(lat=lat, lon=lon, alert_id=alert_id)

    # Cache CDN, alasan sama persis dengan endpoint FIRMS: cache dalam proses
    # tidak berguna di lingkungan serverless. 10 menit mengikuti kadensi
    # penyegaran Open-Meteo; `stale-while-revalidate` menjaga panel tetap terisi
    # saat Open-Meteo atau Overpass sedang lambat — termasuk saat rekaman demo.
    #
    # Tidak di-cache kalau ada blok yang gagal: menyimpan kegagalan selama 10
    # menit berarti satu hiccup jaringan mematikan panel jauh lebih lama
    # daripada gangguan yang sebenarnya.
    semua_ada = all(b.get("status") == "ada" for b in hasil["blok"].values())
    if semua_ada:
        respons.headers["Cache-Control"] = (
            "public, s-maxage=600, stale-while-revalidate=3600"
        )
    else:
        respons.headers["Cache-Control"] = "no-store"
    return hasil
