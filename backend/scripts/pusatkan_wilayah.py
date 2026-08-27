"""Pusatkan seluruh data demo ke SATU wilayah cakupan yang koheren.

=============================================================================
 MASALAH YANG DIPERBAIKI
=============================================================================
Sepuluh alert demo tersebar **1.366 km timur-barat dan 544 km utara-selatan**,
melintasi empat provinsi. Tidak ada satu posko pun yang mencakup itu, dan satu
drone berbaterai 30 menit jelas tidak. Sebarannya secara diam-diam merusak
cerita operasional yang justru ingin ditunjukkan produk ini: satu posko, satu
regu, satu pangkalan drone, beberapa titik curiga yang harus diverifikasi.

Anggota tim menangkapnya hanya dengan melihat peta.

=============================================================================
 APA YANG BERUBAH DAN APA YANG TIDAK
=============================================================================
Yang BERUBAH: hanya `location` pada tiap alert dan node sensor.

Yang TIDAK berubah: prediksi, keandalan modalitas, lokalisasi, dan pasangan
citra. Semuanya tetap keluaran model sungguhan atas bingkai FLAME 2 yang sama.

Ini BUKAN menambah kebohongan baru. Koordinat alert memang sudah berupa
penempatan simulasi sejak awal — UI menyatakannya di setiap halaman rincian,
dan alasannya tertulis di CHANGELOG 2026-08-08: model tidak menghasilkan
koordinat, dan belum ada pihak yang ditugasi memasoknya. Yang dilakukan skrip
ini adalah membuat penempatan simulasi itu **koheren**, bukan membuatnya
tampak nyata. Label "penempatan simulasi" tetap wajib dan tidak boleh dihapus.

=============================================================================
 KENAPA PALANGKA RAYA, KALIMANTAN TENGAH — DAN KENAPA 19 AGUSTUS
=============================================================================
Wilayah dan tanggal dipilih dari DATA, bukan dari selera. Tujuh tanggal
disurvei di sepanjang Agustus 2026, dan untuk tiap tanggal dicari klaster
terpadat dalam radius 10 km — radius itu bukan angka sembarang, melainkan
jangkauan realistis satu sortie drone berbaterai 30 menit.

    03 Agu  0 titik           11 Agu   74 dalam 10 km
    07 Agu  119 dalam 10 km   15 Agu   93
    19 Agu  192 dalam 10 km   23 Agu  115
    26 Agu  153 dalam 10 km

**19 Agustus menang telak: 192 titik dalam 10 km, 255 dalam 25 km.**

Pangkalan diletakkan di **Kelurahan Kereng Bangkirai, Kec. Sabangau, Kota
Palangka Raya** — pusat sub-klaster terpadat (89 titik dalam radius 4 km),
di tepi kawasan gambut Sabangau. Ketiga sumber luar terverifikasi bekerja di
titik ini: BIG mengembalikan kelurahan dan penutup lahan, BMKG punya prakiraan
untuk kelurahan itu.

Posisinya sengaja DI DALAM klaster, bukan di pinggirnya. Percobaan pertama
menaruh pangkalan 5,5 km dari titik terdekat, dan perencana sapuan hanya
memuat 3 dari 229 kandidat — drone jadi tampak tak berguna. Posko Manggala Agni
memang berdiri di kawasan rawan, bukan di kota; menaruhnya jauh dari api adalah
pemodelan yang salah, bukan sekadar demo yang kurang menarik.

MEMILIH TANGGAL DEMO ITU SAH, MENYEMBUNYIKANNYA TIDAK. Setiap demo memilih
kasus representatif, dan datanya tetap deteksi satelit sungguhan pada hari itu.
Yang tidak boleh adalah menyajikannya seolah hari biasa. UI menampilkan tanggal
cuplikan di kepala peta, dan itu tidak boleh dihapus.

Percobaan sebelumnya memakai Pulang Pisau (hotspot terdekat 64,8 km — wilayah
operasi tanpa kebakaran di dalamnya) lalu Kayong Utara pada data hari berjalan
(hanya 3 dari 35 kandidat muat, sehingga drone tampak tak berguna). Keduanya
ditinggalkan karena alasan yang sama: data harus mendukung cerita, bukan
melawannya.

Jalankan:
    python backend/scripts/pusatkan_wilayah.py --periksa    # cek titik di darat
    python backend/scripts/pusatkan_wilayah.py
Lalu bekukan ulang cuplikan size-up, karena seluruh koordinatnya berubah:
    python backend/scripts/bekukan_sizeup.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Konsol Windows default cp1252 dan akan MELEMPAR saat mencetak "→" atau "°",
# menjatuhkan skrip sebelum satu berkas pun ditulis. Diperbaiki di sini, bukan
# diserahkan ke pemanggil lewat PYTHONIOENCODING, supaya skrip ini bisa
# dijalankan siapa pun tanpa menyetel apa-apa lebih dulu.
for aliran in (sys.stdout, sys.stderr):
    if hasattr(aliran, "reconfigure"):
        aliran.reconfigure(encoding="utf-8", errors="replace")

AKAR = Path(__file__).resolve().parents[2]
ALERT_BACKEND = AKAR / "backend/app/mock_data/sample_predictions.json"
ALERT_FRONTEND = AKAR / "frontend/public/mock/sample_predictions.json"
IOT_FRONTEND = AKAR / "frontend/public/mock/iot_nodes.json"
WILAYAH = AKAR / "frontend/public/mock/wilayah_operasi.json"

# Posko & pangkalan drone — POSISI ANDAIAN, lihat catatan di kepala berkas.
POSKO = {
    "nama": "Posko lapangan Kereng Bangkirai",
    "lat": -2.2542,
    "lon": 113.8192,
}

# Sebaran alert: (jarak_km, bearing_derajat) dari posko.
#
# Dipilih tangan, bukan acak, dan sengaja MELEWATI jangkauan sapuan drone.
# Empat titik terjauh berada di luar anggaran baterai satu penerbangan — itu
# justru inti masalahnya: operator tidak bisa memverifikasi semuanya sekaligus,
# jadi urutan prioritas benar-benar berarti. Sebaran yang seluruhnya terjangkau
# akan menyembunyikan kendala yang paling menentukan.
#
# SEMUA TITIK HARUS JATUH DI DARAT, dan itu tidak boleh dianggap sepele.
# Percobaan pertama memakai arah 315 derajat dan 190 derajat; keduanya menabrak
# selat, karena posko berdiri di sebuah pulau. Gejalanya menyesatkan: blok
# `wilayah`, `bmkg`, dan `penutup_lahan` gagal terus-menerus pada dua alert itu
# walau geoportal BIG sehat, dan peringatan pembekuan terbaca seolah layanannya
# sedang memblokir. Padahal titiknya memang tidak berada di wilayah administratif
# mana pun.
#
# Jalankan `--periksa` setiap kali angka di bawah diubah. Lihat `periksa_darat`.
SEBARAN = [
    (3.4, 295),
    (5.1, 340),
    (6.8, 25),
    (4.2, 210),
    (8.3, 260),
    (7.1, 150),
    (12.5, 70),
    (13.2, 45),
    (16.0, 95),
    (17.8, 280),
]

# Node sensor ikut dipusatkan — jaringan sensor darat yang tersebar empat
# provinsi tidak masuk akal untuk satu posko.
SEBARAN_IOT = [
    (2.1, 300),
    (4.6, 20),
    (6.2, 235),
    (9.4, 120),
    (12.1, 330),
    (14.7, 60),
]


def geser(lat: float, lon: float, jarak_km: float, bearing_deg: float) -> tuple[float, float]:
    """Titik pada jarak & arah tertentu dari sebuah koordinat."""
    R = 6371.0088
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    d = jarak_km / R
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(
        math.sin(b) * math.sin(d) * math.cos(p1),
        math.cos(d) - math.sin(p1) * math.sin(p2),
    )
    return round(math.degrees(p2), 4), round(math.degrees(l2), 4)


def periksa_darat(pangkalan: tuple[float, float]) -> int:
    """Pastikan tiap titik SEBARAN jatuh di poligon desa BIG — yakni di darat.

    Titik di laut tidak akan pernah punya wilayah administratif, sehingga blok
    `wilayah`, `bmkg`, dan `penutup_lahan` gagal selamanya. Menjalankan ulang
    pembekuan tidak akan pernah memperbaikinya, dan peringatannya terbaca
    seolah layanan luar sedang memblokir. Lebih murah menangkapnya di sini.

    Kembalikan jumlah titik yang bermasalah.
    """
    import time

    import httpx

    basis = (
        "https://geoservices.big.go.id/gis/rest/services/"
        "BAPANAS/Batas_Administrasi/MapServer/2/query"
    )
    bermasalah = 0
    for i, (jarak, arah) in enumerate(SEBARAN, 1):
        lat, lon = geser(pangkalan[0], pangkalan[1], jarak, arah)
        parameter = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "WADMKD",
            "returnGeometry": "false",
            "f": "json",
        }
        try:
            respons = httpx.get(
                basis,
                params=parameter,
                headers={"User-Agent": "karhutla-dashboard-operator/0.9"},
                timeout=40.0,
            )
            respons.raise_for_status()
            fitur = respons.json().get("features") or []
        except Exception as galat:  # noqa: BLE001
            print(f"  {i:2d}. {jarak:5.1f} km {arah:3.0f}°  TIDAK BISA DIPERIKSA ({type(galat).__name__})")
            time.sleep(1.0)
            continue

        if fitur:
            print(f"  {i:2d}. {jarak:5.1f} km {arah:3.0f}°  darat — {fitur[0]['attributes'].get('WADMKD')}")
        else:
            print(f"  {i:2d}. {jarak:5.1f} km {arah:3.0f}°  *** DI LAUT — ganti arah/jaraknya ***")
            bermasalah += 1
        time.sleep(1.0)
    return bermasalah


def main() -> None:
    if "--periksa" in sys.argv:
        print("Memeriksa apakah tiap titik SEBARAN jatuh di darat…\n")
        bermasalah = periksa_darat((POSKO["lat"], POSKO["lon"]))
        print(
            "\nSemua titik di darat."
            if not bermasalah
            else f"\n{bermasalah} titik di laut. Perbaiki SEBARAN sebelum memusatkan."
        )
        sys.exit(1 if bermasalah else 0)

    with ALERT_BACKEND.open(encoding="utf-8") as berkas:
        alerts = json.load(berkas)

    if len(alerts) > len(SEBARAN):
        raise SystemExit(f"SEBARAN cuma {len(SEBARAN)} titik untuk {len(alerts)} alert")

    print(f"Posko andaian: {POSKO['lat']}, {POSKO['lon']}\n")
    for alert, (jarak, arah) in zip(alerts, SEBARAN):
        lat, lon = geser(POSKO["lat"], POSKO["lon"], jarak, arah)
        alert["location"] = {"lat": lat, "lon": lon}
        print(f"  {alert['alert_id'][:8]} → {lat:8.4f}, {lon:9.4f}   {jarak:5.1f} km  {arah:3.0f}°")

    for tujuan in (ALERT_BACKEND, ALERT_FRONTEND):
        with tujuan.open("w", encoding="utf-8") as berkas:
            json.dump(alerts, berkas, ensure_ascii=False, indent=2)
        print(f"\nDitulis: {tujuan.relative_to(AKAR)}")

    with IOT_FRONTEND.open(encoding="utf-8") as berkas:
        iot = json.load(berkas)
    print()
    for node, (jarak, arah) in zip(iot.get("node", []), SEBARAN_IOT):
        lat, lon = geser(POSKO["lat"], POSKO["lon"], jarak, arah)
        node["lat"], node["lon"] = lat, lon
        print(f"  {node['node_id']} → {lat:8.4f}, {lon:9.4f}   {jarak:5.1f} km")
    with IOT_FRONTEND.open("w", encoding="utf-8") as berkas:
        json.dump(iot, berkas, ensure_ascii=False, indent=2)
    print(f"\nDitulis: {IOT_FRONTEND.relative_to(AKAR)}")

    with WILAYAH.open("w", encoding="utf-8") as berkas:
        json.dump(
            {
                "catatan": (
                    "Wilayah cakupan CONTOH untuk demo: satu posko, satu pangkalan "
                    "drone. Posisi posko adalah posisi ANDAIAN — kami tidak "
                    "memverifikasi Daops mana yang membawahi koordinat ini maupun "
                    "di mana poskonya berdiri. Koordinat alert tetap penempatan "
                    "simulasi seperti sebelumnya; yang berubah hanya sebarannya "
                    "agar koheren untuk satu wilayah operasi."
                ),
                "posko": POSKO,
                "wilayah": "Palangka Raya, Kalimantan Tengah",
                "adalah_andaian": True,
            },
            berkas,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Ditulis: {WILAYAH.relative_to(AKAR)}")
    print("\nLANGKAH BERIKUTNYA — koordinat berubah, jadi cuplikan size-up basi:")
    print("    python backend/scripts/bekukan_sizeup.py")


if __name__ == "__main__":
    main()
