"""Klien NASA FIRMS (Stage 11).

API key dibaca dari environment (`MAP_KEY`) — tidak pernah di-hardcode dan
tidak pernah dikirim ke frontend. Frontend hanya melihat hasil parsing.

Endpoint FIRMS yang dipakai (CSV, area):
    https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAYS}

Kalau MAP_KEY belum ada, fungsi ini melempar `FirmsUnavailable` — BUKAN
mengarang hotspot. Router menerjemahkannya jadi 503 dan UI menampilkan copy
error dari DESIGN_BRIEF Bagian 6.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
from typing import Any

import httpx

from ..config import MOCK_DATA_DIR, settings

logger = logging.getLogger(__name__)

# Cache dalam proses. FIRMS NRT diperbarui beberapa jam sekali, jadi 5 menit
# sangat konservatif — tidak ada data yang terlewat.
#
# Dua alasan, keduanya nyata:
#  1. Panggilan ke NASA makan 2,5-4 detik (pernah 20 detik). Tanpa cache, tiap
#     buka Halaman 1 menunggu selama itu.
#  2. Saat rekaman demo, satu hiccup jaringan cukup untuk merusak take. Dengan
#     cache, respons terakhir yang berhasil tetap tersaji.
#
# Kuota MAP_KEY 5.000 transaksi / 10 menit juga jadi lebih aman.
_TTL_DETIK = 300
_cache: dict[tuple[int, str, str], tuple[float, dict[str, Any]]] = {}

_BASIS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
_SUMBER_DEFAULT = "VIIRS_SNPP_NRT"
_FIXTURE_PATH = MOCK_DATA_DIR / "firms_fixture.json"


class FirmsUnavailable(RuntimeError):
    """FIRMS tidak bisa dipakai: key belum diisi, jaringan gagal, atau 4xx/5xx."""

    def __init__(self, alasan: str, detail: str = ""):
        super().__init__(detail or alasan)
        self.alasan = alasan
        self.detail = detail


def _angka(nilai: str) -> float | None:
    try:
        return float(nilai)
    except (TypeError, ValueError):
        return None


def _normalkan(baris: dict[str, str]) -> dict[str, Any]:
    """Samakan bentuk lintas sumber (MODIS pakai `brightness`, VIIRS `bright_ti4`)."""
    jam = (baris.get("acq_time") or "0000").zfill(4)
    return {
        "lat": _angka(baris.get("latitude", "")),
        "lon": _angka(baris.get("longitude", "")),
        "kecerahan_k": _angka(baris.get("bright_ti4") or baris.get("brightness", "")),
        "frp_mw": _angka(baris.get("frp", "")),
        "keyakinan": (baris.get("confidence") or "").strip() or None,
        "satelit": (baris.get("satellite") or "").strip() or None,
        "waktu_akuisisi": f"{baris.get('acq_date', '')}T{jam[:2]}:{jam[2:]}:00Z",
        "siang_malam": (baris.get("daynight") or "").strip() or None,
    }


def _muat_fixture() -> list[dict[str, Any]]:
    with _FIXTURE_PATH.open(encoding="utf-8") as berkas:
        return json.load(berkas)


def ambil_hotspot(
    hari: int = 1, sumber: str = _SUMBER_DEFAULT, tanggal: str | None = None
) -> dict[str, Any]:
    """Kembalikan hotspot dalam AOI.

    `tanggal` (YYYY-MM-DD) mengambil arsip untuk hari tertentu alih-alih hari
    terakhir. Dipakai untuk MENGUNCI data demo pada satu kejadian kebakaran yang
    tercatat, supaya rekaman tidak bergantung pada apa yang kebetulan terbakar
    di hari perekaman. Datanya tetap deteksi satelit sungguhan; yang dipilih
    hanya tanggalnya, dan UI wajib menampilkan tanggal itu.

    `is_fixture=True` berarti data contoh untuk dev/screenshot, bukan satelit
    sungguhan — UI wajib melabelinya.
    """
    kunci = (hari, sumber, tanggal or "terakhir")
    tersimpan = _cache.get(kunci)
    if tersimpan and (time.monotonic() - tersimpan[0]) < _TTL_DETIK:
        return {**tersimpan[1], "dari_cache": True}

    if not settings.map_key:
        if settings.firms_fixture:
            logger.warning("MAP_KEY kosong — menyajikan fixture FIRMS (dev only)")
            titik = _muat_fixture()
            return {
                "is_fixture": True,
                "sumber": sumber,
                "rentang_hari": hari,
                "jumlah": len(titik),
                "titik": titik,
            }
        raise FirmsUnavailable("map_key_missing", "MAP_KEY belum diisi di .env")

    url = f"{_BASIS_URL}/{settings.map_key}/{sumber}/{settings.aoi.as_firms_area()}/{hari}"
    if tanggal:
        url = f"{url}/{tanggal}"
    try:
        respons = httpx.get(url, timeout=20.0)
        respons.raise_for_status()
    except httpx.HTTPError as galat:
        # Jangan pernah bocorkan URL — MAP_KEY ada di dalamnya.
        logger.error("FIRMS gagal: %s", type(galat).__name__)
        raise FirmsUnavailable("upstream_error", type(galat).__name__) from galat

    teks = respons.text.strip()
    if not teks or teks.lower().startswith("invalid"):
        raise FirmsUnavailable("upstream_error", "respons FIRMS tidak bisa dibaca")

    pembaca = csv.DictReader(io.StringIO(teks))
    titik = [_normalkan(baris) for baris in pembaca]
    titik = [t for t in titik if t["lat"] is not None and t["lon"] is not None]
    hasil = {
        "is_fixture": False,
        "sumber": sumber,
        "rentang_hari": hari,
        "tanggal_arsip": tanggal,
        "jumlah": len(titik),
        "titik": titik,
    }
    _cache[kunci] = (time.monotonic(), hasil)
    return {**hasil, "dari_cache": False}
