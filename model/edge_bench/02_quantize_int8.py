"""
edge_bench/02_quantize_int8.py — Stage 8c

Kuantisasi model ONNX (hasil 01_export_onnx.py) ke INT8, lalu laporkan
TIGA hal sekaligus — ukuran, latensi, DAN delta akurasi
(bukan cuma ukuran).

============================================================================
STATUS: bagian ukuran & latensi FULL JALAN sekarang. Bagian delta akurasi
DI-SKIP OTOMATIS kalau dependency-nya belum ada (lihat --eval-manifest,
--metrics-module di bawah) — TIDAK dipaksa jalan pakai rumus tebakan,
karena aturannya eksplisit: fungsi metrik wajib diambil dari
`model/src/metrics.py` -- jangan hitung ulang dengan formula sendiri.
============================================================================

Cara pakai (minimal, size+latency saja):
    python edge_bench/02_quantize_int8.py \
        --onnx-path edge_bench/reports/fusion_v1.onnx \
        --out edge_bench/reports/latency_quantized.csv

Cara pakai (lengkap, dengan delta akurasi — setelah dependency tim model ada):
    python edge_bench/02_quantize_int8.py \
        --onnx-path edge_bench/reports/fusion_v1.onnx \
        --model-src src \
        --eval-manifest manifests/flame2_val.csv \
        --out edge_bench/reports/latency_quantized.csv
"""
import argparse
import csv
import os
import statistics
import sys
import time

import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="Stage 8c — kuantisasi INT8 + ukuran + latensi + delta akurasi")
    p.add_argument("--onnx-path", required=True, help="Path ke model .onnx hasil 01_export_onnx.py")
    p.add_argument("--quantized-out", default=None,
                    help="Path output model .onnx terkuantisasi (default: <onnx-path> dengan suffix _int8)")
    p.add_argument("--out", default="edge_bench/reports/latency_quantized.csv")
    p.add_argument("--rgb-size", type=int, nargs=2, default=[224, 224], metavar=("H", "W"))
    p.add_argument("--thermal-size", type=int, nargs=2, default=[224, 224], metavar=("H", "W"))
    p.add_argument("--n-tiles", type=int, default=1)
    p.add_argument("--n-warmup", type=int, default=10)
    p.add_argument("--n-runs", type=int, default=100)

    # --- untuk delta akurasi (opsional, di-skip otomatis kalau kosong) ---
    p.add_argument("--model-src", default=None,
                    help="Path ke folder src/ tim model (buat import metrics.py & data/dataset_flame2.py). "
                         "Kosongkan kalau belum ada -- delta akurasi otomatis di-skip.")
    p.add_argument("--flame2-labels", default=None,
                    help="Path ke 'Frame Pair Labels.txt' asli FLAME2 (biasanya satu paket dengan "
                         "item #9 yang didownload dari IEEE Dataport)")
    p.add_argument("--flame2-manifest", default=None,
                    help="Path ke manifests/flame2_train.csv (hasil Stage 0 kamu)")
    p.add_argument("--flame2-dataset-root", default=None,
                    help="Folder yang LANGSUNG berisi '254p RGB Images/' dan '254p Thermal Images/' "
                         "(biasanya data_prep/raw/flame2)")
    p.add_argument("--flame2-excluded-csv", default=None,
                    help="Path ke manifests/flame2_excluded_leakage.csv (hasil Stage 0 kamu)")
    p.add_argument("--val-fraction", type=float, default=0.1,
                    help="Harus SAMA dengan yang dipakai tim model training (default fungsi: 0.1)")
    p.add_argument("--split-seed", type=int, default=42,
                    help="Harus SAMA dengan yang dipakai tim model training (default fungsi: 42) -- "
                         "kalau beda, split val yang dipakai evaluasi ini BEDA dari yang menghasilkan "
                         "val_acc di metadata checkpoint, hasil jadi tidak apple-to-apple")
    p.add_argument("--eval-max-samples", type=int, default=200,
                    help="Batasi jumlah sampel val yang dievaluasi (biar tidak terlalu lama). "
                         "None/0 = pakai semua sampel val.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Kuantisasi
# ---------------------------------------------------------------------------
def quantize_onnx_dynamic(onnx_path, quantized_out):
    """Dynamic quantization (weight-only INT8) via onnxruntime.quantization.
    Dipilih (bukan static quantization) karena TIDAK butuh calibration
    dataset tambahan -- cukup dari model .onnx yang sudah ada. Static
    quantization biasanya sedikit lebih akurat tapi butuh data kalibrasi
    representatif (batch sampel asli) yang belum kita punya di tahap ini.
    """
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        print("[ERROR] onnxruntime.quantization tidak tersedia. Install/upgrade:")
        print("        pip install onnxruntime")
        sys.exit(1)

    os.makedirs(os.path.dirname(quantized_out) or ".", exist_ok=True)
    print(f"[INFO] Kuantisasi dinamis INT8: {onnx_path} -> {quantized_out}")
    quantize_dynamic(
        model_input=onnx_path,
        model_output=quantized_out,
        weight_type=QuantType.QInt8,
    )
    print(f"[DONE] Model terkuantisasi disimpan: {quantized_out}")


# ---------------------------------------------------------------------------
# Latensi (pola sama seperti 01_export_onnx.py, supaya angka apple-to-apple)
# ---------------------------------------------------------------------------
def measure_latency_onnxruntime(onnx_path, dummy_inputs_np, input_names, n_warmup, n_runs):
    import onnxruntime as ort

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_feed = {name: arr for name, arr in zip(input_names, dummy_inputs_np)}

    print(f"[INFO] Warm-up {n_warmup}x (tidak dihitung)...")
    for _ in range(n_warmup):
        session.run(None, input_feed)

    print(f"[INFO] Mengukur latensi {n_runs}x...")
    latencies_ms = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        session.run(None, input_feed)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000)

    return {
        "median_ms": statistics.median(latencies_ms),
        "mean_ms": statistics.mean(latencies_ms),
        "stdev_ms": statistics.stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0,
        "p95_ms": sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1],
    }


# ---------------------------------------------------------------------------
# Delta akurasi — WAJIB pakai metrics.py tim model, di-skip kalau belum ada
# ---------------------------------------------------------------------------
def try_load_accuracy_dependencies(model_src):
    """Coba import metrics.py & dataset_flame2.py dari tim model. Return
    (metrics_module, dataset_module) atau (None, None) kalau tidak ketemu
    -- TIDAK raise error, karena delta akurasi memang opsional di tahap ini.
    """
    if model_src is None:
        return None, None

    model_src = os.path.abspath(model_src)
    sys.path.insert(0, model_src)

    metrics_module = None
    dataset_module = None
    try:
        import metrics as metrics_module  # confirmed: src/metrics.py
        print(f"[INFO] metrics.py ditemukan & di-import dari: {model_src}")
    except ImportError:
        print(f"[WARN] Tidak bisa import metrics.py dari {model_src} -- "
              f"delta akurasi akan DI-SKIP (bukan dihitung pakai formula sendiri).")

    try:
        import data.dataset_flame2 as dataset_module  # confirmed: src/data/dataset_flame2.py
        print(f"[INFO] dataset_flame2.py ditemukan & di-import.")
    except ImportError:
        try:
            import dataset_flame2 as dataset_module  # fallback kalau tidak di subfolder data/
            print(f"[INFO] dataset_flame2.py ditemukan & di-import (tanpa subfolder data/).")
        except ImportError:
            print(f"[WARN] Tidak bisa import dataset_flame2.py -- delta akurasi akan DI-SKIP.")

    return metrics_module, dataset_module


def load_eval_manifest(eval_manifest_path, n_samples=None):
    """(Sudah tidak dipakai — digantikan build_flame2_datasets() resmi tim model,
    lihat compute_accuracy(). Dibiarkan di sini kalau-kalau butuh fallback CSV
    generik di masa depan.)"""
    import csv as _csv
    rows = []
    with open(eval_manifest_path, newline="") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            rows.append(row)
    if n_samples is not None:
        rows = rows[:n_samples]
    return rows


def build_val_dataset(dataset_module, args):
    """Bangun val dataset PAKAI FUNGSI RESMI tim model (build_flame2_datasets),
    bukan reimplementasi manual — supaya preprocessing, split train/val
    (per-scene, bukan per-frame), dan filter leakage semuanya identik
    dengan yang dipakai saat training menghasilkan val_acc di checkpoint.

    ⚠️ CATATAN: video_frame_ranges pakai DEFAULT_VIDEO_FRAME_RANGES dari
    dataset_flame2.py, yang di docstring aslinya ditandai TODO-VERIFIKASI
    ("BUKAN angka asli", masih proporsional/placeholder). Artinya split
    val yang dipakai evaluasi ini BISA BERUBAH begitu tim model verifikasi
    rentang video asli dari README FLAME2 -- anggap delta akurasi dari
    script ini PROVISIONAL, bukan angka final buat paper, sampai itu
    dikonfirmasi.
    """
    from pathlib import Path

    missing = [name for name, val in [
        ("--flame2-labels", args.flame2_labels),
        ("--flame2-manifest", args.flame2_manifest),
        ("--flame2-dataset-root", args.flame2_dataset_root),
        ("--flame2-excluded-csv", args.flame2_excluded_csv),
    ] if val is None]
    if missing:
        print(f"[SKIP] Argumen belum lengkap buat bangun val dataset: {missing}")
        return None

    print("[WARN] video_frame_ranges masih pakai DEFAULT_VIDEO_FRAME_RANGES "
          "(placeholder, ditandai TODO-VERIFIKASI di dataset_flame2.py) -- "
          "delta akurasi dari run ini PROVISIONAL, jangan dipakai sebagai angka "
          "final paper sampai tim model konfirmasi rentang video asli.")

    _, val_set = dataset_module.build_flame2_datasets(
        labels_path=Path(args.flame2_labels),
        manifest_path=Path(args.flame2_manifest),
        dataset_root=Path(args.flame2_dataset_root),
        excluded_csv_path=Path(args.flame2_excluded_csv),
        video_frame_ranges=dataset_module.DEFAULT_VIDEO_FRAME_RANGES,
        val_fraction=args.val_fraction,
        seed=args.split_seed,
        image_size=args.rgb_size[0],
    )
    print(f"[INFO] Val dataset dibangun: {len(val_set)} sampel total.")
    return val_set


def compute_accuracy(session, input_names, val_set, metrics_module, max_samples=None):
    """Jalankan inferensi ONNX Runtime di val_set resmi (FLAME2ClassificationDataset,
    train=False -> preprocessing tanpa augmentasi random), hitung:
      - accuracy sederhana (correct/total) -- formula universal, TIDAK ada di
        metrics.py (yang cuma expose precision/recall/F1), jadi ini dihitung
        langsung di sini, BUKAN "menulis ulang metrik resmi" karena tidak ada
        definisi yang berbeda-beda buat accuracy.
      - macro precision/recall/F1 -- WAJIB via metrics.classification_precision_recall_f1()
        (implementasi resmi).
    """
    n = len(val_set) if not max_samples else min(max_samples, len(val_set))
    print(f"[INFO] Evaluasi {n} dari {len(val_set)} sampel val...")

    y_true, y_pred = [], []
    for i in range(n):
        rgb_t, thermal_t, target = val_set[i]
        rgb_np = rgb_t.unsqueeze(0).numpy().astype(np.float32)
        thermal_np = thermal_t.unsqueeze(0).numpy().astype(np.float32)
        input_feed = {input_names[0]: rgb_np, input_names[1]: thermal_np}
        logits = session.run(None, input_feed)[0]  # (1, n_classes)
        pred_idx = int(np.argmax(logits, axis=-1)[0])
        y_true.append(int(target.item()))
        y_pred.append(pred_idx)
        if (i + 1) % 50 == 0:
            print(f"         ... {i + 1}/{n}")

    accuracy = float(np.mean(np.array(y_true) == np.array(y_pred)))
    pr = metrics_module.classification_precision_recall_f1(y_true, y_pred)

    return {
        "accuracy": accuracy,
        "macro_precision": pr["macro"]["precision"],
        "macro_recall": pr["macro"]["recall"],
        "macro_f1": pr["macro"]["f1"],
        "n_samples": n,
    }


# ---------------------------------------------------------------------------
def main():
    args = parse_args()

    if not os.path.isfile(args.onnx_path):
        print(f"[ERROR] File ONNX tidak ditemukan: {args.onnx_path}")
        print("        Jalankan 01_export_onnx.py dulu buat menghasilkan file ini.")
        sys.exit(1)

    quantized_out = args.quantized_out
    if quantized_out is None:
        base, ext = os.path.splitext(args.onnx_path)
        quantized_out = f"{base}_int8{ext}"

    # --- Stage 8c bagian 1: kuantisasi ---
    quantize_onnx_dynamic(args.onnx_path, quantized_out)

    # --- Stage 8c bagian 2: ukuran file (selalu bisa dihitung) ---
    size_before_mb = os.path.getsize(args.onnx_path) / (1024 * 1024)
    size_after_mb = os.path.getsize(quantized_out) / (1024 * 1024)
    size_reduction_pct = (1 - size_after_mb / size_before_mb) * 100 if size_before_mb > 0 else 0.0
    print(f"[INFO] Ukuran sebelum: {size_before_mb:.2f} MB")
    print(f"[INFO] Ukuran sesudah: {size_after_mb:.2f} MB  (-{size_reduction_pct:.1f}%)")

    # --- Stage 8c bagian 3: latensi FP32 vs INT8 (selalu bisa dihitung) ---
    input_names = ["rgb_img", "thermal_img"]  # harus sama dengan 01_export_onnx.py
    h_rgb, w_rgb = args.rgb_size
    h_th, w_th = args.thermal_size
    dummy_inputs_np = [
        np.random.randn(1, 3, h_rgb, w_rgb).astype(np.float32),
        np.random.randn(1, 1, h_th, w_th).astype(np.float32),
    ]

    print("\n[INFO] === Latensi model FP32 (sebelum kuantisasi) ===")
    stats_fp32 = measure_latency_onnxruntime(args.onnx_path, dummy_inputs_np, input_names,
                                              args.n_warmup, args.n_runs)
    print(f"[RESULT FP32] median={stats_fp32['median_ms']:.2f}ms mean={stats_fp32['mean_ms']:.2f}ms "
          f"stdev={stats_fp32['stdev_ms']:.2f}ms p95={stats_fp32['p95_ms']:.2f}ms")

    print("\n[INFO] === Latensi model INT8 (sesudah kuantisasi) ===")
    stats_int8 = measure_latency_onnxruntime(quantized_out, dummy_inputs_np, input_names,
                                              args.n_warmup, args.n_runs)
    print(f"[RESULT INT8] median={stats_int8['median_ms']:.2f}ms mean={stats_int8['mean_ms']:.2f}ms "
          f"stdev={stats_int8['stdev_ms']:.2f}ms p95={stats_int8['p95_ms']:.2f}ms")

    speedup = stats_fp32["median_ms"] / stats_int8["median_ms"] if stats_int8["median_ms"] > 0 else float("nan")
    print(f"\n[INFO] Speedup median (FP32/INT8): {speedup:.2f}x")

    if args.n_tiles > 1:
        print(f"[INFO] n_tiles={args.n_tiles} -> kalikan median_ms manual buat estimasi per-frame "
              f"(sekuensial). FP32: {stats_fp32['median_ms']*args.n_tiles:.2f}ms, "
              f"INT8: {stats_int8['median_ms']*args.n_tiles:.2f}ms")

    # --- Stage 8c bagian 4: delta akurasi (opsional, wajib pakai metrics.py tim model) ---
    delta_acc_str = "N/A (belum diukur)"
    result_fp32, result_int8 = None, None

    if args.model_src is None:
        print("\n[SKIP] Delta akurasi TIDAK dihitung -- --model-src belum diisi. "
              "Ini BUKAN error, tapi WAJIB diisi sebelum laporan Stage 8c final "
              "(laporkan ukuran/latensi/delta akurasi tiga-tiganya).")
    else:
        metrics_module, dataset_module = try_load_accuracy_dependencies(args.model_src)
        if metrics_module is None or dataset_module is None:
            print("\n[SKIP] Delta akurasi TIDAK dihitung -- metrics.py atau "
                  "data/dataset_flame2.py belum ketemu/belum bisa di-import di --model-src.")
        else:
            val_set = build_val_dataset(dataset_module, args)
            if val_set is None:
                print("\n[SKIP] Delta akurasi TIDAK dihitung -- argumen --flame2-* belum lengkap "
                      "(lihat pesan [SKIP] di atas untuk daftar yang masih kosong).")
            else:
                import onnxruntime as ort
                sess_fp32 = ort.InferenceSession(args.onnx_path, providers=["CPUExecutionProvider"])
                sess_int8 = ort.InferenceSession(quantized_out, providers=["CPUExecutionProvider"])

                max_samples = args.eval_max_samples if args.eval_max_samples else None
                print("\n[INFO] === Evaluasi akurasi model FP32 ===")
                result_fp32 = compute_accuracy(sess_fp32, input_names, val_set, metrics_module, max_samples)
                print("\n[INFO] === Evaluasi akurasi model INT8 ===")
                result_int8 = compute_accuracy(sess_int8, input_names, val_set, metrics_module, max_samples)

                delta_acc = result_int8["accuracy"] - result_fp32["accuracy"]
                delta_f1 = result_int8["macro_f1"] - result_fp32["macro_f1"]
                delta_acc_str = f"{delta_acc:+.4f}"
                print(f"\n[RESULT] Accuracy   FP32={result_fp32['accuracy']:.4f}  "
                      f"INT8={result_int8['accuracy']:.4f}  Delta={delta_acc_str}  "
                      f"(n={result_fp32['n_samples']} sampel)")
                print(f"[RESULT] Macro-F1    FP32={result_fp32['macro_f1']:.4f}  "
                      f"INT8={result_int8['macro_f1']:.4f}  Delta={delta_f1:+.4f}  "
                      f"(dari metrics.py resmi tim model)")

    # --- Simpan hasil ---
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_header = not os.path.isfile(args.out)
    with open(args.out, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "onnx_path", "quantized_path", "size_before_mb", "size_after_mb",
                "size_reduction_pct", "median_ms_fp32", "median_ms_int8", "speedup",
                "acc_fp32", "acc_int8", "delta_accuracy",
                "macro_f1_fp32", "macro_f1_int8", "delta_macro_f1",
                "n_eval_samples", "n_tiles",
            ])
        writer.writerow([
            args.onnx_path, quantized_out, f"{size_before_mb:.2f}", f"{size_after_mb:.2f}",
            f"{size_reduction_pct:.1f}", f"{stats_fp32['median_ms']:.3f}",
            f"{stats_int8['median_ms']:.3f}", f"{speedup:.3f}",
            f"{result_fp32['accuracy']:.4f}" if result_fp32 else "N/A",
            f"{result_int8['accuracy']:.4f}" if result_int8 else "N/A",
            delta_acc_str,
            f"{result_fp32['macro_f1']:.4f}" if result_fp32 else "N/A",
            f"{result_int8['macro_f1']:.4f}" if result_int8 else "N/A",
            f"{(result_int8['macro_f1'] - result_fp32['macro_f1']):+.4f}" if result_fp32 and result_int8 else "N/A",
            result_fp32["n_samples"] if result_fp32 else "N/A",
            args.n_tiles,
        ])
    print(f"\n[DONE] Hasil ditambahkan ke: {args.out}")

    if result_fp32 is None:
        print("\n" + "=" * 70)
        print("[REMINDER] Delta akurasi BELUM lengkap. Laporan Stage 8c")
        print("wajib memuat tiga-tiganya (ukuran + latensi + delta akurasi), bukan cuma dua.")
        print("Lihat pesan chat buat daftar lengkap yang masih dibutuhkan.")
        print("=" * 70)
    else:
        print("\n[REMINDER] video_frame_ranges masih placeholder (TODO-VERIFIKASI) -- "
              "angka delta akurasi di atas PROVISIONAL, jangan pakai sebagai angka final "
              "paper sampai tim model konfirmasi rentang video asli dari README FLAME2.")


if __name__ == "__main__":
    main()
