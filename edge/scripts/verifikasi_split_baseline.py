#!/usr/bin/env python
"""Verifikasi bahwa rffnet_test.csv identik dengan lists/test_flm.txt milik RFFNet.

Bila identik, kita boleh menulis "dievaluasi pada partisi tertahan yang IDENTIK",
kalimat yang jauh lebih kuat daripada "sama-sama 200 sampel". Bila tidak,
perbandingan baseline harus diberi catatan bahwa datanya berbeda.

Biaya: nol. Jalankan ini SEBELUM eksperimen apa pun, karena hasilnya menentukan
seberapa kuat kalimat yang boleh masuk paper.

    python verifikasi_split_baseline.py \
        --kami manifests/rffnet_test.csv \
        --mereka /path/ke/rffnet/lists/test_flm.txt
"""
import argparse, csv, re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--kami", required=True)
ap.add_argument("--mereka", required=True)
a = ap.parse_args()

kami = set()
for r in csv.DictReader(open(a.kami, encoding="utf-8")):
    kami.add(int(r["frame_index"]))

mereka = set()
for ln in open(a.mereka, encoding="utf-8"):
    ln = ln.strip()
    if not ln:
        continue
    # baris berisi path seperti .../img_rgb_(378).png ; ambil angka di kurung
    m = re.findall(r"\((\d+)\)", ln)
    if m:
        mereka.add(int(m[0]))
        continue
    m = re.findall(r"(\d+)", ln)
    if m:
        mereka.add(int(m[-1]))

print(f"partisi kami   : {len(kami)} frame unik")
print(f"partisi mereka : {len(mereka)} frame unik")
irisan = kami & mereka
print(f"irisan         : {len(irisan)}")
print(f"hanya di kami  : {len(kami - mereka)}")
print(f"hanya di mereka: {len(mereka - kami)}")

if kami == mereka:
    print("\nIDENTIK. Boleh ditulis: 'dievaluasi pada partisi tertahan yang identik'.")
elif len(irisan) / max(len(kami), 1) > 0.9:
    print(f"\nHAMPIR identik ({len(irisan)/len(kami)*100:.1f}% beririsan), tetapi TIDAK sama.")
    print("Tulis jumlah yang beririsan apa adanya, jangan klaim identik.")
    print(f"contoh beda: hanya-kami {sorted(kami-mereka)[:8]}  hanya-mereka {sorted(mereka-kami)[:8]}")
else:
    print("\nBERBEDA. Perbandingan baseline dilakukan pada data yang tidak sama.")
    print("Ini HARUS dinyatakan di paper, dan klaim perbandingannya dilemahkan.")
