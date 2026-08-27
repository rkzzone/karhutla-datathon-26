"""Simulator sensor darat (Stage 12).

Ini SIMULASI, bukan sensor nyata. Setiap objek yang keluar dari modul ini
membawa `simulasi: true` dan router menambahkan header `X-Data-Simulated: true`,
supaya tidak ada jalur di mana UI bisa keliru menampilkannya sebagai data
lapangan.

Model deret waktu sengaja deterministik terhadap waktu (bukan acak murni) agar
demo bisa diulang dan hasilnya sama di tiap take rekaman.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

WIB = timezone(timedelta(hours=7))

# Node ditempatkan berdekatan dengan lokasi alert supaya korelasi
# "sensor darat naik → alert muncul" terbaca di peta saat demo.
_NODE = [
    {"node_id": "IOT-KTG-01", "nama": "Kanal Blok C, Pulang Pisau", "lat": -2.7101, "lon": 114.2310, "fase": 0.0},
    {"node_id": "IOT-KTG-02", "nama": "Sekat Bakar 4, Pulang Pisau", "lat": -2.6355, "lon": 114.1002, "fase": 1.1},
    {"node_id": "IOT-OKI-01", "nama": "Menara Pantau OKI", "lat": -3.3760, "lon": 105.4510, "fase": 2.3},
    {"node_id": "IOT-JBI-01", "nama": "Gambut Muaro Jambi", "lat": -1.5540, "lon": 103.5960, "fase": 3.4},
    {"node_id": "IOT-RIA-01", "nama": "Konsesi Siak Blok 2", "lat": 0.8180, "lon": 101.9210, "fase": 4.6},
    {"node_id": "IOT-KBR-01", "nama": "Kubu Raya Selatan", "lat": -0.2860, "lon": 109.4260, "fase": 5.2},
]

_AMBANG = {
    "suhu_c": 41.0,
    "kelembapan_persen": 30.0,
    "pm25_ugm3": 55.0,
    "kelembapan_gambut_persen": 35.0,
}


def _gelombang(fase: float, detik: float, periode: float) -> float:
    """Nilai -1..1, deterministik terhadap jam dinding."""
    return math.sin((detik / periode) * 2 * math.pi + fase)


def _status(bacaan: dict[str, float]) -> str:
    pelanggaran = sum(
        [
            bacaan["suhu_c"] > _AMBANG["suhu_c"],
            bacaan["kelembapan_persen"] < _AMBANG["kelembapan_persen"],
            bacaan["pm25_ugm3"] > _AMBANG["pm25_ugm3"],
            bacaan["kelembapan_gambut_persen"] < _AMBANG["kelembapan_gambut_persen"],
        ]
    )
    if pelanggaran >= 3:
        return "kritis"
    if pelanggaran >= 1:
        return "waspada"
    return "normal"


def _baca(node: dict[str, Any], saat: datetime) -> dict[str, Any]:
    detik = saat.timestamp()
    fase = node["fase"]
    ayun_lambat = _gelombang(fase, detik, periode=600.0)
    ayun_cepat = _gelombang(fase * 1.7, detik, periode=90.0)

    suhu = 34.0 + 8.0 * ayun_lambat + 1.2 * ayun_cepat
    kelembapan = 52.0 - 24.0 * ayun_lambat + 3.0 * ayun_cepat
    pm25 = 34.0 + 32.0 * max(ayun_lambat, 0.0) + 6.0 * ayun_cepat
    gambut = 48.0 - 20.0 * ayun_lambat

    bacaan = {
        "suhu_c": round(suhu, 1),
        "kelembapan_persen": round(max(kelembapan, 5.0), 1),
        "pm25_ugm3": round(max(pm25, 4.0), 1),
        "kelembapan_gambut_persen": round(max(gambut, 8.0), 1),
    }
    return {
        "node_id": node["node_id"],
        "nama": node["nama"],
        "lat": node["lat"],
        "lon": node["lon"],
        "waktu": saat.astimezone(WIB).isoformat(timespec="seconds"),
        "bacaan": bacaan,
        "ambang": _AMBANG,
        "status": _status(bacaan),
        "baterai_persen": round(72.0 + 22.0 * _gelombang(fase, detik, 3600.0), 0),
        "simulasi": True,
    }


def ambil_node(saat: datetime | None = None) -> dict[str, Any]:
    saat = saat or datetime.now(tz=WIB)
    node = [_baca(n, saat) for n in _NODE]
    return {
        "simulasi": True,
        "catatan": "Data sensor disimulasikan untuk demo — bukan bacaan lapangan.",
        "waktu_server": saat.astimezone(WIB).isoformat(timespec="seconds"),
        "jumlah": len(node),
        "node": node,
    }


def ambil_riwayat(node_id: str, menit: int = 60, langkah: int = 5) -> dict[str, Any]:
    """Deret waktu mundur `menit` terakhir untuk sparkline di Halaman 1."""
    sumber = next((n for n in _NODE if n["node_id"] == node_id), None)
    if sumber is None:
        return {}
    sekarang = datetime.now(tz=WIB)
    titik = [
        _baca(sumber, sekarang - timedelta(minutes=selang))
        for selang in range(menit, -1, -langkah)
    ]
    return {
        "simulasi": True,
        "node_id": node_id,
        "nama": sumber["nama"],
        "rentang_menit": menit,
        "titik": titik,
    }
