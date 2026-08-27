"""Sapu seluruh layer geoportal BIG untuk mencari layer gambut / KHG.

KENAPA ADA: produk ini menyatakan di layar bahwa **tidak ada** peta Kesatuan
Hidrologis Gambut di server publik BIG. Pernyataan negatif seperti itu mudah
diucapkan dan sulit dipercaya, jadi ia butuh alat yang membuktikannya — bukan
sekadar catatan "saya sudah cek".

Jalankan kapan saja untuk memeriksa ulang:

    python backend/scripts/sapu_layer_big.py

HASIL 26 Agustus 2026 — dan provenansnya disebut apa adanya:

  Sapuan LENGKAP (enumerasi terpisah lewat PowerShell, nol bagian terlewat):
      78 layanan · 982 layer · NOL layer gambut/KHG.
  Tiga sapuan skrip ini pada hari yang sama, masing-masing bolong sedikit
  (76/944, 78/967, 67/867): semuanya juga NOL layer gambut/KHG.

  Satu-satunya yang cocok dengan pola pencarian adalah "Rawan Tsunami", "Rawan
  Gempa Bumi", dan "Rawan Gerakan Tanah" — kata "rawan", bukan "rawa".

Empat pengamatan sepakat, jadi temuannya kuat. Tetapi angka 78/982 berasal dari
enumerasi PowerShell itu, BUKAN dari skrip ini — dan itu disebutkan supaya tidak
ada yang mengira skrip ini sudah pernah mencetaknya.

BIG MEMBATASI LAJU. Setelah beberapa sapuan penuh beruntun, ia berhenti menjawab
sama sekali (handshake TLS menggantung sejak permintaan pertama). Blokirnya
sementara. Jalankan skrip ini SEKALI, bukan berulang; kalau ia gagal total,
tunggu belasan menit sebelum mencoba lagi.

Kalau suatu hari BIG menerbitkan layer gambut, skrip ini yang akan menemukannya
lebih dulu, dan catatan di UI serta `SIZEUP_CONTRACT.md` harus segera diperbarui.

CATATAN JARINGAN: pada host ini, klien HTTP yang berbeda berperilaku berbeda di
mesin yang SAMA. Diamati 26 Agustus 2026: `httpx` dan PowerShell berhasil,
sementara `curl` dan `urllib.request` gagal menyelesaikan handshake TLS (TCP
tersambung, handshake tidak pernah selesai). Kami sempat menyimpulkan "server
BIG mati" gara-gara itu, dan kesimpulan itu keliru. Kalau skrip ini gagal total,
curigai lapisan jaringan lebih dulu sebelum menyimpulkan servernya mati.
"""
from __future__ import annotations

import re
import sys
import time

import httpx

BASIS = "https://geoservices.big.go.id/gis/rest/services"
POLA = re.compile(r"gambut|peat|khg|hidrologis|rawa", re.IGNORECASE)

# "Rawan" (bencana) cocok dengan pola "rawa" tetapi artinya sama sekali berbeda.
# Disaring terpisah supaya laporannya tidak penuh temuan palsu.
PALSU = re.compile(r"rawan", re.IGNORECASE)

# Jeda antar permintaan. Ini yang membuat sapuan berhasil, bukan percobaan ulang.
#
# Diamati saat mengembangkan skrip ini: sapuan tanpa jeda kehilangan satu-dua
# layanan acak; menambah percobaan ulang justru MEMPERBURUK (5 folder hilang),
# karena ia menambah jumlah permintaan sekaligus memperpanjang durasi tekanan.
# Servernya melemah di bawah permintaan beruntun, persis seperti Overpass.
# Melambat menyelesaikannya; mencoba lebih keras tidak.
#
# Jangan menjalankan skrip ini berulang kali beruntun — tekanannya menumpuk.
JEDA_DETIK = 0.5


def ambil(url: str, timeout: int = 30, percobaan: int = 2):
    """Pakai httpx, BUKAN urllib — dan itu bukan selera.

    Diamati 26 Agustus 2026 di mesin yang sama, pada host ini: httpx berhasil
    menyelesaikan handshake TLS sementara `urllib.request` selalu kehabisan
    waktu. Kalau skrip ini pernah diubah kembali ke urllib, ia akan melaporkan
    "server mati" untuk server yang sebenarnya sehat — persis kekeliruan yang
    dijelaskan di CATATAN JARINGAN.

    Percobaan ulang di sini SEDIKIT saja (dua), dan sengaja. Dugaan pertama kami
    keliru: kami mengira permintaan yang jatuh itu acak dan menambah percobaan
    ulang akan menutupinya. Hasilnya justru sebaliknya — sapuan dengan tiga
    percobaan kehilangan LIMA folder, jauh lebih buruk daripada satu layanan
    yang hilang tanpa percobaan ulang. Mencoba lebih keras menambah jumlah
    permintaan sekaligus memperpanjang durasi tekanan pada server yang memang
    melemah di bawah beban beruntun.

    Yang menyelesaikannya adalah `JEDA_DETIK`. Melambat berhasil; memaksa tidak.
    """
    galat_terakhir: Exception | None = None
    for i in range(percobaan):
        try:
            respons = httpx.get(
                url,
                headers={"User-Agent": "karhutla-dashboard-operator/0.9"},
                timeout=timeout,
            )
            respons.raise_for_status()
            return respons.json()
        except Exception as galat:  # noqa: BLE001, PERF203
            galat_terakhir = galat
            if i < percobaan - 1:
                time.sleep(2.0 * (i + 1))
    raise galat_terakhir  # type: ignore[misc]


def main() -> None:
    try:
        akar = ambil(f"{BASIS}?f=json")
    except Exception as galat:  # noqa: BLE001
        print(f"GAGAL menghubungi {BASIS}: {galat}")
        print("Lihat CATATAN JARINGAN di kepala berkas ini sebelum menyimpulkan.")
        sys.exit(1)

    folder = akar.get("folders", [])
    print(f"{len(folder)} folder: {', '.join(folder)}\n")

    layanan = 0
    layer = 0
    cocok: list[str] = []
    palsu: list[str] = []
    # Cakupan yang tidak lengkap HARUS dilacak. Skrip ini ada untuk menyokong
    # pernyataan NEGATIF ("tidak ada peta gambut"), dan pernyataan negatif dari
    # sapuan yang bolong tidak membuktikan apa pun.
    terlewat: list[str] = []

    for f in folder:
        time.sleep(JEDA_DETIK)
        try:
            isi = ambil(f"{BASIS}/{f}?f=json")
        except Exception:  # noqa: BLE001
            print(f"  [{f}] folder tidak bisa dibaca, DILEWATI")
            terlewat.append(f"folder {f}")
            continue

        for s in isi.get("services", []):
            layanan += 1
            time.sleep(JEDA_DETIK)
            try:
                peta = ambil(f"{BASIS}/{s['name']}/{s['type']}?f=json", timeout=25)
            except Exception:  # noqa: BLE001
                print(f"  [{s['name']}] layanan tidak bisa dibaca, DILEWATI")
                terlewat.append(f"layanan {s['name']}")
                continue
            for l in peta.get("layers") or []:
                layer += 1
                nama = l.get("name") or ""
                if POLA.search(nama):
                    baris = f"{s['name']} [{l.get('id')}] {nama}"
                    (palsu if PALSU.search(nama) else cocok).append(baris)

    print(f"Layanan diperiksa : {layanan}")
    print(f"Layer diperiksa   : {layer}")
    print()

    if cocok:
        print("DITEMUKAN layer yang mungkin gambut/KHG:")
        for b in cocok:
            print(f"  · {b}")
        print("\nPerbarui SIZEUP_CONTRACT.md, big_client.py, dan teks di PanelSizeUp.jsx.")
    elif terlewat:
        # Nol temuan pada sapuan bolong BUKAN bukti ketiadaan.
        print("Nol layer gambut/KHG pada bagian yang berhasil dibaca —")
        print(f"TETAPI {len(terlewat)} bagian TERLEWAT, jadi sapuan ini BELUM konklusif:")
        for t in terlewat:
            print(f"  · {t}")
        print("\nJalankan ulang sampai bersih sebelum memakai hasilnya sebagai bukti.")
        sys.exit(2)
    else:
        print("Sapuan LENGKAP, nol layer gambut/KHG.")
        print("Catatan di UI dan SIZEUP_CONTRACT.md masih benar.")

    if palsu:
        print(f"\n({len(palsu)} cocok karena kata \"rawan\" — bencana, bukan rawa/gambut)")


if __name__ == "__main__":
    main()
