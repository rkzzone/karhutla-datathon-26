"""Tempatkan alert pada posisi yang DITURUNKAN dari rantai alur, bukan sembarang.

=============================================================================
 MASALAH YANG DIPERBAIKI
=============================================================================
Sebelumnya alert ditempatkan dengan sebaran jarak/arah sembarang dari posko,
sementara sapuan drone direncanakan terpisah di atas hotspot FIRMS. Dua proses
yang tidak pernah saling bicara — hasilnya alert berjarak **2,8 sampai 17,6 km**
dari singgah drone terdekat.

Di peta itu terbaca mustahil: drone terbang ke satu tempat, tetapi apinya
ditemukan di tempat lain yang tak pernah dilewati siapa pun. Ditangkap anggota
tim hanya dengan melihat peta, dan ia benar.

=============================================================================
 ATURAN PENEMPATAN — `source_trigger` MENENTUKAN LOKASI
=============================================================================
Field `source_trigger` sudah ada di kontrak sejak awal, tetapi selama ini hanya
label tanpa konsekuensi geografis. Sekarang ia yang menentukan tempat, dan
rantainya jadi bisa dibaca dari peta tanpa penjelasan:

  satellite_firms  → TEPAT di singgah sapuan drone.
                     Satelit curiga → drone terbang ke sana → memotret →
                     model mengklasifikasi. Alertnya lahir di titik itu.

  iot_ground       → dekat node sensor darat yang memicunya.
                     Sensor melaporkan anomali → titik itu diverifikasi.

  patrol_scheduled → di sepanjang JALUR sapuan, di antara singgah.
                     Ditemukan tak sengaja saat melintas, bukan karena ada
                     yang mencurigainya lebih dulu.

Yang TIDAK berubah: prediksi, keandalan modalitas, lokalisasi, dan pasangan
citra. Semuanya tetap keluaran model sungguhan atas bingkai FLAME 2 yang sama.
Koordinat tetap penempatan simulasi — yang berubah adalah penempatan itu kini
KONSISTEN dengan rantai alurnya, bukan bahwa ia jadi nyata.

=============================================================================
 URUTAN JALAN — SKRIP INI PALING BELAKANG
=============================================================================
    python backend/scripts/pusatkan_wilayah.py     # posko + node sensor
    python backend/scripts/rencanakan_sapuan.py    # sapuan atas hotspot FIRMS
    python backend/scripts/tempatkan_alert.py      # BERKAS INI
    python backend/scripts/rutekan_patroli.py      # pengerahan regu darat
    python backend/scripts/bekukan_sizeup.py       # koordinat berubah → beku ulang

Skrip ini butuh sapuan yang SUDAH direncanakan. Menjalankannya lebih dulu akan
gagal dengan pesan yang menjelaskan urutannya.
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
ALERT_BACKEND = AKAR / "backend/app/mock_data/sample_predictions.json"
ALERT_FRONTEND = AKAR / "frontend/public/mock/sample_predictions.json"
SAPUAN = AKAR / "frontend/public/mock/sapuan_drone.json"
IOT = AKAR / "frontend/public/mock/iot_nodes.json"

# Geseran kecil dari titik acuan, supaya marker alert tidak menimpa persis
# marker singgah/sensor di bawahnya dan keduanya tetap bisa diklik. Kecil saja
# — 120 meter tidak mengubah desa, penutup lahan, maupun sumber air terdekat.
GESER_METER = 120.0


def geser(lat: float, lon: float, meter: float, bearing_deg: float) -> tuple[float, float]:
    R = 6371008.8
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    d = meter / R
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(
        math.sin(b) * math.sin(d) * math.cos(p1),
        math.cos(d) - math.sin(p1) * math.sin(p2),
    )
    return round(math.degrees(p2), 4), round(math.degrees(l2), 4)


def titik_pada_jalur(jalur: list[list[float]], pecahan: float) -> tuple[float, float]:
    """Titik pada `pecahan` (0..1) sepanjang jalur, diukur per ruas.

    Dipakai untuk alert `patrol_scheduled`: ia ditemukan SAAT MELINTAS, jadi
    tempatnya di antara singgah — bukan di singgah, yang justru menandakan
    kunjungan yang direncanakan.
    """
    if len(jalur) < 2:
        return tuple(jalur[0])
    indeks = max(0, min(len(jalur) - 2, int(pecahan * (len(jalur) - 1))))
    a, b = jalur[indeks], jalur[indeks + 1]
    t = (pecahan * (len(jalur) - 1)) - indeks
    return round(a[0] + (b[0] - a[0]) * t, 4), round(a[1] + (b[1] - a[1]) * t, 4)


def main() -> None:
    if not SAPUAN.exists():
        raise SystemExit(
            "sapuan_drone.json belum ada. Jalankan rencanakan_sapuan.py lebih dulu — "
            "posisi alert diturunkan DARI sapuan, jadi urutannya tidak bisa dibalik."
        )

    with SAPUAN.open(encoding="utf-8") as berkas:
        sapuan = json.load(berkas)
    with IOT.open(encoding="utf-8") as berkas:
        node = json.load(berkas).get("node", [])
    with ALERT_BACKEND.open(encoding="utf-8") as berkas:
        alerts = json.load(berkas)

    singgah = sapuan.get("urutan", [])
    jalur = sapuan.get("jalur", [])
    # Hotspot yang TIDAK muat di penerbangan ini tetap hotspot sungguhan.
    # Dipakai sebagai limpahan untuk alert `satellite_firms` ketika singgah
    # habis: alert menumpuk lintas sortie, jadi sebagian memang berasal dari
    # penerbangan sebelumnya ke titik yang hari ini tak terjangkau. Yang tidak
    # boleh adalah menaruh alert satelit di tempat yang bukan hotspot sama
    # sekali — itu memutus rantai yang justru ingin ditunjukkan.
    luar = sorted(
        sapuan.get("di_luar_jangkauan", []),
        key=lambda t: t.get("jarak_pangkalan_km", 9e9),
    )
    if not singgah:
        raise SystemExit("Sapuan tidak punya satu pun singgah — tidak ada tempat menaruh alert.")

    pakai_singgah = 0
    pakai_luar = 0
    pakai_node = 0
    pakai_jalur = 0
    ringkasan = []

    for alert in alerts:
        pemicu = alert["source_trigger"]

        if pemicu == "satellite_firms" and pakai_singgah < len(singgah):
            t = singgah[pakai_singgah]
            lat, lon = geser(t["lat"], t["lon"], GESER_METER, 45 + pakai_singgah * 37)
            asal = f"singgah #{pakai_singgah + 1} (FRP {t['frp_mw']} MW)"
            pakai_singgah += 1

        elif pemicu == "satellite_firms" and pakai_luar < len(luar):
            t = luar[pakai_luar]
            lat, lon = geser(t["lat"], t["lon"], GESER_METER, 90 + pakai_luar * 43)
            asal = (
                f"hotspot di luar sortie ini, {t['jarak_pangkalan_km']} km "
                f"(FRP {t['frp_mw']} MW) — diverifikasi penerbangan sebelumnya"
            )
            pakai_luar += 1

        elif pemicu == "iot_ground" and pakai_node < len(node):
            n = node[pakai_node]
            lat, lon = geser(n["lat"], n["lon"], GESER_METER * 3, 200 + pakai_node * 51)
            asal = f"sensor {n['node_id']}"
            pakai_node += 1

        else:
            # patrol_scheduled, dan juga cadangan kalau singgah/sensor habis.
            # Pecahan dipilih menyebar supaya ketiganya tidak menumpuk di satu
            # ruas jalur yang sama.
            pecahan = 0.18 + 0.28 * pakai_jalur
            lat, lon = titik_pada_jalur(jalur, min(pecahan, 0.92))
            asal = f"jalur sapuan, {round(min(pecahan, 0.92) * 100)}% lintasan"
            pakai_jalur += 1

        alert["location"] = {"lat": lat, "lon": lon}
        ringkasan.append((alert["alert_id"][:8], pemicu, lat, lon, asal))

    for aid, pemicu, lat, lon, asal in ringkasan:
        print(f"  {aid}  {pemicu:<17} {lat:8.4f}, {lon:9.4f}   ← {asal}")

    for tujuan in (ALERT_BACKEND, ALERT_FRONTEND):
        with tujuan.open("w", encoding="utf-8") as berkas:
            json.dump(alerts, berkas, ensure_ascii=False, indent=2)
        print(f"\nDitulis: {tujuan.relative_to(AKAR)}")

    print(
        f"\n{pakai_singgah} alert di singgah drone · {pakai_node} di sensor darat · "
        f"{pakai_jalur} di jalur sapuan"
    )
    print("\nKoordinat berubah — turunannya ikut basi:")
    print("    python backend/scripts/rutekan_patroli.py")
    print("    python backend/scripts/bekukan_sizeup.py")


if __name__ == "__main__":
    main()
