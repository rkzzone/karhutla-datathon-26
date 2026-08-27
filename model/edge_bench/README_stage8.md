# Stage 8 — Edge Benchmark

## Status arsitektur: COMPOSE, BELUM DIKONFIRMASI 100%

`00_params_flops.py` sekarang punya class `FusionModel` yang menggabungkan
7 modul dari `src/models/` (encoder_rgb, encoder_thermal,
fusion_cross_attention, modality_dropout, reliability_gate,
head_classification, head_segmentation). Tapi **ini hasil compose saya**,
bukan file asli dari tim model — belum ada file top-level (`model.py` atau
class di `train.py`) yang dikirim untuk konfirmasi nama atribut persis.

**Cara ini aman dipakai** karena `load_checkpoint()` load dengan
`strict=False` secara default — kalau nama atribut di `FusionModel` beda
dari yang dipakai tim model pas training, script akan print daftar
`missing_keys` / `unexpected_keys` biar kamu bisa cocokkan nama atribut di
`FusionModel.__init__()` (di `00_params_flops.py`) sampai keduanya kosong.
**Jangan lanjut ke FLOPs/ONNX kalau masih ada key mismatch** — params yang
dihitung dari model yang gagal load sebagian akan salah.

Kalau mau maksa error keras (bukan cuma warning) saat ada mismatch, pakai
flag `--strict-load`.

## Yang masih perlu dikonfirmasi ke tim model

1. **fusion_v1.pth pakai reliability gate atau belum?** Default script:
   TIDAK (karena gate itu fitur Stage 5, sementara fusion_v1 dari Stage 2).
   Kalau checkpoint yang kamu benchmark sudah dari Stage 5+
   (`fusion_v2_gated.pth`), tambahkan flag `--use-reliability-gate`.
2. **Head mana yang aktif** — default `classification`. Kalau mau
   benchmark jalur segmentasi (Stage 6, Jalur B), pakai `--head segmentation`.
   Ingat: segmentation head biasanya dilatih **di atas encoder beku**
   terpisah dari classification head — kemungkinan besar itu checkpoint
   yang berbeda, bukan satu file gabungan otomatis.
3. Kalau setelah dicocokkan masih ada `unexpected_keys` yang tidak masuk
   akal (misal ada prefix aneh kayak `module.` dari `DataParallel`), itu
   tanda lain lagi — tanya ke saya, jangan asal strip prefix tanpa yakin.

## Sebelum jalankan

- **Path folder sumber model diisi eksplisit** lewat `--model-src`. Isi
  dengan path ke folder `src/` yang di dalamnya ada subfolder `models/`
  berisi `encoder_rgb.py` dkk. Seluruh contoh di bawah dijalankan dari
  `model/`, sehingga path-nya cukup `src`.
- **Bobot model tidak ada di repositori ini** (lihat README akar) — unduh
  lebih dulu dari Hugging Face, lalu tunjuk `--checkpoint` ke berkas itu.
- **RGBEncoder butuh internet** di run pertama — dia download bobot
  DINOv2 lewat `torch.hub.load(...)`, lalu di-cache lokal.

## Urutan pakai

```bash
# Stage 8a — params, FLOPs, ukuran file
python edge_bench/00_params_flops.py \
    --checkpoint weights/fusion_v1.pth \
    --model-src src \
    --rgb-size 224 224 --thermal-size 224 224

# Cek output: [OK] load_state_dict: SEMUA KEY COCOK -- baru lanjut.
# Kalau masih [WARN] missing/unexpected keys, perbaiki dulu nama atribut
# di class FusionModel (00_params_flops.py) sebelum lanjut ke bawah.

# Stage 8b — export ONNX + latensi CPU (median >=100 run setelah warmup)
python edge_bench/01_export_onnx.py \
    --checkpoint weights/fusion_v1.pth \
    --model-src src \
    --rgb-size 224 224 --thermal-size 224 224 \
    --n-warmup 10 --n-runs 100
```

Sesuaikan `--checkpoint` dan `--model-src` dengan path sebenarnya di
mesinmu — relatif terhadap direktori tempat perintah dijalankan, atau
absolut kalau lebih mudah.

Dependency tambahan yang mungkin perlu diinstall:
```bash
pip install thop onnx onnxruntime --break-system-packages
```

## Kalau `n_tiles > 1`

Kedua script menerima `--n-tiles`. Angka latensi/FLOPs yang di-print itu
**per tile**, script akan kasih estimasi per-frame (dikali n_tiles) tapi
ini asumsi tile diproses **sekuensial** — kalau implementasi tim model
memproses tile secara batched/paralel, angka estimasi ini overestimate.
Sesuaikan cara hitungnya begitu tahu implementasi sebenarnya, sebelum
dipakai di laporan/paper (Bagian 9 brief: "anggaran latensi per-frame yang
sebenarnya, bukan cuma per-tile").

## Setelah ini

Stage 8c (`02_quantize_int8.py`) — kuantisasi INT8, ukuran + latensi sudah
bisa dihitung penuh sekarang. Delta akurasi butuh `metrics.py` +
`dataset_flame2.py` dari tim model, plus manifest evaluasi berlabel — lihat
bagian "Stage 8c" di bawah untuk daftar lengkap yang masih dibutuhkan.

```bash
python edge_bench/02_quantize_int8.py \
    --onnx-path edge_bench/reports/fusion_model.onnx \
    --out edge_bench/reports/latency_quantized.csv
```

## Stage 8c — status delta akurasi: SIAP DIPAKAI (dengan 1 catatan penting)

`metrics.py` dan `data/dataset_flame2.py` sudah dikonfirmasi ada di
`model/src/`. Script sekarang pakai `build_flame2_datasets()`
**resmi** dari `dataset_flame2.py` buat bangun val split (bukan CSV
generik reka-reka) — preprocessing, split per-scene, dan filter leakage
semuanya otomatis identik dengan training.

**⚠️ Catatan penting**: split val pakai `DEFAULT_VIDEO_FRAME_RANGES` yang
di source code-nya sendiri ditandai `TODO-VERIFIKASI` ("BUKAN angka asli",
masih placeholder proporsional). Artinya **delta akurasi dari script ini
provisional** — sah dipakai buat sanity-check awal, tapi jangan jadi
angka final di paper sampai tim model konfirmasi rentang video asli dari
README FLAME2 item #9/#12. Script akan print warning ini tiap kali
dijalankan supaya tidak lupa.

Argumen yang perlu diisi (4 path + opsional):
```bash
python edge_bench/02_quantize_int8.py \
    --onnx-path edge_bench/reports/fusion_model.onnx \
    --model-src src \
    --flame2-labels ../data_prep/raw/flame2/"Frame Pair Labels.txt" \
    --flame2-manifest ../data_prep/manifests/flame2_train.csv \
    --flame2-dataset-root ../data_prep/raw/flame2 \
    --flame2-excluded-csv ../data_prep/manifests/flame2_excluded_leakage.csv \
    --eval-max-samples 200 \
    --out edge_bench/reports/latency_quantized.csv
```

`--flame2-labels` ("Frame Pair Labels.txt") itu file asli dari paket
FLAME2 item #9 — cek di folder hasil download IEEE Dataport kamu (`raw/flame2/`),
kemungkinan besar sudah ada di situ dari waktu Stage 0.

`--eval-max-samples 200` (default) biar tidak terlalu lama — val set
penuh bisa ribuan sampel. Set `0` kalau mau evaluasi semua.

**Dependency tambahan**: `pip install torchvision pillow` (dipakai
`dataset_flame2.py` buat load & preprocess gambar).

Delta akurasi dilaporkan 2 cara:
- **`accuracy`** (correct/total) — dihitung langsung di script ini (bukan
  dari `metrics.py`, karena `metrics.py` tidak expose fungsi accuracy
  polos, cuma precision/recall/F1 — accuracy sederhana ini formula
  universal tanpa ambiguitas, bukan "menulis ulang metrik resmi")
- **`macro_f1`** — dari `metrics.classification_precision_recall_f1()`
  resmi tim model
