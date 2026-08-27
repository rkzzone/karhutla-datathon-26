"""Bekukan konteks size-up nyata untuk deployment statis dan untuk rekaman demo.

KENAPA ADA — dua alasan, dan yang kedua yang sebenarnya mendesak.

1. Deployment statis (Vercel tanpa backend) tidak bisa memanggil Open-Meteo dan
   Overpass sendiri dengan rapi. Sama seperti `bekukan_firms.py`, skrip ini
   membekukan data SUNGGUHAN beserta waktu pengambilannya, dan UI melabelinya
   sebagai cuplikan — bukan sebagai data langsung.

2. Overpass adalah infrastruktur sukarela yang memblokir agresif. Diamati
   26 Agustus 2026: dua kueri uji berturut-turut dari satu IP sudah cukup untuk
   membuat `overpass-api.de` menolak koneksi di tingkat TLS, dan dua mirror
   membalas 500. Blokirnya sementara, tetapi kalau ia datang di menit ketiga
   rekaman demo, panel size-up kosong dan tidak ada cara memperbaikinya di
   tempat.

   Karena itu: JANGAN merekam demo dengan mengandalkan Overpass hidup. Jalankan
   skrip ini lebih dulu, pastikan berkasnya lengkap, baru rekam.

Tiga keadaan yang dipertahankan UI, sama persis dengan lapisan FIRMS:
    tidak tersedia → tidak ada backend dan tidak ada cuplikan
    cuplikan       → cuaca & geografi nyata, beku pada waktu tercatat
    langsung       → ditarik saat panel dibuka (butuh backend)

Jalankan dengan backend lokal menyala:
    uvicorn app.main:app --port 8000      # terminal lain
    python backend/scripts/bekukan_sizeup.py

Perbarui menjelang demo supaya cuacanya masih relevan — cuaca beku berumur
seminggu tetap jujur (waktunya tercatat), tapi tidak lagi menarik.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER_ALERT = AKAR / "backend/app/mock_data/sample_predictions.json"
TUJUAN = AKAR / "frontend/public/mock/sizeup_snapshot.json"
BASIS = "http://127.0.0.1:8000/api/sizeup"
WIB = timezone(timedelta(hours=7))

# Jeda antar alert. Bukan kehati-hatian berlebihan: diamati 26 Agustus 2026,
# SATU kueri berhasil sudah cukup untuk membuat Overpass menolak kueri
# berikutnya beberapa menit kemudian. Sepuluh alert beruntun tanpa jeda tidak
# akan pernah selesai.
JEDA_DETIK = 15.0

# Percobaan ulang per alert, dengan jeda yang memanjang. Blokir Overpass bersifat
# sementara, jadi menunggu jauh lebih berguna daripada menyerah — dan jauh lebih
# sopan daripada mencoba lagi secepat mungkin.
JEDA_ULANG_DETIK = (30.0, 90.0, 180.0)


def ambil(lat: float, lon: float, alert_id: str) -> dict | None:
    parameter = urllib.parse.urlencode({"lat": lat, "lon": lon, "alert_id": alert_id})
    try:
        with urllib.request.urlopen(f"{BASIS}?{parameter}", timeout=180) as respons:
            return json.loads(respons.read().decode("utf-8"))
    except Exception as galat:  # noqa: BLE001 — pesan ramah lebih berguna di sini
        print(f"  GAGAL {alert_id[:8]}: {galat}")
        return None


def _blok_gagal(hasil: dict) -> list[str]:
    return [
        nama for nama, isi in hasil.get("blok", {}).items() if isi.get("status") != "ada"
    ]


def muat_sebelumnya() -> dict[str, dict]:
    """Cuplikan yang sudah ada, supaya skrip ini bisa DILANJUTKAN, bukan diulang.

    Ini bukan kenyamanan. Karena Overpass memblokir di tengah jalan, sekali
    jalan penuh sering hanya menghasilkan sebagian. Tanpa kemampuan melanjutkan,
    percobaan berikutnya membuang alert yang sudah berhasil dan menariknya lagi
    dari nol — menambah beban kueri yang justru memicu blokir berikutnya.
    """
    if not TUJUAN.exists():
        return {}
    try:
        with TUJUAN.open(encoding="utf-8") as berkas:
            return json.load(berkas).get("sizeup", {}) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    with SUMBER_ALERT.open(encoding="utf-8") as berkas:
        alerts = json.load(berkas)

    beku = muat_sebelumnya()
    lengkap_sebelumnya = {
        aid for aid, isi in beku.items() if not _blok_gagal(isi)
    }
    if lengkap_sebelumnya:
        print(f"Melanjutkan — {len(lengkap_sebelumnya)} alert sudah lengkap, dilewati.\n")

    tak_lengkap: list[str] = []

    for i, alert in enumerate(alerts):
        alert_id = alert["alert_id"]
        lokasi = alert["location"]
        if alert_id in lengkap_sebelumnya:
            continue

        print(f"[{i + 1}/{len(alerts)}] {alert_id[:8]} …", end=" ", flush=True)
        hasil = None
        for percobaan, jeda in enumerate((0.0, *JEDA_ULANG_DETIK)):
            if jeda:
                print(f"\n    ulang {percobaan} setelah {jeda:.0f} dtk …", end=" ", flush=True)
                time.sleep(jeda)
            hasil = ambil(lokasi["lat"], lokasi["lon"], alert_id)
            if hasil is not None and not _blok_gagal(hasil):
                break

        if hasil is None:
            continue

        gagal = _blok_gagal(hasil)
        # Blok yang gagal TETAP dibekukan apa adanya, tidak ditambal. Kartu yang
        # jujur melaporkan "peta tidak bisa dimuat" lebih baik daripada kartu
        # yang terisi angka yang tidak pernah diambil.
        hasil["is_cuplikan"] = True
        beku[alert_id] = hasil
        if gagal:
            tak_lengkap.append(f"{alert_id[:8]} ({', '.join(gagal)})")
            print(f"sebagian — gagal: {', '.join(gagal)}")
        else:
            print("lengkap")

        if i < len(alerts) - 1:
            time.sleep(JEDA_DETIK)

    if not beku:
        print("\nTidak ada satu pun alert yang berhasil. Berkas TIDAK ditulis.")
        print("Pastikan `uvicorn app.main:app --port 8000` menyala.")
        sys.exit(1)

    keluaran = {
        "is_cuplikan": True,
        "dibekukan": datetime.now(WIB).isoformat(),
        "jumlah": len(beku),
        "sumber": ["Open-Meteo", "OpenStreetMap"],
        "sizeup": beku,
    }
    TUJUAN.parent.mkdir(parents=True, exist_ok=True)
    with TUJUAN.open("w", encoding="utf-8") as berkas:
        json.dump(keluaran, berkas, ensure_ascii=False, indent=2)

    print(f"\nDitulis: {TUJUAN.relative_to(AKAR)} — {len(beku)}/{len(alerts)} alert")
    if tak_lengkap:
        print("\nPERINGATAN — blok berikut beku dalam keadaan gagal:")
        for baris in tak_lengkap:
            print(f"  · {baris}")
        # Menyebut layanan yang BENAR-BENAR gagal, bukan menebak.
        #
        # Versi sebelumnya selalu menuduh Overpass. Itu keliru dan menyesatkan:
        # blok `wilayah`, `bmkg`, dan `penutup_lahan` bergantung pada geoportal
        # BIG, bukan Overpass, sehingga orang yang membaca peringatan itu akan
        # menunggu layanan yang salah pulih.
        gabungan = " ".join(tak_lengkap)
        tersangka = []
        if any(b in gabungan for b in ("wilayah", "bmkg", "penutup_lahan")):
            tersangka.append("geoportal BIG")
        if any(b in gabungan for b in ("sumber_air", "akses", "peralatan")):
            tersangka.append("Overpass")
        if any(b in gabungan for b in ("cuaca", "bahaya")):
            tersangka.append("Open-Meteo")
        print(
            f"\nYang kemungkinan sedang memblokir: "
            f"{' dan '.join(tersangka) or 'sumber luar'}.\n"
            "Tunggu 15-30 menit lalu jalankan skrip ini lagi — alert yang sudah\n"
            "lengkap otomatis dilewati, jadi menjalankannya berulang kali aman dan\n"
            "makin lama makin lengkap.\n"
            "JANGAN merekam demo sebelum baris peringatan ini bersih."
        )


if __name__ == "__main__":
    main()
