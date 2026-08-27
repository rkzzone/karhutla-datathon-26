"""
edge_bench/01_export_onnx.py — Stage 8b

Export model fusi tim model ke format ONNX, lalu ukur latensi CPU (median
dari >=100 inferensi setelah warm-up).

Jalankan SETELAH 00_params_flops.py sukses (artinya build_model() dan
checkpoint loading sudah benar) — script ini reuse fungsi yang sama supaya
tidak ada dua sumber kebenaran soal cara load model.

============================================================================
TODO WAJIB DIISI (cari "TODO"):
============================================================================
1. Pastikan import build_model()/load_checkpoint() dari 00_params_flops.py
   sudah terisi benar (file ini akan gagal kalau itu belum selesai)
2. Cek urutan & bentuk dummy_inputs cocok dengan forward() model asli
3. Isi input_names/output_names & dynamic_axes sesuai signature model

Cara pakai:
    python edge_bench/01_export_onnx.py \
        --checkpoint weights/fusion_v1.pth \
        --onnx-out edge_bench/reports/fusion_v1.onnx \
        --out edge_bench/reports/latency_cpu.csv \
        --n-runs 100
"""
import argparse
import csv
import os
import statistics
import sys
import time

import torch
import torch.nn.functional as F

# Python tidak bisa "from 00_params_flops import ..." langsung (nama modul
# tidak boleh diawali angka), jadi load manual pakai importlib supaya
# build_model() & load_checkpoint() tetap satu sumber kebenaran dengan
# script 00_params_flops.py (bukan disalin ulang -> berisiko out-of-sync).
import importlib.util

_this_dir = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "params_flops_module", os.path.join(_this_dir, "00_params_flops.py")
)
params_flops_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(params_flops_module)

build_model = params_flops_module.build_model
load_checkpoint = params_flops_module.load_checkpoint


def parse_args():
    p = argparse.ArgumentParser(description="Stage 8b — export ONNX + ukur latensi CPU")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--onnx-out", default="edge_bench/reports/fusion_model.onnx")
    p.add_argument("--out", default="edge_bench/reports/latency_cpu.csv")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                    help="Device untuk load model PyTorch sebelum export "
                         "(latensi tetap diukur di CPU sesuai kebutuhan edge)")
    p.add_argument("--rgb-size", type=int, nargs=2, default=[224, 224], metavar=("H", "W"))
    p.add_argument("--thermal-size", type=int, nargs=2, default=[224, 224], metavar=("H", "W"))
    p.add_argument("--n-tiles", type=int, default=1)
    p.add_argument("--n-classes", type=int, default=3)
    p.add_argument("--head", default="classification", choices=["classification", "segmentation"])
    p.add_argument("--use-reliability-gate", action="store_true",
                    help="Set kalau checkpoint dari Stage 5+ (fusion_v2_gated.pth dst.)")
    p.add_argument("--strict-load", action="store_true")
    p.add_argument("--model-src", default=None,
                    help="Path ke folder src/ milik tim model — sama seperti di 00_params_flops.py")
    p.add_argument("--n-warmup", type=int, default=10,
                    help="Jumlah inferensi warm-up sebelum mulai ukur (dibuang, tidak dihitung)")
    p.add_argument("--n-runs", type=int, default=100,
                    help="Jumlah inferensi untuk hitung median latensi (minimal 100)")
    p.add_argument("--opset", type=int, default=17)
    return p.parse_args()


def _patch_align_token_grid_for_tracing():
    """
    Workaround khusus buat ONNX export — bukan mengubah file asli tim model.

    align_token_grid() di fusion_cross_attention.py pakai round(N ** 0.5)
    di mana N = tokens.shape[1]. Saat di-trace oleh torch.onnx.export(),
    N kadang jadi bertipe Tensor (bukan int Python biasa), dan Tensor
    tidak punya __round__() -> TypeError. Ini murni artefak tracing —
    nilai N tetap sama persis (mis. 196 utk input 224x224), cuma perlu
    di-cast eksplisit ke int sebelum dipakai aritmetika.

    Di-patch di sini (override atribut modul saat runtime), BUKAN edit
    file fusion_cross_attention.py di folder tim model — supaya source
    code milik tim model tidak tersentuh. Worth dilaporkan ke tim model
    supaya nanti ditambahkan permanen (int(N) sebelum round()) di source
    aslinya, karena masalah ini akan muncul lagi kalau ada tim data lain
    coba export model yang sama.
    """
    import fusion_cross_attention as fca

    def _patched_align_token_grid(tokens, target_grid):
        B, N, C = tokens.shape
        N = int(N)  # <-- fix: paksa jadi int Python biasa sebelum aritmetika
        src_grid = int(round(N ** 0.5))
        if src_grid == target_grid:
            return tokens
        x = tokens.transpose(1, 2).reshape(B, C, src_grid, src_grid)
        x = F.interpolate(x, size=(target_grid, target_grid), mode="bilinear", align_corners=False)
        return x.flatten(2).transpose(1, 2)

    fca.align_token_grid = _patched_align_token_grid
    print("[INFO] Patch align_token_grid() diterapkan (fix TypeError Tensor.__round__ "
          "saat ONNX trace) — file asli tim model TIDAK diubah, ini override runtime "
          "khusus proses export ini saja.")


def export_to_onnx(model, dummy_inputs, onnx_path, opset):
    os.makedirs(os.path.dirname(onnx_path), exist_ok=True)
    # Sesuai signature FusionModel.forward(rgb_img, thermal_img) -> logits/heatmap
    input_names = ["rgb_img", "thermal_img"]
    output_names = ["output"]
    dynamic_axes = {
        "rgb_img": {0: "batch"},
        "thermal_img": {0: "batch"},
        "output": {0: "batch"},
    }
    torch.onnx.export(
        model,
        dummy_inputs,
        onnx_path,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        opset_version=opset,
        do_constant_folding=True,
    )
    print(f"[DONE] Model diexport ke: {onnx_path}")


def verify_onnx(onnx_path):
    """Cek dasar: file valid & bisa di-load onnxruntime. Bukan cek akurasi
    (bandingkan output PyTorch vs ONNX itu tanggung jawab terpisah kalau
    mau lebih teliti — di sini cuma pastikan tidak crash pas load)."""
    try:
        import onnx
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        print("[INFO] onnx.checker.check_model: PASS (struktur graph valid)")
    except ImportError:
        print("[WARN] Package 'onnx' tidak terinstall, skip structural check. "
              "Install: pip install onnx --break-system-packages")
    except Exception as e:
        print(f"[WARN] onnx.checker gagal: {e}")


def measure_latency_onnxruntime(onnx_path, dummy_inputs_np, n_warmup, n_runs):
    """Ukur latensi inferensi ONNX Runtime di CPU: warm-up dulu (dibuang),
    baru ukur n_runs kali, laporkan median (bukan mean — median lebih tahan
    terhadap outlier dari OS scheduling noise)."""
    try:
        import onnxruntime as ort
    except ImportError:
        print("[ERROR] onnxruntime tidak terinstall. Install dulu:")
        print("        pip install onnxruntime --break-system-packages")
        sys.exit(1)

    sess_options = ort.SessionOptions()
    session = ort.InferenceSession(onnx_path, sess_options, providers=["CPUExecutionProvider"])
    input_feed = {inp.name: arr for inp, arr in zip(session.get_inputs(), dummy_inputs_np)}

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
        "min_ms": min(latencies_ms),
        "max_ms": max(latencies_ms),
        "p95_ms": sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1],
    }


def main():
    args = parse_args()
    device = torch.device(args.device)

    if not os.path.isfile(args.checkpoint):
        print(f"[ERROR] Checkpoint tidak ditemukan: {args.checkpoint}")
        sys.exit(1)

    print(f"[INFO] Loading model dari checkpoint: {args.checkpoint}")
    model = build_model(args)
    model = load_checkpoint(model, args.checkpoint, device, strict=args.strict_load)
    model.to(device)
    model.eval()

    h_rgb, w_rgb = args.rgb_size
    h_th, w_th = args.thermal_size
    dummy_rgb = torch.randn(1, 3, h_rgb, w_rgb, device=device)
    dummy_thermal = torch.randn(1, 1, h_th, w_th, device=device)
    dummy_inputs = (dummy_rgb, dummy_thermal)

    print("[INFO] Export ke ONNX...")
    _patch_align_token_grid_for_tracing()
    export_to_onnx(model, dummy_inputs, args.onnx_out, args.opset)
    verify_onnx(args.onnx_out)

    dummy_inputs_np = [t.cpu().numpy() for t in dummy_inputs]
    stats = measure_latency_onnxruntime(args.onnx_out, dummy_inputs_np, args.n_warmup, args.n_runs)

    per_frame_note = ""
    if args.n_tiles > 1:
        per_frame_ms = stats["median_ms"] * args.n_tiles
        per_frame_note = f" | latensi PER FRAME (x{args.n_tiles} tile) ~= {per_frame_ms:.2f} ms"
        print(f"[INFO] n_tiles={args.n_tiles} -> latensi di atas per-tile. "
              f"Estimasi per-frame (sekuensial): {per_frame_ms:.2f} ms")
        print("       (Kalau tile diproses batched/paralel, angka ini overestimate — "
              "sesuaikan cara hitung dengan implementasi tim model yang sebenarnya)")

    print(f"[RESULT] median={stats['median_ms']:.2f}ms mean={stats['mean_ms']:.2f}ms "
          f"stdev={stats['stdev_ms']:.2f}ms p95={stats['p95_ms']:.2f}ms{per_frame_note}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    write_header = not os.path.isfile(args.out)
    with open(args.out, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "checkpoint", "onnx_path", "n_warmup", "n_runs", "n_tiles",
                "median_ms", "mean_ms", "stdev_ms", "min_ms", "max_ms", "p95_ms",
                "median_per_frame_ms",
            ])
        writer.writerow([
            os.path.basename(args.checkpoint), args.onnx_out, args.n_warmup, args.n_runs,
            args.n_tiles, f"{stats['median_ms']:.3f}", f"{stats['mean_ms']:.3f}",
            f"{stats['stdev_ms']:.3f}", f"{stats['min_ms']:.3f}", f"{stats['max_ms']:.3f}",
            f"{stats['p95_ms']:.3f}",
            f"{stats['median_ms'] * args.n_tiles:.3f}" if args.n_tiles > 1 else f"{stats['median_ms']:.3f}",
        ])
    print(f"[DONE] Hasil ditambahkan ke: {args.out}")
    print("[REMINDER] Simpan juga file .onnx ini — dipakai lagi di 02_quantize_int8.py. "
          "Lanjut ke script itu setelah angka latensi di atas dicek masuk akal.")


if __name__ == "__main__":
    main()