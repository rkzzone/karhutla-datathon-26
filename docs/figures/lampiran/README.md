# Lampiran F — Tangkapan Layar Antarmuka

Diambil 9 Agustus 2026 dari build produksi dengan **data nyata**: alert
merupakan keluaran `fusion_v3_localization.pth`, hotspot berasal dari NASA
FIRMS langsung, dan angka evaluasi berasal dari CSV tim model.

Resolusi 3200×N piksel (DPR 2), tema gelap — tema kanonik sesuai
`DESIGN_BRIEF.md`.

| Berkas | Halaman | Yang ditunjukkan |
|---|---|---|
| `F1_peta_operasi.png` | Peta Operasi | Hotspot FIRMS langsung, marker alert, sensor simulasi berlabel, rute patroli, legenda skala Ember |
| `F2_panel_alert.png` | Panel Alert | Daftar terurut risiko, ribbon Ironbow mengikuti keyakinan, badge modalitas di tiap kartu |
| `F3_rincian_alert.png` | Rincian Alert | RGB + termal berdampingan, overlay lokalisasi, keandalan modalitas, jejak keputusan |
| `F4_info_model.png` | Info Model | Tabel baseline, kurva degradasi, ablation gating, metrik lokalisasi |

## Catatan untuk penulis paper

**F3 adalah tangkapan terkuat.** Alert yang ditampilkan punya keandalan
RGB **15%** vs termal **83%** — visualisasi paling langsung dari argumen inti
proposal: saat satu modalitas terdegradasi, sistem menyatakan ketergantungannya
secara eksplisit alih-alih diam. Badge berbunyi "Bersandar pada termal".

Catatan provenans di bagian bawah F3 menyebutkan bahwa bingkai berasal dari
FLAME 2 (Arizona) dan koordinat merupakan penempatan simulasi. **Jangan
memotong bagian itu** saat menyisipkan gambar ke paper — ia yang menjaga klaim
tetap jujur.

Bila butuh varian tema terang atau keadaan data lain (`null`, kosong, galat),
seluruhnya tersedia di `frontend/temporary-screenshots/` dengan penamaan
`run{NN}-{halaman}-{keadaan}-{seq}.png`.
