# Estimasi Biaya Penerapan

**Untuk:** paper Bagian 5 (Kelayakan Adopsi) / Lampiran · rubrik 2b
**Disusun:** 23 Agustus 2026
**Aturan:** setiap angka punya sumber. Sel bertanda ⚠️ **belum terverifikasi** dan
tidak boleh masuk paper sebelum dicek langsung ke penjual.

---

## 1. Tabel biaya

| Komponen | Estimasi | Sifat | Sumber |
|---|---|---|---|
| Drone RGB (armada eksisting) | **Rp 0 tambahan** | modal, sudah ada | Lihat catatan §3 |
| Drone RGB + termal, mis. DJI Mavic 3 Enterprise Thermal | **Rp 79.553.000**/unit (sudah termasuk PPN) | modal, opsional | [Galaxy Camera](https://www.galaxy.co.id/products/dji-mavic-3-thermal-3t-kamera-drone-professional-garansi-resmi), mitra resmi DJI, diakses 23 Agustus 2026 |
| Perangkat tepi — NVIDIA Jetson Orin Nano Super Dev Kit | **Rp 9,46 – 12,89 juta**/unit (ritel Indonesia); daftar resmi USD 249 | modal, sekali beli | [Blibli — Rp 10.999.000](https://www.blibli.com/p/nvidia-jetson-orin-nano-official-developer-kit-8gb/ps--WAI-70137-00050), [Tokopedia](https://www.tokopedia.com/find/jetson-orin-nano) |
| Pelatihan model, satu siklus penuh | **Rp 0** | operasional | Seluruh Stage 1–7 dijalankan di Kaggle (T4×2 gratis) — lihat `model/configs/` |
| Inferensi operasional | **Rp 0 marginal** | operasional | Berjalan lokal/on-device; tidak ada API berbayar per-inferensi |
| API hotspot NASA FIRMS | **Rp 0** | operasional | Kuota 5.000 transaksi/10 menit, `docs/integrasi_firms.md` §1 |
| Hosting konsol operator | **Rp 0** pada Vercel free tier yang dipakai sekarang; alternatif VPS **Rp 48 – 156 rb/bulan** | operasional berulang | `docs/status_deployment.md` §1; [DomaiNesia Rp 48.000](https://www.domainesia.com/cloud-vps-lite/), [Rumahweb Rp 50.000](https://www.rumahweb.com/vps-murah/), [Hostinger KVM 2 Rp 155.900](https://www.jagoanhosting.com/harga-vps/) |
| Basemap peta (CARTO) | **Rp 0** free tier | operasional | `docs/status_deployment.md` §6 — butuh jaringan |

## 2. Struktur biaya — ini yang penting, bukan angka absolutnya

1. **Tidak ada biaya per-inferensi.** Model berjalan di perangkat sendiri, bukan
   memanggil API berbayar. Menambah frekuensi patroli tidak menambah biaya
   perangkat lunak sama sekali — hanya jam terbang dan baterai.
2. **Biaya berulang satu-satunya adalah hosting**, di kisaran ratusan ribu rupiah
   per bulan, dan itu pun nol pada tingkat pilot.
3. **Belanja modal bersifat opsional, bukan syarat masuk.** Perangkat tepi dan
   drone bersensor termal meningkatkan kemampuan; keduanya tidak diperlukan
   untuk menjalankan jalur RGB.
4. **Pelatihan tidak menambah biaya.** Arsitektur sengaja diturunkan dari
   anggaran satu GPU kelas menengah, dan seluruh siklus pelatihan proyek ini
   memang berjalan di kuota gratis.

## 3. ⚠️ Catatan yang mengubah argumen adopsi

Argumen "armada instansi mayoritas RGB-saja, sehingga modality dropout
menghapus hambatan adopsi" **tidak didukung** oleh wawancara narasumber
(`docs/notul interview.txt`, 7 Agustus 2026), yang menyatakan drone berkamera
inframerah **sudah banyak dipakai**.

Rumusan yang jujur karenanya bukan "armada yang ada tidak punya termal",
melainkan: **ketahanan modalitas menurunkan syarat perangkat keras minimum dan
menjaga sistem tetap berfungsi ketika sensor termal mati, gagal, atau tidak
terpasang pada sebagian armada** — bukan klaim bahwa termal langka.

## 4. Batasan operasional dari lapangan

Dari wawancara yang sama: daya tahan baterai drone **sekitar 30 menit** tanpa
beban tambahan, dan **lebih singkat** bila drone juga mengirim data. Ini batas
nyata pada cakupan per siklus patroli, dan memperkuat argumen inferensi
on-device: memproses di perangkat dan mengirim hanya alert jauh lebih hemat daya
daripada mengalirkan video mentah.

## 5. Yang belum dihitung

- Biaya operator dan pelatihan personel
- Perawatan, asuransi, dan penggantian baterai drone
- Perizinan penerbangan
- Biaya integrasi ke sistem instansi yang sudah berjalan

Keempatnya di luar jangkauan verifikasi tim dalam jendela kompetisi dan
dinyatakan terbuka, bukan diperkirakan.
