"""Latensi CPU, jumlah parameter, dan ukuran model, diukur pada perangkat nyata.

BUKAN perangkat tepi. Ini CPU x86, dan harus disebut sebagai itu di paper
maupun slide. Memakai src/metrics.py::measure_latency, minimal 100 pengukuran
setelah pemanasan, sesuai definisi metrik tim.

Butuh bobot DINOv2 dari torch.hub, jadi run pertama memerlukan internet.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from pathlib import Path

import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True,
                    help="folder yang berisi src/, agar 'from src...' dapat diimpor")
    ap.add_argument("--checkpoints", nargs="+", required=True,
                    help="satu atau lebih path .pth")
    ap.add_argument("--device-name", required=True,
                    help="nama perangkat SPESIFIK, mis. 'Lenovo ThinkPad T480, Intel i5-8250U'")
    ap.add_argument("--n-runs", type=int, default=100)
    ap.add_argument("--out-prefix", default="latency_cpu")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(args.repo_root).resolve()))
    from src import metrics as M
    from src.eval_paper_metrics import build_model

    torch.set_grad_enabled(False)
    device = torch.device("cpu")

    hasil = []
    stats = {
        "perangkat": args.device_name,
        "bukan_perangkat_tepi": True,
        "catatan": ("Diukur pada CPU x86, presisi fp32, batch 1, bingkai penuh "
                    "224x224, PyTorch eager. Angka ini BUKAN latensi perangkat tepi."),
        "torch": torch.__version__,
        "python": platform.python_version(),
        "threads": torch.get_num_threads(),
        "checkpoint": {},
    }

    for path_str in args.checkpoints:
        path = Path(path_str)
        rgb_enc, th_enc, fus, head, _, _ = build_model(path, device)

        raw = torch.load(path, map_location="cpu", weights_only=False)
        per_komponen = {k: int(sum(t.numel() for t in v.values() if hasattr(t, "numel")))
                        for k, v in raw.items() if isinstance(v, dict)}
        stats["checkpoint"][path.name] = {
            "params_per_komponen": per_komponen,
            "params_total_termasuk_buffer": sum(per_komponen.values()),
            "ukuran_berkas_byte": path.stat().st_size,
            "ukuran_berkas_mib": round(path.stat().st_size / 1024 ** 2, 1),
        }

        rgb = torch.randn(1, 3, 224, 224)
        thermal = torch.randn(1, 1, 224, 224)

        kandidat = [
            ("encoder_rgb", lambda: rgb_enc(rgb)),
            ("encoder_termal", lambda: th_enc(thermal)),
            ("pipeline_penuh_fusi", lambda: head(fus(rgb_enc(rgb), th_enc(thermal)))),
            ("pipeline_rgb_saja", lambda: head(fus(rgb_enc(rgb), torch.zeros(1, 196, 384)))),
        ]
        for nama, fn in kandidat:
            st = M.measure_latency(fn, n_measurements=args.n_runs, n_warmup=10)
            hasil.append({
                "checkpoint": path.name, "komponen": nama,
                "median_ms": round(st.median_ms, 2), "mean_ms": round(st.mean_ms, 2),
                "p90_ms": round(st.p90_ms, 2), "p99_ms": round(st.p99_ms, 2),
                "n_pengukuran": st.n_measurements, "warmup_dibuang": st.warmup_discarded,
            })
            print(f"{path.name:30s} {nama:22s} median={st.median_ms:8.2f} ms  "
                  f"p90={st.p90_ms:8.2f}  p99={st.p99_ms:8.2f}")

    with open(f"{args.out_prefix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hasil[0].keys()))
        w.writeheader(); w.writerows(hasil)
    json.dump({"perangkat_uji": stats, "latensi": hasil},
              open(f"{args.out_prefix}_stats.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(f"\n-> {args.out_prefix}.csv dan {args.out_prefix}_stats.json")


if __name__ == "__main__":
    main()
