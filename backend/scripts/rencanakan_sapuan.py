"""Rencanakan sapuan verifikasi drone di bawah kendala baterai.

=============================================================================
 MASALAH YANG DIPECAHKAN
=============================================================================
FIRMS memberi N titik CURIGA dalam satu wilayah operasi. Drone tidak bisa
mendatangi semuanya: baterainya habis ~30 menit, dan ia harus kembali ke
pangkalan. Jadi pertanyaannya bukan "terbang ke mana", melainkan:

    Titik mana yang diverifikasi, dengan urutan apa, supaya sebanyak mungkin
    terverifikasi dan drone tetap pulang sebelum baterai habis?

Ini **Orienteering Problem** — TSP berhadiah dengan anggaran perjalanan. Ia
punya nama, punya literatur, dan yang terpenting: ia **aturan deterministik**,
bukan keluaran model. Setiap keputusannya bisa dijelaskan di layar, sama
seperti lapisan size-up. Tidak ada yang perlu dipercaya begitu saja.

=============================================================================
 KENAPA GARIS LURUS, BUKAN MENGIKUTI JALAN
=============================================================================
Sempat keliru dikerjakan sebelumnya: jalur patroli dirutekan lewat jalan pakai
OSRM. Itu benar untuk REGU DARAT dan salah untuk DRONE — drone terbang, jalan
tidak relevan baginya.

Keduanya tetap ada di produk, sebagai dua hal berbeda:
  · sapuan drone  → garis lurus, dibatasi baterai       (berkas ini)
  · pengerahan regu → mengikuti jalan, dari posko ke api (rutekan_patroli.py)

=============================================================================
 ANGKA YANG DIPAKAI — DAN DARI MANA ASALNYA
=============================================================================
Ketiganya ditampilkan di layar supaya bisa diperiksa, bukan disembunyikan.

  Daya tahan 30 menit  → keterangan Dr. Supriyanto dalam wawancara narasumber
                         ("≈ 30 menit, lebih singkat bila mengirim data").
  Laju jelajah 15 m/s  → angka wajar untuk drone kelas Mavic 3T. TIDAK diukur
                         tim ini. Disebut sebagai asumsi, bukan pengukuran.
  Hover 60 detik/titik → waktu menangkap pasangan RGB+termal yang layak.
                         Juga asumsi, juga disebut begitu.

Marjin cadangan 20% disisihkan dari anggaran: rencana yang memakai baterai
sampai tetes terakhir bukan rencana, itu taruhan.

Jalankan (setelah `pusatkan_wilayah.py`):
    python backend/scripts/rencanakan_sapuan.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

for aliran in (sys.stdout, sys.stderr):
    if hasattr(aliran, "reconfigure"):
        aliran.reconfigure(encoding="utf-8", errors="replace")

AKAR = Path(__file__).resolve().parents[2]
FIRMS = AKAR / "frontend/public/mock/firms_snapshot.json"
WILAYAH = AKAR / "frontend/public/mock/wilayah_operasi.json"
TUJUAN = AKAR / "frontend/public/mock/sapuan_drone.json"

DAYA_TAHAN_MENIT = 30.0
LAJU_MPS = 15.0
HOVER_DETIK = 60.0
MARJIN_CADANGAN = 0.20

# Hotspot di luar radius ini tidak ikut dipertimbangkan sama sekali. Bukan
# penyaringan kosmetik: dengan anggaran 24 menit, titik 40 km jauhnya mustahil
# masuk, dan membiarkannya jadi kandidat hanya memperlambat perencana tanpa
# pernah mengubah hasilnya.
RADIUS_KANDIDAT_KM = 25.0


def jarak_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    R = 6371.0088
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def menit_jalur(urutan: list[dict], pangkalan: tuple[float, float]) -> float:
    """Total menit satu sapuan: terbang + hover, pangkalan → titik → pangkalan."""
    if not urutan:
        return 0.0
    titik = [pangkalan] + [(t["lat"], t["lon"]) for t in urutan] + [pangkalan]
    km = sum(jarak_km(titik[i], titik[i + 1]) for i in range(len(titik) - 1))
    menit_terbang = (km * 1000.0 / LAJU_MPS) / 60.0
    return menit_terbang + len(urutan) * (HOVER_DETIK / 60.0)


def _dua_opt(urutan: list[dict], pangkalan: tuple[float, float]) -> list[dict]:
    """Perbaikan 2-opt: buang jalur yang menyilang dirinya sendiri.

    Serakah saja sering menghasilkan urutan yang bolak-balik melewati
    pangkalan. 2-opt murah (n kecil — paling banyak belasan titik) dan hasilnya
    langsung terlihat lebih masuk akal di peta, yang penting karena operator
    HARUS bisa menilai sendiri apakah rencananya waras.
    """
    terbaik = urutan[:]
    membaik = True
    while membaik:
        membaik = False
        for i in range(len(terbaik) - 1):
            for j in range(i + 1, len(terbaik)):
                calon = terbaik[:i] + terbaik[i : j + 1][::-1] + terbaik[j + 1 :]
                if menit_jalur(calon, pangkalan) + 1e-9 < menit_jalur(terbaik, pangkalan):
                    terbaik, membaik = calon, True
    return terbaik


def rencanakan(kandidat: list[dict], pangkalan: tuple[float, float], anggaran: float):
    """Sisipan serakah + 2-opt.

    Serakah dipilih bukan karena optimal — ia tidak — melainkan karena tiap
    langkahnya bisa DIJELASKAN: pada tiap putaran, titik yang dipilih adalah
    yang menambah waktu paling sedikit per satuan prioritas. Operator yang
    bertanya "kenapa titik ini dilewati" punya jawaban, dan itu lebih berharga
    daripada beberapa persen efisiensi dari solver yang tak bisa ditanyai.
    """
    terpilih: list[dict] = []
    tersisa = sorted(kandidat, key=lambda t: -t["prioritas"])

    while True:
        calon_terbaik = None
        for t in tersisa:
            for posisi in range(len(terpilih) + 1):
                calon = terpilih[:posisi] + [t] + terpilih[posisi:]
                menit = menit_jalur(calon, pangkalan)
                if menit > anggaran:
                    continue
                tambahan = menit - menit_jalur(terpilih, pangkalan)
                skor = tambahan / max(t["prioritas"], 1e-6)
                if calon_terbaik is None or skor < calon_terbaik[0]:
                    calon_terbaik = (skor, calon, t)
        if calon_terbaik is None:
            break
        _, terpilih, dipakai = calon_terbaik
        tersisa.remove(dipakai)

    if len(terpilih) > 2:
        terpilih = _dua_opt(terpilih, pangkalan)
    return terpilih, tersisa


def main() -> None:
    with WILAYAH.open(encoding="utf-8") as berkas:
        wilayah = json.load(berkas)
    with FIRMS.open(encoding="utf-8") as berkas:
        hotspot = json.load(berkas).get("titik", [])

    posko = wilayah["posko"]
    pangkalan = (posko["lat"], posko["lon"])
    anggaran = DAYA_TAHAN_MENIT * (1.0 - MARJIN_CADANGAN)

    # KANDIDAT ADALAH HOTSPOT FIRMS, BUKAN ALERT — dan itu koreksi konseptual,
    # bukan detail teknis.
    #
    # Percobaan pertama memakai daftar alert sebagai kandidat. Itu terbalik:
    # alert ADALAH hasil verifikasi, jadi merencanakan penerbangan untuk
    # memverifikasinya berarti terbang ke tempat yang sudah diketahui isinya.
    # Yang belum diverifikasi — dan karena itu yang layak didatangi — adalah
    # hotspot satelit.
    #
    # Prioritas memakai FRP (Fire Radiative Power), daya pancar radiatif yang
    # diukur satelit dalam megawatt. Ia bervariasi lebar di data nyata
    # (15-36 MW pada klaster ini), berbeda dari keyakinan model yang softmax-nya
    # jenuh di 1,0 untuk sembilan dari sepuluh bingkai — dicatat di CHANGELOG
    # 2026-08-08. Prioritas yang seragam tidak memilih apa pun.
    kandidat = []
    for i, h in enumerate(hotspot):
        if not isinstance(h.get("lat"), (int, float)) or not isinstance(h.get("lon"), (int, float)):
            continue
        d = jarak_km(pangkalan, (h["lat"], h["lon"]))
        if d > RADIUS_KANDIDAT_KM:
            continue
        kandidat.append(
            {
                "id": f"FIRMS-{i:04d}",
                "lat": h["lat"],
                "lon": h["lon"],
                "frp_mw": h.get("frp_mw"),
                "kecerahan_k": h.get("kecerahan_k"),
                "waktu_akuisisi": h.get("waktu_akuisisi"),
                "prioritas": round(float(h.get("frp_mw") or 0.0), 2),
                "jarak_pangkalan_km": round(d, 2),
            }
        )
    if not kandidat:
        raise SystemExit(
            f"Tidak ada hotspot FIRMS dalam {RADIUS_KANDIDAT_KM} km dari pangkalan. "
            "Wilayah operasi tanpa kebakaran di dalamnya tidak bisa "
            "mendemonstrasikan verifikasi — pindahkan posko, atau perbarui cuplikan FIRMS."
        )

    terpilih, terlewat = rencanakan(kandidat, pangkalan, anggaran)
    menit = menit_jalur(terpilih, pangkalan)
    titik = [pangkalan] + [(t["lat"], t["lon"]) for t in terpilih] + [pangkalan]
    km = sum(jarak_km(titik[i], titik[i + 1]) for i in range(len(titik) - 1))

    print(f"Pangkalan   : {posko['nama']} ({pangkalan[0]}, {pangkalan[1]})")
    print(f"Anggaran    : {anggaran:.0f} menit ({DAYA_TAHAN_MENIT:.0f} menit − cadangan {MARJIN_CADANGAN:.0%})")
    print(f"Kandidat    : {len(kandidat)} titik\n")
    print(f"Terpilih    : {len(terpilih)} titik · {km:.1f} km · {menit:.1f} menit")
    for i, t in enumerate(terpilih, 1):
        print(f"   {i}. {t['id']}  {t['jarak_pangkalan_km']:5.1f} km  FRP {t['frp_mw']} MW")
    print(f"\nDi luar jangkauan penerbangan ini: {len(terlewat)} titik")
    for t in sorted(terlewat, key=lambda x: -float(x["frp_mw"] or 0))[:6]:
        print(f"   · {t['id']}  {t['jarak_pangkalan_km']:5.1f} km  FRP {t['frp_mw']} MW")

    with TUJUAN.open("w", encoding="utf-8") as berkas:
        json.dump(
            {
                "catatan": (
                    "Rencana sapuan verifikasi drone, dihitung aturan deterministik "
                    "(Orienteering Problem: sisipan serakah + 2-opt) — bukan keluaran "
                    "model. Jalur berupa garis lurus karena drone terbang; jalan tidak "
                    "relevan baginya. Titik di luar daftar bukan berarti aman, hanya "
                    "belum terjangkau penerbangan ini."
                ),
                "pangkalan": posko,
                "asumsi": {
                    "daya_tahan_menit": DAYA_TAHAN_MENIT,
                    "laju_mps": LAJU_MPS,
                    "hover_detik_per_titik": HOVER_DETIK,
                    "marjin_cadangan": MARJIN_CADANGAN,
                    "sumber_daya_tahan": "keterangan Dr. Supriyanto, 7 Agustus 2026",
                    "sumber_laju_dan_hover": "asumsi tim ini, TIDAK diukur",
                },
                "anggaran_menit": round(anggaran, 1),
                "jarak_km": round(km, 1),
                "durasi_menit": round(menit, 1),
                "urutan": terpilih,
                "di_luar_jangkauan": sorted(terlewat, key=lambda x: x["jarak_pangkalan_km"]),
                "jalur": [[lat, lon] for lat, lon in titik],
            },
            berkas,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nDitulis: {TUJUAN.relative_to(AKAR)}")


if __name__ == "__main__":
    main()
