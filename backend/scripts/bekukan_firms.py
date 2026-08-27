"""Bekukan cuplikan hotspot FIRMS nyata untuk deployment statis.

KENAPA ADA: MAP_KEY tidak boleh masuk bundle frontend, jadi deployment statis
(Vercel tanpa backend) tidak bisa memanggil NASA sendiri. Alih-alih memakai
berkas contoh karangan, skrip ini membekukan data satelit SUNGGUHAN beserta
waktu pengambilannya, dan UI melabelinya sebagai cuplikan — bukan sebagai data
langsung.

Perbedaannya penting dan disengaja:
    berkas contoh  → titik karangan, tidak pernah terjadi
    cuplikan       → hotspot nyata, terjadi pada waktu yang tercatat
    langsung       → ditarik saat halaman dibuka (butuh backend)

Jalankan dengan backend lokal menyala:
    uvicorn app.main:app --port 8000      # terminal lain, MAP_KEY terisi
    python backend/scripts/bekukan_firms.py

Perbarui sebelum demo supaya tanggalnya masih relevan.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
TUJUAN = AKAR / 'frontend/public/mock/firms_snapshot.json'
WILAYAH = AKAR / 'frontend/public/mock/wilayah_operasi.json'
WIB = timezone(timedelta(hours=7))

# Ambil SEMUA titik, lalu saring sendiri menurut jarak — bukan menyerahkan
# pemangkasan ke `batas` di server.
# Tanggal demo DIKUNCI. Rekaman final tidak boleh bergantung pada apa yang
# kebetulan terbakar di hari perekaman — kalau AOI sedang sepi, peta kosong dan
# demo kehilangan seluruh isinya. Datanya tetap deteksi satelit sungguhan; yang
# dipilih hanya tanggalnya, dan UI menampilkan tanggal itu apa adanya.
#
# Kosongkan untuk kembali memakai data terakhir.
TANGGAL_DEMO = '2026-08-19'

SUMBER = 'http://127.0.0.1:8000/api/firms/hotspots?batas=5000'
if TANGGAL_DEMO:
    SUMBER += f'&tanggal={TANGGAL_DEMO}'

# =============================================================================
#  KENAPA DISARING MENURUT JARAK, BUKAN MENURUT FRP
# =============================================================================
# Endpoint memangkas ke N titik ber-FRP tertinggi supaya peta tidak tersendat.
# Itu masuk akal ketika demo mencakup seluruh Sumatra-Kalimantan.
#
# Setelah produk berkomitmen pada SATU wilayah operasi, pemangkasan itu jadi
# salah, dan salahnya senyap: diamati 27 Agustus 2026, dari 4.712 titik yang
# terdeteksi, "400 terkuat" seluruhnya berada di luar wilayah operasi, karena
# api di sana kebetulan lemah (2-14 MW) sementara ambang 400-terkuat ada di
# 19,4 MW. Cuplikan yang dihasilkan menyisakan empat kandidat, semuanya di luar
# jangkauan drone, dan perencana sapuan mengembalikan nol singgah.
#
# Konsol operasi untuk satu Daops harus menampilkan api DI DAOPS ITU, bukan 400
# api terkuat se-nasional. Karena itu penyaringnya jarak.
RADIUS_KM = 60.0
BATAS_TITIK = 600


def jarak_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def main() -> None:
    try:
        with urllib.request.urlopen(SUMBER, timeout=90) as respons:
            data = json.loads(respons.read().decode('utf-8'))
    except Exception as galat:  # noqa: BLE001 — pesan ramah lebih berguna di sini
        print(f'GAGAL menghubungi backend lokal: {galat}')
        print('Pastikan `uvicorn app.main:app --port 8000` menyala dan MAP_KEY terisi.')
        sys.exit(1)

    if data.get('is_fixture'):
        print('DITOLAK: backend mengembalikan fixture, bukan data satelit.')
        print('MAP_KEY belum terbaca — cuplikan dari fixture tidak ada gunanya.')
        sys.exit(1)

    semua = data.get('titik', [])
    if not semua:
        print('DITOLAK: nol titik. Tidak ada yang layak dibekukan.')
        sys.exit(1)

    posko = json.loads(WILAYAH.read_text(encoding='utf-8'))['posko']
    dekat = []
    for t in semua:
        if not isinstance(t.get('lat'), (int, float)) or not isinstance(t.get('lon'), (int, float)):
            continue
        d = jarak_km(posko['lat'], posko['lon'], t['lat'], t['lon'])
        if d <= RADIUS_KM:
            dekat.append((d, t))
    dekat.sort(key=lambda x: x[0])
    titik = [t for _, t in dekat[:BATAS_TITIK]]

    if not titik:
        print(f'DITOLAK: nol titik dalam {RADIUS_KM:.0f} km dari posko.')
        print('Wilayah operasi tanpa kebakaran di dalamnya tidak bisa')
        print('mendemonstrasikan verifikasi. Pindahkan posko, atau tunggu data baru.')
        sys.exit(1)

    cuplikan = {
        'is_fixture': False,
        'is_cuplikan': True,
        'diambil': datetime.now(tz=WIB).isoformat(timespec='seconds'),
        'sumber': data.get('sumber'),
        'rentang_hari': data.get('rentang_hari'),
        'tanggal_arsip': data.get('tanggal_arsip'),
        'jumlah': len(titik),
        'jumlah_total': data.get('jumlah_total', len(semua)),
        'dipangkas': len(titik) < len(semua),
        'radius_km': RADIUS_KM,
        'pusat': {'lat': posko['lat'], 'lon': posko['lon'], 'nama': posko.get('nama')},
        'titik': titik,
    }
    TUJUAN.write_text(json.dumps(cuplikan, ensure_ascii=False) + '\n', encoding='utf-8')

    frp = [t['frp_mw'] for t in titik if t.get('frp_mw')]
    print(f'cuplikan ditulis: {TUJUAN.relative_to(AKAR)}')
    print(f'  diambil     : {cuplikan["diambil"]}')
    print(f'  titik       : {cuplikan["jumlah"]} dalam {RADIUS_KM:.0f} km dari posko')
    print(f'  terdeteksi  : {cuplikan["jumlah_total"]} di seluruh AOI')
    print(f'  FRP         : {min(frp):.1f} - {max(frp):.1f} MW')
    print(f'  ukuran      : {TUJUAN.stat().st_size / 1024:.0f} KB')


if __name__ == '__main__':
    main()
