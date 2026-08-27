"""Lapisan size-up — mesin aturan deterministik, BUKAN model.

Rancangan lapisan: `docs/SIZEUP_CONTRACT.md`.

    PEMICU            DETEKSI                  SIZE-UP               TINDAKAN
    FIRMS / sensor →  fusi RGB+termal      →   konteks & rencana →   keputusan
                      keandalan modalitas      cuaca, angin, air     brief ke
                      lokalisasi               akses, tingkat alat   grup siaga
                      ---------------          ---------------
                      MODEL TERLATIH           ATURAN DETERMINISTIK
                      (tidak berubah)          (dapat diaudit)

Garis pemisah itu adalah inti argumennya, dan berkas ini adalah sisi KANANnya.
Konsekuensi yang harus dijaga setiap kali berkas ini disunting:

  1. Tidak ada satu pun nilai di sini yang berasal dari model. Semuanya
     dihitung dari cuaca/geografi dengan rumus yang tertulis di bawah, dan
     setiap keluaran membawa daftar `aturan`/`alasan` supaya bisa diperiksa
     di layar — bukan kotak hitam.
  2. `cuaca` TIDAK PERNAH mengalir balik menjadi masukan model deteksi
     (larangan nomor 13). Satu-satunya arah aliran: model → size-up.
  3. Kerucut arah selalu disebut **proyeksi arah angin**, tidak pernah
     "prediksi rambatan" (larangan nomor 14). Ia tidak memperhitungkan bahan
     bakar, kelerengan, maupun kelembapan gambut.
  4. Brief selalu berlabel **draf untuk verifikasi tim size-up** — sistem tidak
     pernah menyatakan api padam dan tidak pernah menentukan arah serangan.

Tiap blok berdiri sendiri: kalau Overpass tumbang, blok air/akses melapor gagal
sementara blok cuaca tetap tampil. Kartu size-up tidak pernah gagal seluruhnya
gara-gara satu sumber, dan tidak pernah menambal blok yang gagal dengan tebakan.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..schemas.prediction_schema import AlertPrediction
from . import big_client, bmkg_client, cuaca_client, fwi, model_client, osm_client

logger = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))

LABEL_PREDIKSI = {
    "fire_smoke": "Api + asap",
    "fire_no_smoke": "Api tanpa asap",
    "no_fire": "Tidak ada api",
}

# Provenans, disebut berdampingan dan tidak pernah salah satunya saja
# (Bagian 4 "Aturan pelabelan", butir 1).
CATATAN_PROVENANS = (
    "Cuaca (Open-Meteo), prakiraan resmi (BMKG), wilayah dan penutup lahan "
    "(Badan Informasi Geospasial), serta sumber air dan akses (OpenStreetMap) "
    "semuanya ditarik nyata untuk koordinat ini. Koordinatnya sendiri adalah "
    "penempatan simulasi di lahan gambut Indonesia, di atas citra benchmark "
    "FLAME 2 (Arizona)."
)
CATATAN_BRIEF = (
    "Draf untuk verifikasi tim size-up. Sistem tidak menyatakan api padam dan "
    "tidak menentukan arah serangan."
)
CATATAN_KERUCUT = (
    "Proyeksi arah angin, bukan prediksi rambatan model. Tidak memperhitungkan "
    "bahan bakar, kelerengan, maupun kelembapan gambut."
)


def _blok_gagal(alasan: str, pesan: str) -> dict[str, Any]:
    return {"status": "gagal", "alasan": alasan, "pesan": pesan}


# --------------------------------------------------------------------------- #
# Saran tingkat peralatan                                                      #
# --------------------------------------------------------------------------- #

# Kosakata peralatan berasal langsung dari keterangan praktisi polisi hutan
# (Bagian 3.5 dokumen rencana): manual (kepyok, garu) → semi-mekanis (jet
# shooter) → mekanis (mini striker), dengan embung plastik sebagai penyambung.
#
# Aturannya sederhana dan sengaja begitu: dua jarak menentukan satu saran, dan
# keduanya ditampilkan di layar bersama hasilnya. Ini SARAN, bukan perintah —
# tim size-up yang memutuskan setelah melihat sendiri.
TINGKAT_PERALATAN = {
    "mekanis": {
        "nama": "Mekanis",
        "contoh": "mini striker, pompa jinjing",
        "ambang_air_km": 2.0,
        "ambang_akses_km": 2.0,
    },
    "semi_mekanis": {
        "nama": "Semi-mekanis",
        "contoh": "jet shooter, embung plastik sebagai penyambung",
        "ambang_air_km": 5.0,
    },
    "manual": {
        "nama": "Manual",
        "contoh": "kepyok, garu — bertumpu pada sekat bakar, bukan pemadaman basah",
    },
}


def sarankan_peralatan(
    air: list[dict[str, Any]], akses: list[dict[str, Any]]
) -> dict[str, Any]:
    """Jarak air + ketersediaan akses kendaraan → satu saran tingkat peralatan."""
    air_terdekat = air[0] if air else None
    # Alat mekanis diangkut kendaraan; jalan setapak/servis tidak dihitung
    # sebagai akses yang memadai untuk itu.
    akses_berat = next((j for j in akses if j.get("kendaraan_berat")), None)
    akses_terdekat = akses[0] if akses else None

    jarak_air = air_terdekat["jarak_km"] if air_terdekat else None
    jarak_akses = akses_berat["jarak_km"] if akses_berat else None

    alasan: list[str] = []
    if air_terdekat:
        sebutan = air_terdekat["nama"] or air_terdekat["jenis_nama"].lower()
        alasan.append(f"sumber air terdekat {sebutan} {jarak_air} km")
    else:
        alasan.append("tidak ada sumber air terpetakan dalam radius pencarian")
    if akses_berat:
        alasan.append(f"akses kendaraan terdekat {akses_berat['jenis_nama'].lower()} {jarak_akses} km")
    elif akses_terdekat:
        alasan.append(
            f"hanya {akses_terdekat['jenis_nama'].lower()} {akses_terdekat['jarak_km']} km — "
            "belum tentu dilalui kendaraan pengangkut alat"
        )
    else:
        alasan.append("tidak ada akses jalan terpetakan dalam radius pencarian")

    mek = TINGKAT_PERALATAN["mekanis"]
    if (
        jarak_air is not None
        and jarak_akses is not None
        and jarak_air <= mek["ambang_air_km"]
        and jarak_akses <= mek["ambang_akses_km"]
    ):
        kunci = "mekanis"
        alasan.append(
            f"air ≤ {mek['ambang_air_km']} km dan akses kendaraan ≤ "
            f"{mek['ambang_akses_km']} km → alat mekanis bisa dibawa masuk"
        )
    elif jarak_air is not None and jarak_air <= TINGKAT_PERALATAN["semi_mekanis"]["ambang_air_km"]:
        kunci = "semi_mekanis"
        alasan.append(
            f"air ≤ {TINGKAT_PERALATAN['semi_mekanis']['ambang_air_km']} km tapi syarat "
            "mekanis tidak terpenuhi → pemadaman basah lewat penyambungan"
        )
    else:
        kunci = "manual"
        alasan.append(
            "air di luar jangkauan penyambungan atau tidak terpetakan → bertumpu "
            "pada sekat bakar"
        )

    tingkat = TINGKAT_PERALATAN[kunci]
    return {
        "status": "ada",
        "tingkat": kunci,
        "nama": tingkat["nama"],
        "contoh": tingkat["contoh"],
        "alasan": alasan,
    }


# --------------------------------------------------------------------------- #
# Brief siap tempel                                                            #
# --------------------------------------------------------------------------- #


def _baris_deteksi(alert: Optional[AlertPrediction]) -> list[str]:
    """Baris deteksi di brief. Kosong kalau alert tidak dikenali — tidak dikarang."""
    if alert is None:
        return []
    p = alert.prediction
    baris = [
        f"Deteksi: {LABEL_PREDIKSI.get(p.label, p.label)} · "
        f"keyakinan {round(p.confidence * 100)}%"
    ]
    m = alert.modality_reliability
    if m.rgb is None or m.thermal is None:
        baris.append("Keandalan modalitas: belum terukur")
    else:
        selisih = m.thermal - m.rgb
        if max(m.rgb, m.thermal) < 0.45:
            ringkas = "dua modalitas lemah"
        elif selisih >= 0.15:
            ringkas = "bersandar pada termal"
        elif selisih <= -0.15:
            ringkas = "bersandar pada RGB"
        else:
            ringkas = "dua modalitas seimbang"
        baris.append(
            f"Keandalan modalitas: RGB {round(m.rgb * 100)}% · "
            f"termal {round(m.thermal * 100)}% — {ringkas}"
        )
    return baris


def _sebut_fitur(fitur: dict[str, Any]) -> str:
    nama = fitur.get("nama")
    jenis = fitur["jenis_nama"]
    # Nama OSM di Indonesia lazimnya sudah memuat jenisnya ("Sungai Kahayan",
    # "Jalan Trans Kalimantan"). Menempelkan jenis di depannya menghasilkan
    # "Sungai Sungai Kahayan".
    if nama and nama.lower().startswith(jenis.split()[0].lower()):
        dasar = nama
    elif nama:
        dasar = f"{jenis} {nama}"
    else:
        dasar = jenis
    arah = cuaca_client.arah_mata_angin(fitur.get("arah_deg"))
    return f"{dasar} {fitur['jarak_km']} km arah {arah}" if arah else f"{dasar} {fitur['jarak_km']} km"


def susun_brief(
    lat: float,
    lon: float,
    blok: dict[str, Any],
    alert: Optional[AlertPrediction],
    diambil: datetime,
) -> str:
    """Rakit teks siap tempel ke grup siaga bencana.

    Perakitannya deterministik: tiap baris berasal dari satu field di `blok`.
    Tidak ada model bahasa yang terlibat — kalau suatu saat lapisan penuturan
    LLM ditambahkan, ia menerima objek ini sebagai masukan dan teks di bawah
    tetap jadi jalur utama saat LLM tidak tersedia (Bagian 6 butir 4).
    """
    ns = "S" if lat < 0 else "N"
    ew = "W" if lon < 0 else "E"
    baris = [
        "SIZE-UP — DRAF, WAJIB DIVERIFIKASI TIM SIZE-UP",
        f"Disusun {diambil.astimezone(WIB):%d %b %Y %H:%M} WIB",
        f"Titik: {abs(lat):.4f}°{ns} {abs(lon):.4f}°{ew}",
    ]
    if alert is not None:
        baris.append(f"ID alert: {alert.alert_id}")
    baris += _baris_deteksi(alert)
    baris.append("")

    cuaca = blok.get("cuaca") or {}
    if cuaca.get("status") == "ada":
        potongan = []
        if cuaca.get("suhu_c") is not None:
            potongan.append(f"{cuaca['suhu_c']} °C")
        if cuaca.get("kelembapan_persen") is not None:
            potongan.append(f"RH {cuaca['kelembapan_persen']}%")
        if cuaca.get("angin_kmj") is not None:
            arah = cuaca.get("arah_angin_mata")
            potongan.append(
                f"angin {cuaca['angin_kmj']} km/j" + (f" dari {arah}" if arah else "")
            )
        baris.append(f"Cuaca ({cuaca.get('sumber', '—')}): " + " · ".join(potongan))

        riwayat = cuaca.get("riwayat_hujan") or {}
        if riwayat.get("hari_kering_berturut") is not None:
            # "≥" bukan hiasan: kalau seluruh jendela kering, hitungan
            # sebenarnya bisa lebih panjang dan kami tidak melihatnya.
            awalan = "≥" if riwayat.get("terpotong_jendela") else ""
            baris.append(
                f"Kekeringan: {awalan}{riwayat['hari_kering_berturut']} hari berturut "
                f"tanpa hujan (ambang {riwayat['ambang_hari_kering_mm']} mm/hari) · "
                f"hujan 24 jam {riwayat.get('hujan_24jam_mm')} mm"
            )
        if cuaca.get("arah_rambatan_mata"):
            baris.append(
                f"Proyeksi arah angin: dorongan ke {cuaca['arah_rambatan_mata']}. "
                "Bukan prediksi rambatan model."
            )
    else:
        baris.append("Cuaca: tidak bisa diambil saat brief ini disusun.")

    bahaya = blok.get("bahaya") or {}
    if bahaya.get("status") == "ada":
        k = bahaya["komponen"]
        baris.append(
            f"Indeks bahaya kebakaran (FWI, Sistem Kanada): {bahaya['fwi']} — "
            f"{bahaya['nama']} ({bahaya['ambang']})"
        )
        baris.append(
            f"  Komponen: FFMC {k['ffmc']} · DMC {k['dmc']} · DC {k['dc']} · "
            f"ISI {k['isi']} · BUI {k['bui']}"
        )
        baris.append(
            "  Dihitung sendiri dari persamaan terbit atas data Open-Meteo. "
            "Sistem yang sama diadopsi SPBK BMKG, tapi ini bukan keluaran BMKG."
        )

    resmi = blok.get("bmkg") or {}
    if resmi.get("status") == "ada":
        wilayah_teks = " / ".join(
            x for x in (resmi.get("desa"), resmi.get("kecamatan"), resmi.get("kotkab")) if x
        )
        jarak_teks = (
            f", {resmi['jarak_titik_acuan_km']} km dari titik"
            if resmi.get("jarak_titik_acuan_km") is not None
            else ""
        )
        baris.append(
            f"Prakiraan resmi BMKG ({wilayah_teks}{jarak_teks}): "
            f"{resmi.get('cuaca')} · {resmi.get('suhu_c')} °C · "
            f"RH {resmi.get('kelembapan_persen')}% · angin {resmi.get('angin_kmj')} km/j "
            f"— berlaku {resmi.get('waktu_prakiraan')}"
        )

    lahan = blok.get("penutup_lahan") or {}
    if lahan.get("status") == "ada":
        baris.append(
            f"Penutup lahan (BIG {lahan.get('skala')}): {lahan.get('nama')}"
            + (
                " — kelas ini mengindikasikan lahan basah; status kesatuan "
                "hidrologis gambut TIDAK ditentukan oleh peta ini"
                if lahan.get("indikasi_lahan_basah")
                else ""
            )
        )

    baris.append("")
    air = blok.get("sumber_air") or {}
    if air.get("status") == "ada" and air.get("daftar"):
        baris.append("Sumber air terdekat: " + "; ".join(_sebut_fitur(f) for f in air["daftar"][:3]))
    elif air.get("status") == "ada":
        baris.append(f"Sumber air: tidak terpetakan dalam radius {air.get('radius_km')} km.")
    else:
        baris.append("Sumber air: data OpenStreetMap tidak bisa diambil.")

    akses = blok.get("akses") or {}
    if akses.get("status") == "ada" and akses.get("daftar"):
        baris.append("Akses terdekat: " + "; ".join(_sebut_fitur(f) for f in akses["daftar"][:3]))
    elif akses.get("status") == "ada":
        baris.append(f"Akses: tidak terpetakan dalam radius {akses.get('radius_km')} km.")
    else:
        baris.append("Akses: data OpenStreetMap tidak bisa diambil.")

    alat = blok.get("peralatan") or {}
    if alat.get("status") == "ada":
        baris.append(f"Saran tingkat peralatan: {alat['nama']} ({alat['contoh']})")
        baris.append("  Dasar: " + "; ".join(alat["alasan"]))

    baris += ["", CATATAN_PROVENANS, CATATAN_BRIEF]
    return "\n".join(baris)


# --------------------------------------------------------------------------- #
# Perakitan                                                                    #
# --------------------------------------------------------------------------- #


def rakit(lat: float, lon: float, alert_id: str | None = None) -> dict[str, Any]:
    """Satu objek size-up lengkap untuk satu koordinat.

    Tidak pernah melempar karena sumber eksternal gagal: kegagalan dilaporkan
    per blok supaya kartu tetap berguna sebagian. Yang tidak pernah terjadi
    adalah blok gagal yang diisi angka tebakan.
    """
    diambil = datetime.now(WIB)
    alert = model_client.ambil_satu_alert(alert_id) if alert_id else None

    blok: dict[str, Any] = {}

    try:
        cuaca = cuaca_client.ambil_cuaca(lat, lon)
        blok["cuaca"] = {"status": "ada", "catatan_kerucut": CATATAN_KERUCUT, **cuaca}
    except cuaca_client.CuacaUnavailable as galat:
        blok["cuaca"] = _blok_gagal(
            galat.alasan,
            "Data cuaca tidak bisa dimuat. Coba lagi dalam beberapa menit, atau "
            "lanjutkan size-up tanpa blok ini.",
        )

    # FWI ditarik TERPISAH dari cuaca saat ini, bukan diturunkan darinya: ia
    # butuh deret 60 hari nilai tengah hari, panggilan yang berbeda dan jauh
    # lebih besar. Memasangkannya ke blok cuaca akan membuat kegagalan salah
    # satunya menjatuhkan yang lain tanpa alasan.
    try:
        deret = cuaca_client.ambil_deret_tengah_hari(lat, lon, fwi.HARI_SPINUP)
        hasil = fwi.hitung_deret(deret)
        blok["bahaya"] = hasil or _blok_gagal(
            "deret_kosong", "Deret cuaca tengah hari tidak cukup untuk menghitung FWI."
        )
    except cuaca_client.CuacaUnavailable as galat:
        blok["bahaya"] = _blok_gagal(
            galat.alasan,
            "Indeks bahaya kebakaran tidak bisa dihitung — riwayat cuaca 60 hari "
            "tidak bisa diambil.",
        )

    # Wilayah administratif (BIG) → kode desa → prakiraan resmi (BMKG).
    # Rantai ini sengaja berurutan: tanpa kode desa dari BIG, BMKG tidak bisa
    # ditanyai sama sekali karena ia tidak menerima lintang/bujur.
    wilayah = None
    try:
        wilayah = big_client.ambil_wilayah(lat, lon)
        blok["wilayah"] = {"status": "ada", **wilayah}
    except big_client.BigUnavailable as galat:
        blok["wilayah"] = _blok_gagal(
            galat.alasan,
            "Wilayah administratif tidak bisa diambil dari geoportal BIG.",
        )

    if wilayah and wilayah.get("kode_desa"):
        try:
            resmi = bmkg_client.ambil_prakiraan(wilayah["kode_desa"], diambil)
            jarak = (
                osm_client.jarak_km(lat, lon, resmi["lat"], resmi["lon"])
                if isinstance(resmi.get("lat"), (int, float))
                and isinstance(resmi.get("lon"), (int, float))
                else None
            )
            blok["bmkg"] = {
                "status": "ada",
                # Jarak titik acuan WAJIB ikut: prakiraan BMKG berlaku untuk desa,
                # bukan untuk titik alert. Tanpa angka ini, dua tempat berbeda
                # akan terbaca sebagai satu.
                "jarak_titik_acuan_km": round(jarak, 2) if jarak is not None else None,
                **resmi,
            }
        except bmkg_client.BmkgUnavailable as galat:
            blok["bmkg"] = _blok_gagal(
                galat.alasan,
                "Prakiraan resmi BMKG tidak bisa dimuat. Angka cuaca di atas tetap "
                "berlaku — sumbernya Open-Meteo, bukan BMKG.",
            )
    else:
        blok["bmkg"] = _blok_gagal(
            "kode_desa_tidak_ada",
            "Prakiraan BMKG butuh kode wilayah desa, yang belum bisa ditentukan "
            "dari koordinat ini.",
        )

    try:
        blok["penutup_lahan"] = {"status": "ada", **big_client.ambil_penutup_lahan(lat, lon)}
    except big_client.BigUnavailable as galat:
        blok["penutup_lahan"] = _blok_gagal(
            galat.alasan, "Penutup lahan tidak bisa diambil dari geoportal BIG."
        )

    try:
        geo = osm_client.ambil_geografi(lat, lon)
        umum = {
            "status": "ada",
            "sumber": geo["sumber"],
            "sumber_url": geo["sumber_url"],
            "radius_km": geo["radius_km"],
        }
        blok["sumber_air"] = {**umum, "daftar": geo["air"]}
        blok["akses"] = {**umum, "daftar": geo["akses"]}
        blok["peralatan"] = sarankan_peralatan(geo["air"], geo["akses"])
    except osm_client.OsmUnavailable as galat:
        pesan = (
            "Peta sumber air dan akses tidak bisa dimuat. Coba lagi dalam beberapa "
            "menit, atau lanjutkan dengan peta cetak posko."
        )
        blok["sumber_air"] = _blok_gagal(galat.alasan, pesan)
        blok["akses"] = _blok_gagal(galat.alasan, pesan)
        blok["peralatan"] = _blok_gagal(
            "geografi_tidak_ada",
            "Saran peralatan butuh jarak sumber air dan akses yang belum tersedia.",
        )

    return {
        "koordinat": {"lat": lat, "lon": lon},
        "alert_id": alert.alert_id if alert else None,
        "diambil": diambil.isoformat(),
        "is_cuplikan": False,
        "blok": blok,
        "brief": susun_brief(lat, lon, blok, alert, diambil),
        "catatan_provenans": CATATAN_PROVENANS,
        "catatan_brief": CATATAN_BRIEF,
    }
