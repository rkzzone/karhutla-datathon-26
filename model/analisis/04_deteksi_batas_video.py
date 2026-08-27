"""Deteksi batas video FLAME 2 dari diskontinuitas antar-bingkai.

Latar belakang. `DEFAULT_VIDEO_FRAME_RANGES` di dataset_flame2.py berisi batas
karangan yang ditandai sendiri sebagai TODO-VERIFIKASI. Batas itu membelah data
latih dan validasi Stage 1, sehingga val_acc Stage 1 tidak dapat ditafsirkan.

README FLAME 2 item #8 memberi dua jangkar yang pasti:
  * 13.700 bingkai RGB beresolusi 3840x2160  -> video 1 dan 2
  * 39.751 bingkai RGB beresolusi 1920x1080  -> video 3 sampai 7
  * Total 53.451, dan batas 13.700 cocok persis dengan akhir segmen label pertama.

Durasi video dari item #1 sampai #7 tidak dapat dipakai langsung karena
durasi kali 30 FPS menghasilkan 56.100, bukan 53.451. Karena itu batas per
video dideteksi dari data: pergantian video menghasilkan lompatan besar pada
selisih antar-bingkai berurutan, sedangkan di dalam satu video selisihnya kecil.

Keluaran: batas_video_terdeteksi.json berisi ranges siap tempel ke
DEFAULT_VIDEO_FRAME_RANGES, beserta bukti pendukungnya.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

# Jangkar dari README FLAME 2 item #8.
JANGKAR_4K = 13700          # akhir video 2, batas antara kelompok 4K dan 1080p
TOTAL_BINGKAI = 53451
N_VIDEO = 7

# Durasi detik dari README item #1 sampai #7, dipakai HANYA sebagai pemeriksaan
# kewajaran proporsi, bukan sebagai sumber batas.
DURASI = {1: 291, 2: 183, 3: 404, 4: 301, 5: 267, 6: 185, 7: 239}


def muat_kecil(path: Path, sisi: int = 32) -> np.ndarray:
    """Baca JPEG dengan draft mode supaya dekoding jauh lebih cepat."""
    im = Image.open(path)
    im.draft("L", (sisi, sisi))
    im = im.convert("L").resize((sisi, sisi))
    return np.asarray(im, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rgb-dir", required=True, help="folder '254p RGB Images'")
    ap.add_argument("--pola", default="254p RGB Frame ({i}).jpg")
    ap.add_argument("--sisi", type=int, default=32)
    ap.add_argument("--out", default="batas_video_terdeteksi.json")
    args = ap.parse_args()

    d = Path(args.rgb_dir)
    n = TOTAL_BINGKAI

    print(f"membaca {n} bingkai pada {args.sisi}x{args.sisi} ...")
    selisih = np.zeros(n + 1, dtype=np.float32)  # selisih[i] = |frame i - frame i-1|
    sebelumnya = muat_kecil(d / args.pola.format(i=1), args.sisi)
    for i in range(2, n + 1):
        kini = muat_kecil(d / args.pola.format(i=i), args.sisi)
        selisih[i] = np.abs(kini - sebelumnya).mean()
        sebelumnya = kini
        if i % 10000 == 0:
            print(f"  {i}/{n}")

    valid = selisih[2:]
    med, mad = float(np.median(valid)), float(np.median(np.abs(valid - np.median(valid))))
    print(f"\nselisih antar-bingkai: median={med:.3f}  MAD={mad:.3f}  maks={valid.max():.3f}")

    # Kandidat batas: lompatan terbesar. Ambil jauh lebih banyak dari yang
    # dibutuhkan, lalu saring supaya tidak ada dua kandidat berdekatan.
    urut = np.argsort(selisih)[::-1]
    kandidat, dipakai = [], []
    for idx in urut:
        i = int(idx)
        if i < 100 or i > n - 100:
            continue
        if any(abs(i - j) < 500 for j in dipakai):
            continue
        dipakai.append(i)
        kandidat.append((i, float(selisih[i]), float((selisih[i] - med) / (mad + 1e-9))))
        if len(kandidat) >= 20:
            break

    print("\n20 diskontinuitas terkuat (bingkai, selisih, z-MAD):")
    for i, v, z in kandidat:
        tanda = "  <-- jangkar README (batas 4K/1080p)" if abs(i - JANGKAR_4K) <= 2 else ""
        print(f"  bingkai {i:6d}   selisih={v:7.3f}   z={z:8.1f}{tanda}")

    # Pemeriksaan jangkar: batas 13.700 HARUS termasuk diskontinuitas kuat.
    dekat_jangkar = [(i, v, z) for i, v, z in kandidat if abs(i - JANGKAR_4K) <= 3]
    if dekat_jangkar:
        print(f"\n[OK] jangkar README pada {JANGKAR_4K} terdeteksi sebagai "
              f"diskontinuitas (z={dekat_jangkar[0][2]:.1f})")
    else:
        peringkat = int(np.argsort(np.argsort(selisih)[::-1] == JANGKAR_4K).argmax())
        print(f"\n[PERINGATAN] jangkar {JANGKAR_4K} TIDAK masuk 20 besar. "
              f"selisih di sana = {selisih[JANGKAR_4K]:.3f} (z={(selisih[JANGKAR_4K]-med)/(mad+1e-9):.1f}). "
              f"Deteksi ini tidak dapat dipercaya; pakai jalur segmen label.")

    # Enam batas internal untuk tujuh video. Batas 13.700 dikunci sebagai jangkar,
    # lima sisanya diambil dari kandidat terkuat di luar jangkar.
    sisa = [k for k in kandidat if abs(k[0] - JANGKAR_4K) > 3]
    terpilih = sorted([JANGKAR_4K] + [k[0] for k in sisa[: N_VIDEO - 2]])
    batas = [1] + terpilih + [TOTAL_BINGKAI + 1]

    ranges = {i + 1: (batas[i], batas[i + 1]) for i in range(N_VIDEO)}
    panjang = {v: hi - lo for v, (lo, hi) in ranges.items()}

    print("\nbatas video terdeteksi (setengah terbuka, [lo, hi)):")
    total_durasi = sum(DURASI.values())
    for v, (lo, hi) in ranges.items():
        n_v = hi - lo
        fps = n_v / DURASI[v]
        print(f"  video {v}: [{lo:6d}, {hi:6d})  n={n_v:6d}  durasi={DURASI[v]:4d}s  "
              f"fps efektif={fps:5.2f}")

    print(f"\n  total bingkai       : {sum(panjang.values())} (harus {TOTAL_BINGKAI})")
    print(f"  video 1+2           : {panjang[1] + panjang[2]} (harus {JANGKAR_4K})")
    print(f"  video 3..7          : {sum(panjang[v] for v in range(3, 8))} (harus {TOTAL_BINGKAI - JANGKAR_4K})")

    fps_semua = [panjang[v] / DURASI[v] for v in ranges]
    print(f"  fps efektif rentang : {min(fps_semua):.2f} sampai {max(fps_semua):.2f}")
    print("  (wajar bila seluruhnya di kisaran 27 sampai 30; bila ada yang jauh "
          "meleset, salah satu batas kemungkinan keliru)")

    hasil = {
        "sumber": "deteksi diskontinuitas antar-bingkai pada 254p RGB",
        "jangkar_readme": {"batas_4k_ke_1080p": JANGKAR_4K,
                           "n_4k": JANGKAR_4K, "n_1080p": TOTAL_BINGKAI - JANGKAR_4K},
        "statistik_selisih": {"median": med, "mad": mad, "maks": float(valid.max())},
        "kandidat_20_terkuat": [{"bingkai": i, "selisih": v, "z_mad": z} for i, v, z in kandidat],
        "ranges": {str(v): list(r) for v, r in ranges.items()},
        "panjang_per_video": {str(v): int(p) for v, p in panjang.items()},
        "fps_efektif": {str(v): round(panjang[v] / DURASI[v], 3) for v in ranges},
        "durasi_readme_detik": DURASI,
    }
    Path(args.out).write_text(json.dumps(hasil, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {args.out}")

    print("\nSiap tempel ke dataset_flame2.py:")
    isi = ", ".join(f"{v}: ({lo}, {hi})" for v, (lo, hi) in ranges.items())
    print(f"DEFAULT_VIDEO_FRAME_RANGES = {{{isi}}}")


if __name__ == "__main__":
    main()
