# Skrip eksekusi

Dijalankan berurutan; tiap skrip memakai keluaran skrip sebelumnya. Konfigurasi
per tahap ada di `../configs/`.

| # | Skrip | Menghasilkan |
|---|---|---|
| 01 | `01_pralatih_termal.py` | Encoder termal terlatih awal |
| 02 | `02_finetune_fusi.py` | Model fusi RGB–termal |
| 02a | `02a_sapuan_berbenih.py` | Sapuan hiperparameter dengan benih tetap |
| 02b | `02b_seleksi_diperbaiki.py` | Seleksi ulang setelah perbaikan kriteria |
| 03 | `03_gating_keandalan.py` | Gating keandalan per modalitas |
| 04 | `04_lokalisasi.py` | Kepala lokalisasi (peta atensi) |
| 05 | `05_adaptasi_domain.py` | Adaptasi domain LoRA, multi-benih |

Hasil tiap tahap ada di `../results/` dengan penamaan yang sama.

## Catatan penomoran

Penomoran ini **berurutan tanpa celah**, berbeda dari penamaan kerja yang
dipakai selama pengembangan (`RUN1`–`RUN6`). Satu skrip pada urutan lama —
kurva degradasi — tidak jadi dipakai karena digantikan
`../analisis/02_plot_kurva_degradasi.py`, sehingga urutan lama menyisakan lubang
di angka 3. Pemetaannya:

```
RUN1  → 01     RUN2C → 02b        RUN5 → 04
RUN2  → 02     RUN3  → (dibuang)  RUN6 → 05
RUN2B → 02a    RUN4  → 03
```
