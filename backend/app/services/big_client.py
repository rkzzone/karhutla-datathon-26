"""Klien Badan Informasi Geospasial (BIG) — geoportal nasional.

Dua hal diambil dari sini, keduanya per koordinat, gratis, tanpa kunci API:

  1. **Wilayah administratif** sampai tingkat desa/kelurahan, berikut kode
     Kemendagri (`KDEPUM`). Kode inilah yang membuka pintu ke prakiraan resmi
     BMKG, yang hanya menerima kode wilayah dan tidak menerima lintang/bujur.
     Rantainya jadi: koordinat → BIG → kode desa → BMKG.
  2. **Penutup lahan** skala 1:250.000.

=============================================================================
 PETA GAMBUT: APA YANG DICARI, APA YANG SEBENARNYA ADA
=============================================================================
Yang dicari adalah layanan "Sumber Daya Alam dan Lingkungan" berisi Peta Lahan
Gambut, Kesatuan Hidrologis Gambut (KHG), dan Fungsi Ekosistem Gambut.

Yang ditemukan setelah menyapu server BIG secara menyeluruh (26 Agustus 2026):
**78 layanan, 982 layer diperiksa satu per satu — nol layer gambut atau KHG.**
Penyaringan memakai pola `gambut|peat|khg|hidrologis|rawa`; satu-satunya yang
cocok adalah "Rawan Tsunami", "Rawan Gempa Bumi", dan "Rawan Gerakan Tanah",
yaitu kata "rawan", bukan "rawa". Layanan bertema alam yang ada adalah seri
Atlas 250K — penutup lahan, hidrogeologi, rawan bencana — tanpa layer gambut.

Host gambut lain yang dicoba (`sigap.menlhk.go.id`, `geoportal.menlhk.go.id`,
`geoportal.brgm.go.id`) tidak ada dalam DNS; `portal.ina-sdi.or.id` gagal TLS.

Skrip penyapuannya ada di `backend/scripts/sapu_layer_big.py` supaya klaim
"tidak ada" ini bisa diperiksa ulang siapa pun, bukan dipercaya begitu saja.

Karena itu blok yang disajikan adalah **penutup lahan**, bukan status gambut.
Penutup lahan menjawab pertanyaan size-up yang nyata dan berbeda ("api ini di
perkebunan, hutan rimba, atau permukiman?") dan tidak pernah diberi label
sebagai penanda gambut. Kelas rawa ditandai sebagai **indikasi** lahan basah,
bukan sebagai penetapan KHG — penetapan KHG adalah dokumen hukum dan tidak
boleh disimpulkan dari peta penutup lahan.
=============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_BASIS = "https://geoservices.big.go.id/gis/rest/services"
_LAYER_DESA = f"{_BASIS}/BAPANAS/Batas_Administrasi/MapServer/2/query"
_LAYER_PENUTUP = f"{_BASIS}/PTRA/Atlas_250K_PenutupLahan/MapServer/8/query"

# Batas administrasi dan penutup lahan 250K tidak berubah dalam hitungan bulan.
_TTL_DETIK = 86_400
_cache: dict[tuple[str, float, float], tuple[float, Any]] = {}

_HEADER = {"User-Agent": "karhutla-dashboard-operator/0.9"}

# Kelas penutup lahan yang MENGINDIKASIKAN lahan basah. Bukan daftar kelas
# gambut — tidak ada kelas gambut di peta ini. Dipakai hanya untuk menyalakan
# catatan "indikasi lahan basah", tidak pernah untuk menyatakan status KHG.
_KELAS_RAWA = {"50201", "50203", "50205"}
_KATA_RAWA = ("rawa", "gambut", "mangrove")


class BigUnavailable(RuntimeError):
    """Geoportal BIG tidak bisa dipakai. Blok terkait melapor gagal."""

    def __init__(self, alasan: str, detail: str = ""):
        super().__init__(detail or alasan)
        self.alasan = alasan
        self.detail = detail


def _kueri_titik(url: str, lat: float, lon: float, field: str) -> list[dict[str, Any]]:
    parameter = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": field,
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        respons = httpx.get(f"{url}?{urlencode(parameter)}", headers=_HEADER, timeout=40.0)
        respons.raise_for_status()
        badan = respons.json()
    except (httpx.HTTPError, ValueError) as galat:
        logger.warning("BIG gagal (%s): %s", url.rsplit("/", 3)[1], type(galat).__name__)
        raise BigUnavailable("upstream_error", type(galat).__name__) from galat

    # ArcGIS membalas 200 dengan badan {"error": {...}} — status HTTP saja tidak
    # cukup untuk menyimpulkan berhasil.
    if isinstance(badan, dict) and badan.get("error"):
        pesan = str(badan["error"].get("message", ""))[:120]
        raise BigUnavailable("upstream_error", pesan)

    return [f.get("attributes", {}) for f in (badan.get("features") or [])]


def ambil_wilayah(lat: float, lon: float) -> dict[str, Any]:
    """Desa/kelurahan yang memuat titik ini, berikut kode Kemendagri."""
    kunci = ("wilayah", round(lat, 4), round(lon, 4))
    tersimpan = _cache.get(kunci)
    if tersimpan and (time.monotonic() - tersimpan[0]) < _TTL_DETIK:
        return {**tersimpan[1], "dari_cache": True}

    fitur = _kueri_titik(
        _LAYER_DESA, lat, lon, "NAMOBJ,KDEPUM,KDCPUM,KDPKAB,WADMKD,WADMKC,WADMKK,WADMPR"
    )
    if not fitur:
        raise BigUnavailable("di_luar_cakupan", "titik tidak jatuh di poligon desa mana pun")

    a = fitur[0]
    hasil = {
        "sumber": "Badan Informasi Geospasial (BIG)",
        "sumber_layanan": "BAPANAS/Batas_Administrasi — Batas Wilayah Kelurahan/Desa",
        "kode_desa": a.get("KDEPUM"),
        "kode_kecamatan": a.get("KDCPUM"),
        "kode_kabupaten": a.get("KDPKAB"),
        "desa": a.get("WADMKD") or a.get("NAMOBJ"),
        "kecamatan": a.get("WADMKC"),
        "kabupaten": a.get("WADMKK"),
        "provinsi": a.get("WADMPR"),
    }
    _cache[kunci] = (time.monotonic(), hasil)
    return {**hasil, "dari_cache": False}


def ambil_penutup_lahan(lat: float, lon: float) -> dict[str, Any]:
    """Kelas penutup lahan BIG 1:250.000 di titik ini."""
    kunci = ("penutup", round(lat, 4), round(lon, 4))
    tersimpan = _cache.get(kunci)
    if tersimpan and (time.monotonic() - tersimpan[0]) < _TTL_DETIK:
        return {**tersimpan[1], "dari_cache": True}

    fitur = _kueri_titik(_LAYER_PENUTUP, lat, lon, "KODE_UNSUR,NAMA_UNSUR,SNI250K")
    if not fitur:
        raise BigUnavailable("di_luar_cakupan", "titik tidak jatuh di poligon penutup lahan")

    a = fitur[0]
    nama = (a.get("NAMA_UNSUR") or "").strip()
    kode = (a.get("KODE_UNSUR") or "").strip()
    indikasi_rawa = kode in _KELAS_RAWA or any(k in nama.lower() for k in _KATA_RAWA)

    hasil = {
        "sumber": "Badan Informasi Geospasial (BIG)",
        "sumber_layanan": "PTRA/Atlas_250K_PenutupLahan — Penutup Lahan Skala 1:250.000",
        "skala": "1:250.000",
        "kode": kode or None,
        "nama": nama or None,
        "sni": (a.get("SNI250K") or "").strip() or None,
        "indikasi_lahan_basah": indikasi_rawa,
    }
    _cache[kunci] = (time.monotonic(), hasil)
    return {**hasil, "dari_cache": False}
