"""Sistem Fire Weather Index (FWI) Kanada — sumber D3.

Implementasi persamaan van Wagner (1987), *Development and Structure of the
Canadian Forest Fire Weather Index System*, Forestry Technical Report 35.
Sistem inilah yang diadopsi BMKG sebagai Sistem Peringkat Bahaya Kebakaran
(SPBK / FDRS).

KENAPA DIHITUNG SENDIRI, BUKAN DITARIK DARI BMKG. Portal SPBK BMKG (SPARTAN)
adalah aplikasi ber-login tanpa API publik; men-scrape portal pemerintah yang
diproteksi bukan pilihan yang pantas maupun andal. Menghitung sendiri dari
persamaan terbit justru lebih baik untuk paper: seluruhnya reproducible, tidak
bergantung pada layanan yang bisa berubah, dan tiap komponen antaranya bisa
diperiksa.

YANG BOLEH DIKATAKAN: "kami menghitung FWI, sistem yang sama yang diadopsi SPBK
BMKG". YANG TIDAK BOLEH: "ini angka SPBK BMKG" — angka kami bukan keluaran
BMKG, dan masukannya pun bukan pengamatan stasiun BMKG melainkan reanalisis
Open-Meteo.

=============================================================================
 TIGA KETERBATASAN YANG WAJIB IKUT DITAMPILKAN, BUKAN DISIMPAN DI KODE
=============================================================================
1. **Faktor panjang hari.** Tabel Le (DMC) dan Lf (DC) asli van Wagner disusun
   untuk lintang 46°N dan tidak berlaku di khatulistiwa. Dipakai penyesuaian
   ekuatorial Le = 9.0 dan Lf = 1.4 sepanjang tahun, mengikuti praktik yang
   dipakai implementasi FDRS wilayah ekuatorial. Ini penyesuaian yang diakui,
   bukan karangan — tetapi tetap sebuah penyesuaian.

2. **Spin-up, bukan kesinambungan sejak awal musim.** FFMC/DMC/DC adalah kode
   yang membawa memori: nilai hari ini bergantung pada nilai kemarin. Sistem
   operasional menjalankannya menerus sejak awal musim. Kami memulai dari nilai
   awal standar (FFMC 85, DMC 6, DC 15) lalu menjalankannya maju selama
   `HARI_SPINUP` hari. FFMC (memori beberapa hari) dan DMC (~15 hari) sudah
   konvergen. **DC bermemori ~50 hari, jadi ia yang paling terpengaruh pilihan
   nilai awal** — dan DC ikut menentukan BUI dan FWI akhir. Karena itu jumlah
   hari spin-up dilaporkan bersama hasilnya.

3. **Masukan reanalisis, bukan stasiun.** Nilai tengah hari diambil dari
   Open-Meteo, bukan dari pengamatan stasiun BMKG.
=============================================================================
"""

from __future__ import annotations

import math
from typing import Any

# Nilai awal standar musim (van Wagner 1987). Lihat keterbatasan nomor 2.
FFMC_AWAL = 85.0
DMC_AWAL = 6.0
DC_AWAL = 15.0

# Panjang spin-up. 60 hari sudah lebih dari cukup untuk FFMC dan DMC; untuk DC
# ia masih di bawah memori penuhnya (~50 hari baru sebagian teredam), dan itu
# disebutkan apa adanya di UI alih-alih dibulatkan jadi "sudah konvergen".
HARI_SPINUP = 60

# Penyesuaian ekuatorial — lihat keterbatasan nomor 1.
LE_EKUATOR = 9.0
LF_EKUATOR = 1.4

# Kelas bahaya FWI yang dipakai FDRS wilayah ekuatorial (ASEAN/Indonesia).
# Ambangnya SENGAJA ditampilkan di layar: kami tidak memverifikasi sendiri
# ambang persis yang dipakai BMKG, jadi angkanya yang jadi pegangan, bukan
# namanya. Urutan menurun — cocok pertama menang.
KELAS_FWI = (
    (26.0, 4, "Ekstrem", "FWI ≥ 26"),
    (13.0, 4, "Sangat tinggi", "FWI 13–26"),
    (6.0, 3, "Tinggi", "FWI 6–13"),
    (1.0, 2, "Sedang", "FWI 1–6"),
    (0.0, 1, "Rendah", "FWI < 1"),
)


def _ffmc(t: float, h: float, w: float, ro: float, ffmc_kemarin: float) -> float:
    """Fine Fuel Moisture Code — kadar air bahan bakar halus permukaan."""
    h = min(h, 100.0)
    mo = 147.2 * (101.0 - ffmc_kemarin) / (59.5 + ffmc_kemarin)

    if ro > 0.5:
        rf = ro - 0.5
        mo += 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf))
        if mo > 150.0:
            mo += 0.0015 * (mo - 150.0) ** 2 * math.sqrt(rf)
        mo = min(mo, 250.0)

    ed = (
        0.942 * h**0.679
        + 11.0 * math.exp((h - 100.0) / 10.0)
        + 0.18 * (21.1 - t) * (1.0 - math.exp(-0.115 * h))
    )
    if mo > ed:
        ko = 0.424 * (1.0 - (h / 100.0) ** 1.7) + 0.0694 * math.sqrt(w) * (
            1.0 - (h / 100.0) ** 8
        )
        kd = ko * 0.581 * math.exp(0.0365 * t)
        m = ed + (mo - ed) * 10.0**-kd
    else:
        ew = (
            0.618 * h**0.753
            + 10.0 * math.exp((h - 100.0) / 10.0)
            + 0.18 * (21.1 - t) * (1.0 - math.exp(-0.115 * h))
        )
        if mo < ew:
            kl = 0.424 * (1.0 - ((100.0 - h) / 100.0) ** 1.7) + 0.0694 * math.sqrt(w) * (
                1.0 - ((100.0 - h) / 100.0) ** 8
            )
            kw = kl * 0.581 * math.exp(0.0365 * t)
            m = ew - (ew - mo) * 10.0**-kw
        else:
            m = mo

    return min(max(59.5 * (250.0 - m) / (147.2 + m), 0.0), 101.0)


def _dmc(t: float, h: float, ro: float, dmc_kemarin: float, le: float) -> float:
    """Duff Moisture Code — kadar air lapisan serasah agak dalam."""
    t = max(t, -1.1)
    p = dmc_kemarin

    if ro > 1.5:
        re = 0.92 * ro - 1.27
        mo = 20.0 + math.exp(5.6348 - p / 43.43)
        if p <= 33.0:
            b = 100.0 / (0.5 + 0.3 * p)
        elif p <= 65.0:
            b = 14.0 - 1.3 * math.log(p)
        else:
            b = 6.2 * math.log(p) - 17.2
        mr = mo + 1000.0 * re / (48.77 + b * re)
        p = max(244.72 - 43.43 * math.log(mr - 20.0), 0.0)

    k = 1.894 * (t + 1.1) * (100.0 - h) * le * 1e-6
    return max(p + 100.0 * k, 0.0)


def _dc(t: float, ro: float, dc_kemarin: float, lf: float) -> float:
    """Drought Code — indeks kekeringan lapisan dalam. Ini yang paling relevan
    untuk gambut, dan sekaligus yang paling terpengaruh panjang spin-up."""
    t = max(t, -2.8)
    d = dc_kemarin

    if ro > 2.8:
        rd = 0.83 * ro - 1.27
        qo = 800.0 * math.exp(-d / 400.0)
        qr = qo + 3.937 * rd
        d = max(400.0 * math.log(800.0 / qr), 0.0)

    v = max(0.36 * (t + 2.8) + lf, 0.0)
    return max(d + 0.5 * v, 0.0)


def _isi(w: float, ffmc: float) -> float:
    """Initial Spread Index — laju penyebaran awal."""
    m = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    f_w = math.exp(0.05039 * w)
    f_f = 91.9 * math.exp(-0.1386 * m) * (1.0 + m**5.31 / 4.93e7)
    return 0.208 * f_w * f_f


def _bui(dmc: float, dc: float) -> float:
    """Buildup Index — total bahan bakar tersedia."""
    if dmc <= 0.0:
        return 0.0
    if dmc <= 0.4 * dc:
        u = 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        u = dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)
    return max(u, 0.0)


def _fwi(isi: float, bui: float) -> float:
    """Fire Weather Index — intensitas & kesulitan pengendalian."""
    if bui <= 80.0:
        f_d = 0.626 * bui**0.809 + 2.0
    else:
        f_d = 1000.0 / (25.0 + 108.64 * math.exp(-0.023 * bui))
    b = 0.1 * isi * f_d
    if b > 1.0:
        return math.exp(2.72 * (0.434 * math.log(b)) ** 0.647)
    return b


def kelas(nilai: float) -> tuple[int, str, str]:
    """FWI → (tingkat 1-4, nama, ambang yang dipakai). Ambang ikut dikembalikan
    supaya UI bisa menampilkannya dan pembacanya bisa memeriksa sendiri."""
    for batas, tingkat, nama, ambang in KELAS_FWI:
        if nilai >= batas:
            return tingkat, nama, ambang
    return 1, "Rendah", "FWI < 1"


def hitung_deret(harian: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Jalankan sistem FWI maju atas deret harian nilai tengah hari.

    `harian` harus terurut menaik, tiap item: tanggal, suhu_c, kelembapan_persen,
    angin_kmj, hujan_24jam_mm. Nilai yang dikembalikan adalah hari TERAKHIR,
    beserta seluruh komponen antaranya supaya bisa diaudit di layar.
    """
    bersih = [
        d
        for d in harian
        if all(
            isinstance(d.get(k), (int, float))
            for k in ("suhu_c", "kelembapan_persen", "angin_kmj", "hujan_24jam_mm")
        )
    ]
    if not bersih:
        return None

    ffmc, dmc, dc = FFMC_AWAL, DMC_AWAL, DC_AWAL
    for hari in bersih:
        t = float(hari["suhu_c"])
        h = float(hari["kelembapan_persen"])
        w = float(hari["angin_kmj"])
        ro = float(hari["hujan_24jam_mm"])
        ffmc = _ffmc(t, h, w, ro, ffmc)
        dmc = _dmc(t, h, ro, dmc, LE_EKUATOR)
        dc = _dc(t, ro, dc, LF_EKUATOR)

    isi = _isi(float(bersih[-1]["angin_kmj"]), ffmc)
    bui = _bui(dmc, dc)
    nilai = _fwi(isi, bui)
    tingkat, nama, ambang = kelas(nilai)

    return {
        "status": "ada",
        "sistem": "Fire Weather Index (FWI) — Sistem Kanada, van Wagner 1987",
        "fwi": round(nilai, 1),
        "tingkat": tingkat,
        "nama": nama,
        "ambang": ambang,
        "komponen": {
            "ffmc": round(ffmc, 1),
            "dmc": round(dmc, 1),
            "dc": round(dc, 1),
            "isi": round(isi, 1),
            "bui": round(bui, 1),
        },
        "hari_dipakai": len(bersih),
        "tanggal_akhir": bersih[-1].get("tanggal"),
        # Keterbatasan ikut dalam payload, bukan cuma di dokumentasi kode —
        # supaya UI tidak bisa menampilkan angkanya tanpa menampilkan batasnya.
        "penyesuaian_ekuator": {"Le": LE_EKUATOR, "Lf": LF_EKUATOR},
        "nilai_awal": {"ffmc": FFMC_AWAL, "dmc": DMC_AWAL, "dc": DC_AWAL},
        "catatan": (
            f"Dihitung tim ini dari persamaan terbit van Wagner (1987) atas "
            f"{len(bersih)} hari data tengah hari Open-Meteo, dengan penyesuaian "
            f"panjang hari ekuatorial (Le {LE_EKUATOR}, Lf {LF_EKUATOR}). Sistem "
            f"yang sama diadopsi SPBK BMKG, tetapi angka ini BUKAN keluaran BMKG "
            f"dan masukannya bukan pengamatan stasiun BMKG."
        ),
        "catatan_spinup": (
            f"Kode kadar air dimulai dari nilai awal standar dan dijalankan maju "
            f"{len(bersih)} hari. FFMC dan DMC sudah konvergen; DC bermemori "
            f"sekitar 50 hari sehingga masih menyimpan sebagian pengaruh nilai "
            f"awal — dan DC ikut menentukan BUI serta FWI."
        ),
    }
