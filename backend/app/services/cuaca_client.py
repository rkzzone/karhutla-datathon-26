"""Klien cuaca Open-Meteo — sumber D1 lapisan size-up.

BATAS YANG TIDAK BOLEH DILANGGAR (larangan nomor 13 di dokumen itu):
cuaca TIDAK PERNAH menjadi masukan model deteksi. Modul ini hanya melayani
lapisan size-up — lapisan keputusan deterministik SETELAH model bicara. Kalau
suatu saat ada yang mengimpor modul ini dari jalur inference, itu bug arsitektur,
bukan optimasi.

Kenapa Open-Meteo: gratis, tanpa kunci API, global, per jam. Tanpa kunci berarti
klaim "tidak ada biaya per-inferensi" di paper dan `estimasi_biaya.md` tetap utuh.

BMKG (sumber D2) sengaja BELUM dipakai: dokumen rencana menandainya "verifikasi
dulu", dan endpoint resminya belum kami uji sendiri. Menyebut BMKG di UI tanpa
menguji endpoint-nya akan jadi klaim kelembagaan yang tidak bisa dipertahankan.

Nama field di bawah sudah diverifikasi terhadap respons sungguhan
(26 Agustus 2026, koordinat -2.15, 113.9) — bukan disalin dari ingatan dokumen.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo menyegarkan data per jam. 10 menit sangat konservatif, dan
# alasannya sama dengan cache FIRMS: satu hiccup jaringan saat rekaman demo
# cukup untuk merusak take.
_TTL_DETIK = 600
_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}

# Hujan harian di bawah nilai ini dihitung sebagai "hari kering". Bukan angka
# karangan: 1 mm adalah ambang lazim "hari hujan" pada praktik pencatatan
# meteorologi. Ditampilkan apa adanya di UI supaya bisa diperiksa, bukan
# disembunyikan di dalam kode.
AMBANG_HARI_KERING_MM = 1.0

MATA_ANGIN = [
    "utara", "timur laut", "timur", "tenggara",
    "selatan", "barat daya", "barat", "barat laut",
]


class CuacaUnavailable(RuntimeError):
    """Cuaca tidak bisa diambil. Panel menampilkan '—', bukan angka rekaan."""

    def __init__(self, alasan: str, detail: str = ""):
        super().__init__(detail or alasan)
        self.alasan = alasan
        self.detail = detail


def arah_mata_angin(derajat: float | None) -> str | None:
    """Derajat → nama arah Indonesia. 8 penjuru sudah cukup untuk brief lisan."""
    if derajat is None:
        return None
    return MATA_ANGIN[int((derajat % 360) / 45 + 0.5) % 8]


def _bulatkan(nilai: float) -> float:
    """Bulatkan koordinat ke ~1 km untuk kunci cache.

    Cuaca tidak berubah bermakna dalam jarak itu, dan alert yang berdekatan jadi
    berbagi satu panggilan.
    """
    return round(nilai, 2)


def ambil_cuaca(lat: float, lon: float) -> dict[str, Any]:
    """Cuaca saat ini + riwayat hujan 7 hari untuk satu koordinat.

    Melempar `CuacaUnavailable` kalau gagal — TIDAK PERNAH mengembalikan nilai
    tebakan. Blok cuaca yang kosong di UI lebih jujur daripada blok yang terisi
    angka yang tidak pernah diukur.
    """
    kunci = (_bulatkan(lat), _bulatkan(lon))
    tersimpan = _cache.get(kunci)
    if tersimpan and (time.monotonic() - tersimpan[0]) < _TTL_DETIK:
        return {**tersimpan[1], "dari_cache": True}

    parameter = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,precipitation,"
            "wind_speed_10m,wind_direction_10m"
        ),
        "daily": "precipitation_sum",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "Asia/Jakarta",
    }
    try:
        respons = httpx.get(_URL, params=parameter, timeout=15.0)
        respons.raise_for_status()
        badan = respons.json()
    except (httpx.HTTPError, ValueError) as galat:
        logger.error("Open-Meteo gagal: %s", type(galat).__name__)
        raise CuacaUnavailable("upstream_error", type(galat).__name__) from galat

    saat_ini = badan.get("current") or {}
    harian = badan.get("daily") or {}
    if not saat_ini:
        raise CuacaUnavailable("upstream_error", "respons tanpa blok `current`")

    arah_dari = saat_ini.get("wind_direction_10m")
    hasil = {
        "sumber": "Open-Meteo",
        "sumber_url": "https://open-meteo.com/",
        "waktu_pengamatan": saat_ini.get("time"),
        "zona_waktu": badan.get("timezone"),
        "suhu_c": saat_ini.get("temperature_2m"),
        "kelembapan_persen": saat_ini.get("relative_humidity_2m"),
        "hujan_mm": saat_ini.get("precipitation"),
        "angin_kmj": saat_ini.get("wind_speed_10m"),
        # Konvensi meteorologi: `wind_direction_10m` adalah arah angin DATANG.
        # Dua field terpisah supaya UI tidak pernah salah baca yang satu sebagai
        # yang lain — kekeliruan itu akan membalik kerucut proyeksi 180°.
        "arah_angin_deg": arah_dari,
        "arah_angin_mata": arah_mata_angin(arah_dari),
        "arah_rambatan_deg": None if arah_dari is None else (arah_dari + 180) % 360,
        "arah_rambatan_mata": arah_mata_angin(None if arah_dari is None else arah_dari + 180),
        "riwayat_hujan": _riwayat_hujan(harian),
    }
    _cache[kunci] = (time.monotonic(), hasil)
    return {**hasil, "dari_cache": False}


_cache_noon: dict[tuple[float, float, int], tuple[float, list[dict[str, Any]]]] = {}
_TTL_NOON = 3600


def ambil_deret_tengah_hari(lat: float, lon: float, hari: int) -> list[dict[str, Any]]:
    """Deret harian nilai TENGAH HARI waktu setempat — masukan sistem FWI.

    Sistem FWI didefinisikan atas pengamatan pukul 12.00 waktu standar setempat,
    dengan hujan yang diakumulasi 24 jam sampai saat itu. Memakai rata-rata
    harian sebagai gantinya akan menghasilkan angka yang bukan FWI, hanya mirip
    FWI — jadi jam-jamannya diambil dan disaring, bukan disederhanakan.

    Hujan dijumlahkan dari pukul 12.00 kemarin sampai 12.00 hari ini, persis
    definisi `ro` di van Wagner (1987).
    """
    kunci = (_bulatkan(lat), _bulatkan(lon), hari)
    tersimpan = _cache_noon.get(kunci)
    if tersimpan and (time.monotonic() - tersimpan[0]) < _TTL_NOON:
        return tersimpan[1]

    parameter = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
        "past_days": min(hari, 92),
        "forecast_days": 1,
        "timezone": "Asia/Jakarta",
    }
    try:
        respons = httpx.get(_URL, params=parameter, timeout=30.0)
        respons.raise_for_status()
        badan = respons.json()
    except (httpx.HTTPError, ValueError) as galat:
        logger.error("Open-Meteo (deret jam) gagal: %s", type(galat).__name__)
        raise CuacaUnavailable("upstream_error", type(galat).__name__) from galat

    jam = badan.get("hourly") or {}
    waktu = jam.get("time") or []
    if not waktu:
        raise CuacaUnavailable("upstream_error", "respons tanpa blok `hourly`")

    suhu = jam.get("temperature_2m") or []
    lembap = jam.get("relative_humidity_2m") or []
    angin = jam.get("wind_speed_10m") or []
    hujan = jam.get("precipitation") or []

    # Indeks tiap pukul 12.00 setempat. Open-Meteo mengembalikan waktu lokal
    # karena `timezone` diminta, jadi pencocokan string sudah tepat dan tidak
    # perlu konversi zona lagi.
    indeks_siang = [i for i, t in enumerate(waktu) if t.endswith("T12:00")]

    deret: list[dict[str, Any]] = []
    for i in indeks_siang:
        awal = i - 24
        if awal < 0:
            # Hari pertama tidak punya 24 jam sebelumnya — dilewati, bukan
            # ditambal nol. Hujan nol palsu akan menaikkan FWI secara keliru.
            continue
        potongan = [h for h in hujan[awal + 1 : i + 1] if isinstance(h, (int, float))]
        deret.append(
            {
                "tanggal": waktu[i][:10],
                "suhu_c": suhu[i] if i < len(suhu) else None,
                "kelembapan_persen": lembap[i] if i < len(lembap) else None,
                "angin_kmj": angin[i] if i < len(angin) else None,
                "hujan_24jam_mm": round(sum(potongan), 2) if potongan else None,
            }
        )

    _cache_noon[kunci] = (time.monotonic(), deret)
    return deret


def _riwayat_hujan(harian: dict[str, Any]) -> dict[str, Any]:
    """Turunan deterministik dari `daily.precipitation_sum` — bukan model.

    `hari_kering_berturut` dihitung mundur dari hari terakhir yang datanya ada,
    dan hari berjalan ikut dihitung.

    `terpotong_jendela` menandai kasus yang mudah dibaca keliru: kalau SELURUH
    hari dalam jendela ternyata kering, hitungan yang sebenarnya bisa jauh lebih
    panjang dari jendela — kami cuma tidak melihatnya. UI wajib merender itu
    sebagai "≥ N hari", bukan "N hari", supaya angkanya tidak dibaca sebagai
    batas atas yang terkonfirmasi.
    """
    tanggal = harian.get("time") or []
    jumlah = harian.get("precipitation_sum") or []
    pasangan = [
        (t, n) for t, n in zip(tanggal, jumlah) if isinstance(n, (int, float))
    ]
    if not pasangan:
        return {
            "hari_kering_berturut": None,
            "terpotong_jendela": False,
            "jendela_hari": 0,
            "hujan_24jam_mm": None,
            "hujan_7hari_mm": None,
            "ambang_hari_kering_mm": AMBANG_HARI_KERING_MM,
            "harian": [],
        }

    berturut = 0
    for _, nilai in reversed(pasangan):
        if nilai < AMBANG_HARI_KERING_MM:
            berturut += 1
        else:
            break

    return {
        "hari_kering_berturut": berturut,
        "terpotong_jendela": berturut == len(pasangan),
        "jendela_hari": len(pasangan),
        "hujan_24jam_mm": round(pasangan[-1][1], 1),
        "hujan_7hari_mm": round(sum(n for _, n in pasangan[-7:]), 1),
        "ambang_hari_kering_mm": AMBANG_HARI_KERING_MM,
        "harian": [{"tanggal": t, "hujan_mm": round(n, 1)} for t, n in pasangan[-7:]],
    }
