# Model — fusi RGB–termal dengan gating keandalan

Pelatihan dan evaluasi model deteksi. Angka hasil ada di README akar; berkas
mentahnya di `../docs/results/`.

## Struktur

```
runs/        Skrip eksekusi berurutan (01–05). Lihat runs/README.md
configs/     Konfigurasi per tahap, satu YAML per skrip
analisis/    Audit label, kurva degradasi, benchmark CPU, deteksi batas video
edge_bench/  Ekspor ONNX, kuantisasi INT8, pengukuran parameter & FLOPs
src/         Modul bersama — data, model, augmentasi
results/     Keluaran tiap tahap
```

## Menjalankan

Skrip dirancang untuk lingkungan Kaggle dengan GPU. Path dataset dikonfigurasi
di `configs/kaggle_paths.yaml`.

```bash
python runs/01_pralatih_termal.py
python runs/02_finetune_fusi.py
# ... berurutan sampai 05
```

## Catatan reproduksibilitas

Angka evaluasi di README akar dihitung ulang **setelah audit label**, dan
berbeda dari angka yang sempat dilaporkan sebelumnya. Skrip audit ada di
`analisis/00_cek_label.py`, dan hasil terkoreksi di
`../docs/results/hasil_terkoreksi.json`. Yang lama sengaja tidak dipertahankan.

Data latih dan bobot tidak disimpan di repositori ini — lihat README akar.
