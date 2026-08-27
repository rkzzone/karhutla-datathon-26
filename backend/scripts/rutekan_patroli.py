"""Ubah jalur patroli dari garis lurus menjadi rute yang mengikuti jalan nyata.

=============================================================================
 MASALAH YANG DIPERBAIKI
=============================================================================
Sampai 26 Agustus 2026, `patrol_routes.json` berisi enam titik yang ditarik
lurus satu sama lain. Di peta, garis itu memotong sungai, rawa, dan hutan tanpa
peduli ada jalan atau tidak — regu patroli darat jelas tidak bergerak begitu.
Seorang anggota tim menangkapnya hanya dengan melihat peta, dan ia benar.

Skrip ini mengganti geometri antar-titik dengan rute jalan sungguhan dari OSRM
(mesin routing di atas data OpenStreetMap, gratis tanpa kunci API), sekaligus
mengambil jarak tempuh dan durasi tempuh yang dihitungnya.

=============================================================================
 APA YANG NYATA DAN APA YANG TIDAK — JANGAN SAMPAI TERTUKAR
=============================================================================
NYATA setelah skrip ini jalan:
  · geometri jalur — jalan yang benar-benar ada di OpenStreetMap
  · jarak tempuh dan durasi tempuh, dihitung di atas jaringan jalan itu

TETAP CONTOH, dan wajib tetap berlabel begitu di UI:
  · titik-titik rencananya sendiri (sektor mana yang dipatroli)
  · nama regu dan jadwalnya

Dengan kata lain: skrip ini membuat GEOMETRI-nya jujur, bukan RENCANA-nya nyata.
Menghapus label "contoh" di UI setelah menjalankan ini adalah kekeliruan yang
persis ingin dicegah berkas ini — jalur yang terlihat meyakinkan justru lebih
mudah disalahartikan sebagai rencana posko sungguhan daripada garis lurus yang
jelas-jelas kasar.

Jalankan:
    python backend/scripts/rutekan_patroli.py

Butuh jaringan. Kalau OSRM tidak bisa dihubungi, berkas TIDAK ditulis dan jalur
lama dipertahankan apa adanya — lebih baik garis lurus berlabel jujur daripada
berkas setengah jadi.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import httpx

AKAR = Path(__file__).resolve().parents[2]
BERKAS = AKAR / "frontend/public/mock/patrol_routes.json"

# Dua server OSRM publik, dicoba berurutan. Keduanya gratis tanpa kunci dan
# berjalan di atas data OpenStreetMap yang sama.
ENDPOINT = (
    "https://router.project-osrm.org",
    "https://routing.openstreetmap.de/routed-car",
)
JEDA_DETIK = 1.5
_HEADER = {"User-Agent": "karhutla-dashboard-operator/0.9"}

# Toleransi penyederhanaan geometri, dalam meter.
#
# OSRM `overview=full` mengembalikan ~500-1600 titik per rute — jauh lebih rinci
# daripada yang bisa TERLIHAT, dan ketiga rute membengkakkan berkas statis jadi
# 177 KB. Alternatif bawaan OSRM (`overview=simplified`) terlalu kasar: 28 titik
# untuk 33 km, sekitar satu titik per 1,2 km, yang tampak patah-patah pada zoom
# tinggi.
#
# Angka di bawah diturunkan dari peta, bukan dikira-kira: zoom maksimum MapView
# adalah 14, dan pada zoom 14 di lintang khatulistiwa satu piksel ≈ 9,5 meter.
# Toleransi 8 m karena itu berada DI BAWAH satu piksel pada perbesaran terbesar
# yang bisa dicapai operator — penyederhanaannya tidak pernah terlihat.
TOLERANSI_METER = 8.0

# Batas penempelan titik ke jalan terdekat. Di atas ini, rute yang dikembalikan
# OSRM bukan lagi rute dari titik yang kita minta, dan menyajikannya sebagai
# rute pengerahan akan menyesatkan. Setengah kilometer sudah longgar: regu
# masih bisa berjalan kaki sejauh itu dari ujung jalan.
AMBANG_PENEMPELAN_M = 500.0


def _jarak_ke_ruas(t, a, b) -> float:
    """Jarak tegak lurus titik `t` ke ruas garis a-b, dalam meter.

    Proyeksi bidang datar sudah cukup: ruas yang dibandingkan panjangnya puluhan
    sampai ratusan meter, dan pada skala itu kelengkungan bumi tidak terasa.
    Bujur diskalakan cos(lintang) supaya derajat bujur dan lintang sebanding.
    """
    m_per_deg = 111_320.0
    skala = math.cos(math.radians(a[0]))
    ax, ay = a[1] * skala * m_per_deg, a[0] * m_per_deg
    bx, by = b[1] * skala * m_per_deg, b[0] * m_per_deg
    tx, ty = t[1] * skala * m_per_deg, t[0] * m_per_deg
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(tx - ax, ty - ay)
    u = max(0.0, min(1.0, ((tx - ax) * dx + (ty - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(tx - (ax + u * dx), ty - (ay + u * dy))


def sederhanakan(titik: list[list[float]], toleransi: float) -> list[list[float]]:
    """Ramer-Douglas-Peucker iteratif.

    Iteratif, bukan rekursif: rute terpanjang punya 1.600 titik, dan rekursi
    pada geometri yang hampir lurus bisa menembus batas tumpukan Python.
    """
    if len(titik) < 3:
        return titik
    simpan = [False] * len(titik)
    simpan[0] = simpan[-1] = True
    tumpukan = [(0, len(titik) - 1)]
    while tumpukan:
        awal, akhir = tumpukan.pop()
        if akhir <= awal + 1:
            continue
        terjauh, jarak_max = -1, 0.0
        for i in range(awal + 1, akhir):
            d = _jarak_ke_ruas(titik[i], titik[awal], titik[akhir])
            if d > jarak_max:
                terjauh, jarak_max = i, d
        if jarak_max > toleransi:
            simpan[terjauh] = True
            tumpukan.append((awal, terjauh))
            tumpukan.append((terjauh, akhir))
    return [t for t, pakai in zip(titik, simpan) if pakai]


def rutekan(titik: list[list[float]]) -> dict | None:
    """Titik rencana → rute jalan nyata. None kalau semua server gagal."""
    # OSRM memakai urutan bujur,lintang — kebalikan dari yang dipakai Leaflet
    # dan seluruh berkas ini. Tertukar di sini menghasilkan rute di tengah
    # Samudra Hindia, dan gejalanya tidak selalu langsung kelihatan.
    koordinat = ";".join(f"{lon},{lat}" for lat, lon in titik)
    for basis in ENDPOINT:
        url = f"{basis}/route/v1/driving/{koordinat}"
        try:
            respons = httpx.get(
                url,
                params={"overview": "full", "geometries": "geojson"},
                headers=_HEADER,
                timeout=45.0,
            )
            respons.raise_for_status()
            badan = respons.json()
        except (httpx.HTTPError, ValueError) as galat:
            print(f"    {basis.split('/')[2]} gagal: {type(galat).__name__}")
            continue

        if badan.get("code") != "Ok" or not badan.get("routes"):
            print(f"    {basis.split('/')[2]} menjawab: {badan.get('code')}")
            continue

        # PERIKSA PENEMPELAN SEBELUM MEMPERCAYAI RUTENYA.
        #
        # OSRM menempelkan tiap titik ke jalan terdekat TANPA memberi tahu, dan
        # tetap membalas `code: Ok`. Di wilayah bergambut yang jaringan jalannya
        # jarang, penempelan itu bisa kilometer jauhnya: diamati di Pulau Maya,
        # posko ditempel **3,9 km** dan titik api 1,7-2,0 km. Rute yang keluar
        # lalu menghubungkan dua titik jalan sembarang — bukan posko ke api.
        #
        # Gejalanya sempat lolos karena angkanya tampak masuk akal. Yang
        # membongkarnya: satu rute melaporkan jarak jalan 0,7 km untuk dua titik
        # yang berjarak lurus 2,1 km. Rute jalan mustahil lebih pendek dari
        # garis lurus antara titik yang sama, dan itulah tanda bahwa titik yang
        # dirutekan bukan titik yang diminta.
        #
        # Ketika penempelan terlalu jauh, jawaban yang benar bukan memperbaiki
        # rutenya melainkan MENGAKUI bahwa titik itu tidak tersambung jaringan
        # jalan. Itu fakta operasional yang nyata di gambut — dan justru
        # alasan terkuat kenapa drone berguna di sana.
        penempelan = [w.get("distance", 0.0) for w in (badan.get("waypoints") or [])]
        terjauh = max(penempelan) if penempelan else 0.0
        if terjauh > AMBANG_PENEMPELAN_M:
            print(
                f"    TIDAK TERSAMBUNG JALAN — titik ditempel sampai {terjauh:.0f} m "
                f"ke jalan terdekat (ambang {AMBANG_PENEMPELAN_M:.0f} m)"
            )
            return {
                "tersambung": False,
                "penempelan_terjauh_m": round(terjauh),
                "mesin": basis.split("/")[2],
            }

        rute = badan["routes"][0]
        penuh = [[lat, lon] for lon, lat in rute["geometry"]["coordinates"]]
        ringkas = sederhanakan(penuh, TOLERANSI_METER)
        return {
            "jalur": ringkas,
            "titik_penuh": len(penuh),
            "jarak_km": round(rute["distance"] / 1000, 1),
            "durasi_menit": round(rute["duration"] / 60),
            "mesin": basis.split("/")[2],
        }
    return None


def main() -> None:
    with BERKAS.open(encoding="utf-8") as berkas:
        data = json.load(berkas)

    rute = data.get("rute", [])
    berhasil = 0

    for r in rute:
        # Titik rencana diambil dari `titik_rencana` kalau sudah pernah
        # dirutekan, supaya menjalankan skrip ini dua kali tidak merutekan
        # ulang di atas hasil rutenya sendiri (389 titik jadi masukan OSRM).
        titik = r.get("titik_rencana") or r.get("jalur") or []
        if len(titik) < 2:
            print(f"[{r.get('rute_id')}] kurang dari dua titik, dilewati")
            continue

        print(f"[{r.get('rute_id')}] {len(titik)} titik rencana …", flush=True)
        hasil = rutekan(titik)
        if hasil is None:
            print("    GAGAL — jalur lama dipertahankan")
            continue

        r["titik_rencana"] = titik
        if not hasil.get("tersambung", True):
            # Jalur tetap digambar sebagai GARIS LURUS, dan ditandai tidak
            # tersambung. Menyembunyikannya akan membuat operator mengira titik
            # itu tak punya rencana pengerahan sama sekali; menyajikannya
            # sebagai rute jalan akan lebih buruk lagi.
            r["jalur"] = titik
            r["tersambung_jalan"] = False
            r["penempelan_terjauh_m"] = hasil["penempelan_terjauh_m"]
            r.pop("jarak_km", None)
            r.pop("durasi_menit", None)
            r["geometri_sumber"] = "garis lurus — tidak ada jalan terpetakan ke titik ini"
            berhasil += 1
            continue

        r["jalur"] = hasil["jalur"]
        r["tersambung_jalan"] = True
        r["jarak_km"] = hasil["jarak_km"]
        r["durasi_menit"] = hasil["durasi_menit"]
        r["geometri_sumber"] = f"OSRM ({hasil['mesin']}) di atas OpenStreetMap"
        berhasil += 1
        print(
            f"    {hasil['jarak_km']} km · {hasil['durasi_menit']} menit · "
            f"{len(hasil['jalur'])} titik geometri "
            f"(disederhanakan dari {hasil['titik_penuh']}, toleransi {TOLERANSI_METER} m)"
        )
        time.sleep(JEDA_DETIK)

    if not berhasil:
        print("\nTidak ada rute yang berhasil. Berkas TIDAK ditulis.")
        sys.exit(1)

    data["catatan"] = (
        "Rencana rute patroli CONTOH — titik sektor, nama regu, dan jadwalnya "
        "karangan untuk demo, bukan rencana posko sungguhan. Yang nyata adalah "
        "GEOMETRI jalurnya: jalan yang benar-benar ada di OpenStreetMap, beserta "
        "jarak dan durasi tempuh yang dihitung OSRM di atasnya. Ganti seluruh "
        "berkas ini dengan rencana posko saat integrasi lapangan."
    )
    with BERKAS.open("w", encoding="utf-8") as berkas:
        json.dump(data, berkas, ensure_ascii=False, indent=2)

    print(f"\nDitulis: {BERKAS.relative_to(AKAR)} — {berhasil}/{len(rute)} rute")
    print(
        "\nINGAT: geometrinya kini nyata, RENCANANYA tetap contoh. Label "
        "\"contoh\" di UI tidak boleh dihapus — jalur yang terlihat meyakinkan "
        "justru lebih mudah disalahartikan daripada garis lurus."
    )


if __name__ == "__main__":
    main()
