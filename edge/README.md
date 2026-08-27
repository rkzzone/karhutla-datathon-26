# Perangkat tepi — pengukuran & verifikasi

Pengukuran kelayakan model di perangkat terbatas, dan verifikasi integritas
pembagian data.

## Struktur

```
scripts/   run_baseline_degradasi.py, verifikasi_split_baseline.py
results/   Keluaran pengukuran
```

## Menjalankan

```bash
python scripts/verifikasi_split_baseline.py   # cek kebocoran antar split
python scripts/run_baseline_degradasi.py      # baseline lintas tingkat degradasi
```

Ekspor ONNX dan kuantisasi ada di `../model/edge_bench/`. Berkas ONNX hasilnya
tidak disimpan di repositori ini — ukurannya 118 MB, melampaui batas keras
GitHub 100 MB. Lihat tautan Hugging Face pada README akar.
