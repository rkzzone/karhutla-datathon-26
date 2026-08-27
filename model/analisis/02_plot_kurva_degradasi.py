"""Gambar kurva degradasi dari CSV terkoreksi, dua panel: validasi dan uji.

Palet Okabe-Ito, lolos validator buta warna: deutan dE 11,0 dan normal 25,8,
kontras terhadap latar di atas 3:1. Identitas seri TIDAK pernah bergantung pada
warna saja, sebab tiap seri juga punya gaya garis dan penanda berbeda, sehingga
tetap terbaca pada cetakan hitam-putih dan bagi pembaca buta warna.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SERI = [
    ("acc_fusion", "Fusi penuh", "#0072B2", "-", "o"),
    ("acc_rgb_only", "RGB saja", "#D55E00", "--", "s"),
    ("acc_thermal_only", "Termal saja", "#009E73", "-.", "^"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", required=True,
                    help="folder berisi degradation_curve_{val,test}_TERKOREKSI.csv")
    ap.add_argument("--out", default="kurva_degradasi_terkoreksi")
    args = ap.parse_args()
    d = Path(args.csv_dir)

    def baca(split):
        with open(d / f"degradation_curve_{split}_TERKOREKSI.csv", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    plt.rcParams.update({
        "font.family": "serif", "font.size": 8,
        "axes.linewidth": 0.6, "axes.edgecolor": "#4a4a4a",
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.color": "#4a4a4a", "ytick.color": "#4a4a4a",
    })

    fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.5), sharey=True)
    for ax, split, judul in zip(axes, ["val", "test"],
                                ["Validasi ($n=240$)", "Uji ($n=200$)"]):
        rows = baca(split)
        tau = [float(r["tau"]) for r in rows]
        for kol, label, warna, gaya, penanda in SERI:
            y = [float(r[kol]) * 100 for r in rows]
            ax.plot(tau, y, color=warna, linestyle=gaya, marker=penanda,
                    markersize=3.5, linewidth=1.4, label=label,
                    markeredgecolor="white", markeredgewidth=0.5,
                    clip_on=False, zorder=3)
        ax.set_title(judul, fontsize=8.5, pad=6)
        ax.set_xlabel(r"$\tau$ (level degradasi)", fontsize=8)
        ax.set_xlim(-0.03, 1.03)
        ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax.grid(axis="y", color="#e2e2e0", linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
        for sisi in ("top", "right"):
            ax.spines[sisi].set_visible(False)

    axes[0].set_ylabel("Akurasi (%)", fontsize=8)
    axes[0].set_ylim(76, 101)
    axes[0].set_yticks([80, 85, 90, 95, 100])

    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=8,
               bbox_to_anchor=(0.5, -0.06), handlelength=2.4, columnspacing=1.8)
    fig.tight_layout()
    fig.savefig(f"{args.out}.pdf", bbox_inches="tight", dpi=300)
    fig.savefig(f"{args.out}.png", bbox_inches="tight", dpi=200)
    print(f"-> {args.out}.pdf dan {args.out}.png")

    for split in ["val", "test"]:
        rows = baca(split)
        a, b = rows[0], rows[-1]
        print(f"{split}: penurunan tau 0->1 (poin)  " + "  ".join(
            f"{lbl}={(float(a[k]) - float(b[k])) * 100:.2f}" for k, lbl, *_ in SERI))


if __name__ == "__main__":
    main()
