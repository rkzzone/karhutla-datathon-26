"""Klien OpenStreetMap/Overpass — sumber D4 lapisan size-up.

Menjawab dua kebutuhan size-up yang disebut narasumber polisi hutan: **sumber
air** dan **akses**. Keduanya data terbuka, gratis, tanpa kunci — sehingga klaim
"tidak ada biaya per-inferensi" tetap utuh.

Kanal gambut ikut dicari secara eksplisit (`waterway=canal`): narasumber
menyebut kanal sebagai infrastruktur mitigasi karhutla yang sengaja dibangun di
lahan gambut, jadi ia sumber air terdekat yang paling relevan di sana — bukan
sekadar garis air biasa.

Kepadatan data di Sumatra/Kalimantan bervariasi. Dokumen rencana mewajibkan
pengecekan sebelum diandalkan; hasil pengecekan di koordinat demo
-2.7148, 114.2213 (26 Agustus 2026): Sungai Kahayan 3,0 km, kanal 4,6 km, jalan
tertiary 4,1 km. Kalau di koordinat lain hasilnya kosong, blok yang bersangkutan
melapor kosong apa adanya — tidak diisi tebakan.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Overpass adalah infrastruktur sukarela dengan slot terbatas per IP, dan ia
# memblokir agresif: dua kueri uji berturut-turut dari mesin pengembangan sudah
# cukup untuk membuat `overpass-api.de` menolak koneksi di tingkat TLS (diamati
# 26 Agustus 2026). Karena itu tiga hal sekaligus:
#
#   1. Daftar mirror, dicoba berurutan.
#   2. User-Agent yang menyebut aplikasi — ini etiket wajib Overpass, dan
#      klien tanpa identitas memang lebih cepat diblokir.
#   3. Cache 24 jam + skrip pembekuan (`scripts/bekukan_sizeup.py`).
#
# Butir 3 yang sebenarnya menyelamatkan demo. Overpass TIDAK BOLEH jadi
# ketergantungan hidup saat rekaman: kalau ia menolak di menit ketiga video,
# panel size-up kosong dan tidak ada cara memperbaikinya di tempat.
_ENDPOINT = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
_HEADER = {
    "User-Agent": (
        "karhutla-dashboard-operator/0.9 "
        "(dasbor operator deteksi dini karhutla; pemakaian rendah, hasil di-cache 24 jam)"
    ),
    "Content-Type": "text/plain; charset=utf-8",
}

# Geografi tidak berubah dalam hitungan jam. TTL panjang menjaga kuota Overpass
# (layanan sukarela, punya batas wajar) dan membuat panel size-up terbuka
# seketika untuk alert yang sudah pernah dilihat.
_TTL_DETIK = 86_400
_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}

# Pencarian berjenjang, bukan satu radius besar.
#
# Overpass TIDAK mengurutkan hasil menurut jarak, dan `out geom N` memotong di
# angka N. Satu query radius 12 km bisa memotong justru fitur terdekat dan
# menyisakan yang jauh — hasilnya panel akan melaporkan "air terdekat 9 km"
# padahal ada sungai 800 m. Radius kecil dulu membuat pemotongan itu tidak
# pernah mengikat: kalau ada hasil di 2 km, jumlahnya sedikit dan semuanya muat.
#
# Jenjang dimulai di 5 km, bukan 2 km, dan itu perubahan yang dibayar mahal
# untuk dipelajari: radius 2 km hampir tidak pernah menemukan sungai DAN jalan
# sekaligus di koordinat gambut yang jarang terpetakan, sehingga ia praktis
# selalu menjadi satu kueri terbuang yang tetap dihitung penuh oleh penjatah
# Overpass. Menghapusnya memotong beban kueri hampir separuh.
_JENJANG_KM = (5, 12)

_JENIS_AIR = {
    "river": "Sungai",
    "canal": "Kanal",
    "stream": "Anak sungai",
    "drain": "Parit",
    "water": "Badan air",
}
_JENIS_JALAN = {
    "motorway": "Jalan bebas hambatan",
    "trunk": "Jalan nasional",
    "primary": "Jalan primer",
    "secondary": "Jalan sekunder",
    "tertiary": "Jalan tersier",
    "unclassified": "Jalan desa",
    "residential": "Jalan permukiman",
    "service": "Jalan servis",
    "track": "Jalan setapak/kebun",
}


class OsmUnavailable(RuntimeError):
    """Overpass tidak bisa dipakai. Blok air/akses melapor gagal, bukan kosong."""

    def __init__(self, alasan: str, detail: str = ""):
        super().__init__(detail or alasan)
        self.alasan = alasan
        self.detail = detail


def jarak_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine. Cukup akurat untuk jarak size-up (satuan kilometer)."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def arah_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing awal dari titik alert ke fitur, 0 derajat = utara."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _kueri(lat: float, lon: float, radius_m: int) -> str:
    sekitar = f"around:{radius_m},{lat},{lon}"
    return (
        "[out:json][timeout:30];\n"
        "(\n"
        f'  way({sekitar})["waterway"~"^(river|canal|stream|drain)$"];\n'
        f'  way({sekitar})["natural"="water"];\n'
        ");\n"
        "out geom 60;\n"
        f'way({sekitar})["highway"~"^(motorway|trunk|primary|secondary|tertiary'
        '|unclassified|residential|service|track)$"];\n'
        "out geom 80;\n"
    )


def _titik_terdekat(lat: float, lon: float, geometri: list[dict]) -> tuple[float, dict] | None:
    """Jarak ke simpul TERDEKAT pada suatu jalur, bukan ke titik tengahnya.

    Perbedaannya besar dan bukan detail akademis: sungai sepanjang 20 km yang
    melintas 500 m dari titik alert punya centroid belasan kilometer jauhnya.
    Memakai centroid akan membuat panel melaporkan sumber air jauh padahal
    airnya persis di sebelah.
    """
    terbaik = None
    for simpul in geometri:
        p_lat, p_lon = simpul.get("lat"), simpul.get("lon")
        if p_lat is None or p_lon is None:
            continue
        d = jarak_km(lat, lon, p_lat, p_lon)
        if terbaik is None or d < terbaik[0]:
            terbaik = (d, {"lat": p_lat, "lon": p_lon})
    return terbaik


def _kumpulkan(lat: float, lon: float, elemen: list[dict]) -> tuple[list[dict], list[dict]]:
    air: list[dict] = []
    jalan: list[dict] = []
    for e in elemen:
        tag = e.get("tags") or {}
        terdekat = _titik_terdekat(lat, lon, e.get("geometry") or [])
        if terdekat is None:
            continue
        d, titik = terdekat

        jenis_air = tag.get("waterway") or ("water" if tag.get("natural") == "water" else None)
        jenis_jalan = tag.get("highway")
        if jenis_air in _JENIS_AIR:
            air.append(
                {
                    "jenis": jenis_air,
                    "jenis_nama": _JENIS_AIR[jenis_air],
                    "nama": tag.get("name"),
                    "jarak_km": round(d, 2),
                    "arah_deg": round(arah_deg(lat, lon, titik["lat"], titik["lon"]), 1),
                    "lat": titik["lat"],
                    "lon": titik["lon"],
                    "kanal_gambut": jenis_air == "canal",
                }
            )
        elif jenis_jalan in _JENIS_JALAN:
            jalan.append(
                {
                    "jenis": jenis_jalan,
                    "jenis_nama": _JENIS_JALAN[jenis_jalan],
                    "nama": tag.get("name"),
                    "jarak_km": round(d, 2),
                    "arah_deg": round(arah_deg(lat, lon, titik["lat"], titik["lon"]), 1),
                    "lat": titik["lat"],
                    "lon": titik["lon"],
                    # Jalan setapak/servis bisa dilalui roda dua, belum tentu oleh
                    # kendaraan pengangkut alat mekanis. Dibedakan karena inilah
                    # yang menentukan saran tingkat peralatan.
                    "kendaraan_berat": jenis_jalan not in {"track", "service"},
                }
            )

    air.sort(key=lambda x: x["jarak_km"])
    jalan.sort(key=lambda x: x["jarak_km"])
    return _ringkas(air), _ringkas(jalan)


def _ringkas(fitur: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sisakan yang TERDEKAT per (jenis, nama) — buang ruas kembar.

    OSM memecah satu sungai atau satu jalan menjadi banyak ruas terpisah. Tanpa
    ini, panel menampilkan "Sungai 3,0 km · Sungai 3,1 km · Sungai 3,3 km" —
    tiga baris yang sebenarnya benda yang sama, memakan seluruh ruang daftar dan
    menyembunyikan kanal atau jalan lain yang justru pilihan berbeda.

    Yang dicari operator adalah pilihan yang BERBEDA, bukan ruas terdekat kedua
    dari benda yang sama. Daftar sudah terurut menaik saat masuk sini, jadi yang
    pertama muncul per kunci memang yang terdekat.
    """
    terlihat: set[tuple[str, str | None]] = set()
    hasil: list[dict[str, Any]] = []
    for f in fitur:
        kunci = (f["jenis"], f["nama"])
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        hasil.append(f)
    return hasil


def _panggil(kueri: str) -> list[dict]:
    """Jalankan satu kueri, cicipi mirror berurutan sampai ada yang menjawab."""
    galat_terakhir: Exception | None = None
    for url in _ENDPOINT:
        try:
            respons = httpx.post(url, content=kueri, headers=_HEADER, timeout=45.0)
            respons.raise_for_status()
            return respons.json().get("elements", [])
        except (httpx.HTTPError, ValueError) as galat:
            logger.warning("Overpass %s gagal: %s", url.split("/")[2], type(galat).__name__)
            galat_terakhir = galat
    raise OsmUnavailable(
        "upstream_error",
        type(galat_terakhir).__name__ if galat_terakhir else "tanpa jawaban",
    )


def ambil_geografi(lat: float, lon: float) -> dict[str, Any]:
    """Sumber air & akses terdekat dari OSM, dicari berjenjang sampai ketemu."""
    kunci = (round(lat, 3), round(lon, 3))
    tersimpan = _cache.get(kunci)
    if tersimpan and (time.monotonic() - tersimpan[0]) < _TTL_DETIK:
        return {**tersimpan[1], "dari_cache": True}

    for radius_km in _JENJANG_KM:
        # Kegagalan seluruh mirror melempar keluar dari fungsi ini — beda dari
        # "radius ini tidak menemukan apa-apa", yang justru wajar dan ditangani
        # dengan naik jenjang.
        elemen = _panggil(_kueri(lat, lon, radius_km * 1000))
        air, jalan = _kumpulkan(lat, lon, elemen)
        # Naik jenjang hanya kalau SALAH SATU kategori masih kosong — sekali
        # keduanya terisi, yang ditemukan sudah pasti yang terdekat.
        if (air and jalan) or radius_km == _JENJANG_KM[-1]:
            hasil = {
                "sumber": "OpenStreetMap",
                "sumber_url": "https://www.openstreetmap.org/copyright",
                "radius_km": radius_km,
                "air": air[:6],
                "akses": jalan[:6],
            }
            _cache[kunci] = (time.monotonic(), hasil)
            return {**hasil, "dari_cache": False}

    # Jenjang terakhir selalu mengembalikan hasil (walau daftarnya kosong), jadi
    # baris ini hanya terjangkau kalau `_JENJANG_KM` dikosongkan.
    raise OsmUnavailable("konfigurasi", "_JENJANG_KM kosong")
