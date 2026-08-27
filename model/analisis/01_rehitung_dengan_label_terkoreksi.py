"""Hitung ulang seluruh hasil klasifikasi memakai label yang sudah dikoreksi.

Prediksi model TIDAK dihitung ulang. Yang diperbaiki hanya ground truth, dan
karena seluruh prediksi per sampel di tiap tau sudah tersimpan, tidak ada
inferensi model yang perlu diulang. Skrip ini berjalan di CPU dalam hitungan
detik, tanpa torch.

Masukan:
  --labels    CSV berisi kolom split, frame_index, label_lama, label_baru
              (dihasilkan oleh 00_cek_label.py)
  --pred-dir  folder berisi per_sample_predictions_{split}_tau{t}.csv
              (dihasilkan oleh src/eval_paper_metrics.py)

Keluaran:
  hasil_terkoreksi.json
  degradation_curve_{split}_TERKOREKSI.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from math import comb
from pathlib import Path

KELAS = ["no_fire", "fire_no_smoke", "fire_smoke"]
MODES = ["fusi_penuh", "rgb_saja", "termal_saja"]
TAUS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
SPLITS = ["train", "val", "test"]
Z = 1.959963984540054  # 95%


def wilson(p: float, n: int) -> tuple[float, float]:
    """Selang kepercayaan Wilson untuk proporsi. Dipakai karena n kecil dan
    proporsi mendekati 1, kondisi tempat selang normal biasa meleset."""
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    m = Z / d * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return max(0.0, c - m), min(1.0, c + m)


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """Uji McNemar eksak dua sisi atas pasangan diskordan. Dipakai karena
    seluruh konfigurasi dievaluasi pada sampel yang SAMA."""
    b01 = sum(1 for x, z in zip(a, b) if x and not z)
    b10 = sum(1 for x, z in zip(a, b) if not x and z)
    nd = b01 + b10
    if nd == 0:
        return b01, b10, 1.0
    k = min(b01, b10)
    return b01, b10, min(1.0, 2 * sum(comb(nd, i) for i in range(k + 1)) * 0.5 ** nd)


def prf(y: list[int], p: list[int], n_kelas: int = 3):
    """Presisi, recall, F1 per kelas. Kelas tanpa dukungan DIKELUARKAN dari
    rerata makro; melibatkannya menghasilkan angka menyesatkan."""
    out, F = {}, []
    for c in range(n_kelas):
        tp = sum(1 for t, q in zip(y, p) if q == c and t == c)
        fp = sum(1 for t, q in zip(y, p) if q == c and t != c)
        fn = sum(1 for t, q in zip(y, p) if q != c and t == c)
        sup = sum(1 for t in y if t == c)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
        out[KELAS[c]] = {"precision": pr, "recall": rc, "f1": f1, "support": sup}
        F.append(f1)
    hadir = [c for c in range(n_kelas) if out[KELAS[c]]["support"] > 0]
    return out, {
        "macro_f1_3kelas": sum(F) / 3,
        "macro_f1_kelas_ber_dukungan": sum(F[c] for c in hadir) / len(hadir),
        "kelas_ber_dukungan": [KELAS[c] for c in hadir],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True, help="labels_terkoreksi.csv")
    ap.add_argument("--pred-dir", required=True, help="folder per_sample_predictions_*.csv")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    pred_dir, out_dir = Path(args.pred_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lab, lama = {}, {}
    for r in csv.DictReader(open(args.labels, encoding="utf-8")):
        lab[(r["split"], r["frame_index"])] = int(r["label_baru"])
        lama[(r["split"], r["frame_index"])] = int(r["label_lama"])
    print(f"label terkoreksi dimuat: {len(lab)} bingkai")

    hasil = {"per_split": {}, "kurva": {}}

    for split in SPLITS:
        hasil["per_split"][split] = {}
        baris_kurva = []
        for tau in TAUS:
            f = pred_dir / f"per_sample_predictions_{split}_tau{tau}.csv"
            if not f.exists():
                continue
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
            fid = [r["frame_index"] for r in rows]
            y = [lab[(split, i)] for i in fid]
            y_lama = [lama[(split, i)] for i in fid]
            # sanity: label lama di CSV harus cocok dgn yang tersimpan di prediksi
            cek = sum(1 for r, t in zip(rows, y_lama) if int(r["label_true"]) != t)
            pred = {m: [int(r[f"pred_{m}"]) for r in rows] for m in MODES}
            n = len(y)
            benar = {m: [p == t for p, t in zip(pred[m], y)] for m in MODES}

            e = {"n": n, "tau": tau, "cek_konsistensi_label_lama": cek,
                 "distribusi_kelas": {KELAS[c]: sum(1 for t in y if t == c) for c in range(3)},
                 "per_mode": {}, "mcnemar": {}}

            for m in MODES:
                acc = sum(benar[m]) / n
                acc_lama = sum(1 for p, t in zip(pred[m], y_lama) if p == t) / n
                lo, hi = wilson(acc, n)
                per_c, makro = prf(y, pred[m])
                fn_api = sum(1 for p, t in zip(pred[m], y) if t != 0 and p == 0)
                fp_api = sum(1 for p, t in zip(pred[m], y) if t == 0 and p != 0)
                e["per_mode"][m] = {
                    "accuracy": acc, "n_benar": sum(benar[m]),
                    "accuracy_label_lama": acc_lama,
                    "selisih_poin": round((acc - acc_lama) * 100, 2),
                    "ci95": [lo, hi], "per_class": per_c, **makro,
                    "false_negative_api_terlewat": fn_api,
                    "false_positive_alarm_palsu": fp_api,
                    "recall_deteksi_kejadian_api": 1 - fn_api / max(1, sum(1 for t in y if t != 0)),
                }

            for a, b in [("fusi_penuh", "rgb_saja"), ("fusi_penuh", "termal_saja"),
                         ("rgb_saja", "termal_saja")]:
                b01, b10, p = mcnemar(benar[a], benar[b])
                e["mcnemar"][f"{a}_vs_{b}"] = {
                    "hanya_pertama_benar": b01, "hanya_kedua_benar": b10,
                    "n_diskordan": b01 + b10, "p_value": p, "signifikan_0.05": p < 0.05}

            hasil["per_split"][split][f"tau{tau}"] = e
            baris_kurva.append({
                "tau": tau,
                "acc_rgb_only": e["per_mode"]["rgb_saja"]["accuracy"],
                "acc_thermal_only": e["per_mode"]["termal_saja"]["accuracy"],
                "acc_fusion": e["per_mode"]["fusi_penuh"]["accuracy"]})

        hasil["kurva"][split] = baris_kurva
        if baris_kurva:
            p = out_dir / f"degradation_curve_{split}_TERKOREKSI.csv"
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["tau", "acc_rgb_only",
                                                   "acc_thermal_only", "acc_fusion"])
                w.writeheader(); w.writerows(baris_kurva)
            print(f"-> {p}")

    jp = out_dir / "hasil_terkoreksi.json"
    json.dump(hasil, open(jp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    for split in SPLITS:
        d = hasil["per_split"].get(split)
        if not d or "tau0.0" not in d:
            continue
        d0 = d["tau0.0"]
        print(f"\n{'=' * 70}\n{split.upper()}  n={d0['n']}  {d0['distribusi_kelas']}"
              f"  (cek label lama: {d0['cek_konsistensi_label_lama']} beda)")
        for tau in TAUS:
            e = d.get(f"tau{tau}")
            if not e:
                continue
            sel = "  ".join(f"{m.split('_')[0]}={e['per_mode'][m]['accuracy'] * 100:6.2f}"
                            for m in MODES)
            print(f"  tau={tau:.1f}  {sel}")
        e0, e1 = d["tau0.0"], d.get("tau1.0")
        if e1:
            print("  penurunan tau 0->1 (poin):", {
                m: round((e0['per_mode'][m]['accuracy'] - e1['per_mode'][m]['accuracy']) * 100, 2)
                for m in MODES})
        for k, v in d["tau0.0"]["mcnemar"].items():
            tanda = "SIGNIFIKAN" if v["signifikan_0.05"] else "tidak signifikan"
            print(f"    McNemar {k:32s} diskordan={v['n_diskordan']:3d}  "
                  f"p={v['p_value']:.5f}  {tanda}")

    print(f"\n-> {jp}")


if __name__ == "__main__":
    main()
