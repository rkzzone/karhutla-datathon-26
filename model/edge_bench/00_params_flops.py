"""
edge_bench/00_params_flops.py — Stage 8a

Hitung jumlah parameter, FLOPs, dan ukuran file dari checkpoint model fusi
Tim model. Ini langkah PALING AWAL Stage 8 — jalankan begitu checkpoint
pertama (fusion_v1.pth dst.) sudah diterima dari tim model.

============================================================================
TODO WAJIB DIISI SEBELUM SCRIPT INI BISA JALAN (3 tempat, cari "TODO"):
============================================================================
1. Import class model yang benar dari model/src/models/
2. Instansiasi model dengan argumen yang PERSIS sama seperti dipakai tim model
   saat training (jumlah channel, num_classes, dst.)
3. Bentuk dummy input (ukuran RGB, ukuran thermal, jumlah tile per frame)

Jangan tebak nilai-nilai ini — minta konfirmasi ke tim model dulu — lihat kolom
"Spesifikasi input/preprocessing" pada README_stage8.md.

Cara pakai:
    python edge_bench/00_params_flops.py \
        --checkpoint weights/fusion_v1.pth \
        --out edge_bench/reports/params_flops.csv
"""
import argparse
import csv
import os
import sys

import torch


def parse_args():
    p = argparse.ArgumentParser(description="Stage 8a — hitung params, FLOPs, ukuran file")
    p.add_argument("--checkpoint", required=True, help="Path ke checkpoint .pth model fusi")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    p.add_argument("--out", default="edge_bench/reports/params_flops.csv")
    # 224x224 dikonfirmasi dari encoder_rgb.py (DINOv2 patch14) & encoder_thermal.py
    # (tes forward asumsi 224 -> grid 14x14). Override kalau ternyata beda.
    p.add_argument("--rgb-size", type=int, nargs=2, default=[224, 224],
                    metavar=("H", "W"), help="Ukuran input RGB (H W)")
    p.add_argument("--thermal-size", type=int, nargs=2, default=[224, 224],
                    metavar=("H", "W"), help="Ukuran input thermal (H W)")
    p.add_argument("--n-tiles", type=int, default=1,
                    help="Jumlah tile/patch yang diproses per frame (1 kalau full-frame)")
    p.add_argument("--n-classes", type=int, default=3,
                    help="background/smoke/fire — sinkron dengan CLASS_LABELS di head_classification.py")
    p.add_argument("--head", default="classification", choices=["classification", "segmentation"],
                    help="Head mana yang mau dibenchmark (lihat catatan di FusionModel)")
    p.add_argument("--use-reliability-gate", action="store_true",
                    help="Set flag ini kalau checkpoint sudah dari Stage 5 (fusion_v2_gated.pth dst.). "
                         "Untuk fusion_v1.pth (Stage 2) biasanya BELUM pakai gate — jangan set flag ini.")
    p.add_argument("--strict-load", action="store_true",
                    help="Kalau di-set, error keras kalau ada key mismatch (default: warn saja & lanjut)")
    p.add_argument("--model-src", default=None,
                    help="Path ke folder src/ milik tim model (isi models/encoder_rgb.py dkk). "
                         "WAJIB diisi eksplisit. Contoh, dijalankan dari model/: "
                         "--model-src src")
    return p.parse_args()


# Path ke folder src/models/ milik tim model DITENTUKAN LEWAT ARGUMEN CLI
# (--model-src), bukan dihardcode di sini — supaya bobot dan kode model boleh
# berada di luar repositori. Path ini di-set di dalam
# build_model() setelah args di-parse, lihat fungsi di bawah.
def _setup_model_src_path(model_src: str):
    if model_src is None:
        print("[ERROR] --model-src belum diisi. Wajib diisi eksplisit, contoh:")
        print(r"        --model-src src   (dijalankan dari model/)")
        print("        (path ke folder 'src' yang di dalamnya ada folder 'models/' "
              "berisi encoder_rgb.py, encoder_thermal.py, dst.)")
        sys.exit(1)
    model_src = os.path.abspath(model_src)
    models_dir = os.path.join(model_src, "models")
    if not os.path.isdir(models_dir):
        print(f"[ERROR] Folder tidak ditemukan: {models_dir}")
        print("        Cek lagi path --model-src yang kamu kasih — pastikan di dalamnya "
              "ada subfolder 'models/' berisi encoder_rgb.py dkk.")
        sys.exit(1)
    sys.path.insert(0, model_src)
    sys.path.insert(0, models_dir)
    print(f"[INFO] Import model dari: {models_dir}")


class FusionModel(torch.nn.Module):
    """
    ⚠️ CATATAN PENTING — INI HASIL COMPOSE, BUKAN FILE ASLI ORANG A.

    Belum ada file top-level (mis. model.py atau class di train.py) yang
    menggabungkan encoder_rgb + encoder_thermal + fusion_cross_attention +
    head jadi satu class. Class di bawah ini saya susun berdasarkan 7 file
    src/models/ yang kamu kirim, dengan asumsi alur forward yang paling
    masuk akal dari dimensi tiap modul (RGBEncoder 384-dim/grid16,
    ThermalEncoder 384-dim/grid14, Fusion->768-dim, ClassificationHead
    terima 768-dim — semua nyambung).

    RISIKO: nama atribut (self.rgb_encoder, dst.) di bawah ini BELUM TENTU
    persis sama dengan yang dipakai tim model saat training/save checkpoint.
    Kalau beda, load_state_dict(strict=False) di load_checkpoint() akan
    print daftar key yang missing/unexpected — pakai daftar itu buat
    perbaiki nama atribut di __init__ ini sampai missing/unexpected = kosong.

    Yang MASIH perlu dikonfirmasi ke tim model:
      - Apakah fusion_v1.pth pakai reliability_gate (Stage 5) atau belum
        (fusion_v1 = Stage 2 = kemungkinan besar BELUM ada gate; gate baru
        masuk di fusion_v2_gated.pth) -> default di bawah: gate=None
      - Head mana yang aktif: classification (default) / segmentation /
        keduanya -> atur lewat --head
    """

    def __init__(self, n_classes: int = 3, use_reliability_gate: bool = False, head: str = "classification"):
        super().__init__()
        from encoder_rgb import RGBEncoder
        from encoder_thermal import ThermalEncoder
        from fusion_cross_attention import CrossAttentionFusion
        from modality_dropout import ModalityDropout

        self.rgb_encoder = RGBEncoder()
        self.thermal_encoder = ThermalEncoder()
        self.modality_dropout = ModalityDropout(p=0.2)  # no-op otomatis saat model.eval()
        self.fusion = CrossAttentionFusion()

        self.use_reliability_gate = use_reliability_gate
        if use_reliability_gate:
            from reliability_gate import DualReliabilityGate
            self.reliability_gate = DualReliabilityGate()

        self.head_type = head
        if head == "classification":
            from head_classification import ClassificationHead
            self.head = ClassificationHead(n_classes=n_classes)
        elif head == "segmentation":
            from head_segmentation import SegmentationHead
            self.head = SegmentationHead(n_classes=n_classes)
        else:
            raise ValueError(f"--head harus 'classification' atau 'segmentation', dapat: {head}")

    def forward(self, rgb_img: torch.Tensor, thermal_img: torch.Tensor) -> torch.Tensor:
        rgb_tokens = self.rgb_encoder(rgb_img)
        thermal_tokens = self.thermal_encoder(thermal_img)
        rgb_tokens, thermal_tokens = self.modality_dropout(rgb_tokens, thermal_tokens)

        if self.use_reliability_gate:
            r_score, t_score = self.reliability_gate(rgb_tokens, thermal_tokens)
            fused = self.fusion(rgb_tokens, thermal_tokens, r_score, t_score)
        else:
            fused = self.fusion(rgb_tokens, thermal_tokens)

        return self.head(fused)


def build_model(args):
    _setup_model_src_path(args.model_src)
    model = FusionModel(
        n_classes=getattr(args, "n_classes", 3),
        use_reliability_gate=getattr(args, "use_reliability_gate", False),
        head=getattr(args, "head", "classification"),
    )
    return model


def load_checkpoint(model, checkpoint_path, device, strict=False):
    """Load state_dict ke model.

    Mendukung 2 kemungkinan format checkpoint:
    1. Flat state_dict biasa (semua parameter dalam satu dict rata,
       key model.rgb_encoder.backbone.blocks.0..., dst.)
    2. Dict PER-SUBMODUL — setiap submodul (rgb_encoder, thermal_encoder,
       fusion, head_classification/head_segmentation, dst.) disimpan
       sebagai state_dict terpisah di bawah key masing-masing, plus
       metadata non-model (epoch, val_acc, dll). Ini format yang dipakai
       fusion_v1.pth (dikonfirmasi dari log run pertama) — auto-terdeteksi
       di bawah.
    """
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
        sd = ckpt["model_state_dict"]
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        sd = ckpt["state_dict"]
    else:
        sd = ckpt

    is_nested = isinstance(sd, dict) and any(isinstance(v, dict) for v in sd.values())

    if is_nested:
        print("[INFO] Checkpoint terdeteksi format PER-SUBMODUL (bukan flat state_dict) "
              "— load tiap submodul secara terpisah.")
        submodule_map = {
            "rgb_encoder": getattr(model, "rgb_encoder", None),
            "thermal_encoder": getattr(model, "thermal_encoder", None),
            "fusion": getattr(model, "fusion", None),
            f"head_{model.head_type}": getattr(model, "head", None),
            "reliability_gate": getattr(model, "reliability_gate", None),
        }
        metadata = {}
        any_mismatch = False
        for key, value in sd.items():
            if isinstance(value, dict):
                target = submodule_map.get(key)
                if target is None:
                    print(f"[WARN] Key checkpoint '{key}' tidak dipetakan ke submodul manapun di "
                          f"FusionModel — kemungkinan nama atribut beda, atau ini submodul yang "
                          f"belum ada di compose (mis. reliability_gate padahal --use-reliability-gate "
                          f"tidak di-set). Submodul ini TIDAK di-load.")
                    any_mismatch = True
                    continue
                sub_result = target.load_state_dict(value, strict=strict)
                sub_missing = getattr(sub_result, "missing_keys", [])
                sub_unexpected = getattr(sub_result, "unexpected_keys", [])
                if not sub_missing and not sub_unexpected:
                    print(f"[OK]   {key}: cocok 100%")
                else:
                    any_mismatch = True
                    print(f"[WARN] {key}: {len(sub_missing)} missing, {len(sub_unexpected)} unexpected")
                    for k in sub_missing[:5]:
                        print(f"         missing   : {k}")
                    for k in sub_unexpected[:5]:
                        print(f"         unexpected: {k}")
            else:
                metadata[key] = value

        if metadata:
            print(f"[INFO] Metadata checkpoint (bukan bobot model): {metadata}")

        # submodul yang ada di model tapi TIDAK disebut sama sekali di checkpoint
        model_submodules = {k for k, v in submodule_map.items() if v is not None}
        checkpoint_submodules = {k for k, v in sd.items() if isinstance(v, dict)}
        missing_entirely = model_submodules - checkpoint_submodules
        if missing_entirely:
            print(f"[WARN] Submodul ada di model tapi TIDAK ada sama sekali di checkpoint "
                  f"(masih pakai bobot random/pretrained awal): {missing_entirely}")
            any_mismatch = True

        if not any_mismatch:
            print("[OK] load_checkpoint: SEMUA SUBMODUL COCOK 100% — aman lanjut.")
        elif strict:
            raise RuntimeError("load_checkpoint gagal (strict=True) — lihat log mismatch di atas.")
        return model

    # --- fallback: flat state_dict biasa ---
    result = model.load_state_dict(sd, strict=strict)
    missing = getattr(result, "missing_keys", [])
    unexpected = getattr(result, "unexpected_keys", [])

    if not missing and not unexpected:
        print("[OK] load_state_dict: SEMUA KEY COCOK — arsitektur FusionModel "
              "match persis dengan checkpoint. Aman lanjut.")
    else:
        print(f"[WARN] load_state_dict TIDAK sepenuhnya cocok "
              f"({len(missing)} missing, {len(unexpected)} unexpected).")
        print("       Model di script ini masih HASIL COMPOSE, bukan file asli tim model.")
        if missing:
            print(f"       Missing keys (ada di model, TIDAK ada di checkpoint), contoh 10 pertama:")
            for k in missing[:10]:
                print(f"         - {k}")
        if unexpected:
            print(f"       Unexpected keys (ada di checkpoint, TIDAK ada di model), contoh 10 pertama:")
            for k in unexpected[:10]:
                print(f"         - {k}")
        print("       -> Cocokkan pola nama key di atas dengan nama atribut di class "
              "FusionModel.__init__() (mis. kalau checkpoint punya key "
              "'encoder_rgb.backbone....' tapi model kamu pakai self.rgb_encoder, "
              "ganti jadi self.encoder_rgb supaya cocok), lalu jalankan ulang.")
        if strict:
            raise RuntimeError("load_state_dict gagal (strict=True) — lihat log di atas.")
    return model


def count_params(model):
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable


def count_flops(model, dummy_inputs):
    """
    Coba beberapa library FLOPs counter, urut prioritas. Kalau semua gagal
    (belum terinstall / model punya operasi custom yang tidak didukung),
    laporkan FLOPs = None dan kasih tahu instruksi manual — jangan pura-pura
    berhasil dengan angka 0.
    """
    # 1) coba thop (paling umum dipakai, ringan)
    try:
        from thop import profile
        macs, _ = profile(model, inputs=dummy_inputs, verbose=False)
        flops = macs * 2  # 1 MAC = 2 FLOPs
        return flops, "thop"
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] thop gagal profiling: {e}")

    # 2) fallback ke fvcore (dari Facebook, biasanya lebih akurat untuk transformer)
    try:
        from fvcore.nn import FlopCountAnalysis
        flops_analyzer = FlopCountAnalysis(model, dummy_inputs)
        flops = flops_analyzer.total()
        return flops, "fvcore"
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] fvcore gagal profiling: {e}")

    print("[WARN] Tidak ada FLOPs counter yang berhasil jalan.")
    print("       Install salah satu: pip install thop --break-system-packages")
    print("                        atau: pip install fvcore --break-system-packages")
    return None, None


def main():
    args = parse_args()
    device = torch.device(args.device)

    if not os.path.isfile(args.checkpoint):
        print(f"[ERROR] Checkpoint tidak ditemukan: {args.checkpoint}")
        sys.exit(1)

    print(f"[INFO] Loading checkpoint: {args.checkpoint}")
    print(f"[INFO] RGBEncoder butuh download bobot DINOv2 via torch.hub — pastikan ada internet "
          f"di run pertama (akan di-cache lokal setelahnya).")
    model = build_model(args)
    model = load_checkpoint(model, args.checkpoint, device, strict=args.strict_load)
    model.to(device)
    model.eval()

    # --- Params ---
    total_params, trainable_params = count_params(model)
    print(f"[INFO] Total params     : {total_params:,} (~{total_params/1e6:.2f}M)")
    print(f"[INFO] Trainable params : {trainable_params:,} (~{trainable_params/1e6:.2f}M)")

    # --- Ukuran file checkpoint ---
    file_size_mb = os.path.getsize(args.checkpoint) / (1024 * 1024)
    print(f"[INFO] Ukuran file checkpoint: {file_size_mb:.2f} MB")

    # --- Dummy input untuk FLOPs ---
    # FusionModel.forward(rgb_img, thermal_img) — rgb_img (B,3,H,W), thermal_img (B,1,H,W).
    # Default 224x224 karena RGBEncoder pakai DINOv2 patch14 (224/14=16 grid) — cocok
    # dengan tes forward di encoder_thermal.py (224/16=14 grid) yang lalu dialign ke 16.
    h_rgb, w_rgb = args.rgb_size
    h_th, w_th = args.thermal_size
    dummy_rgb = torch.randn(1, 3, h_rgb, w_rgb, device=device)
    dummy_thermal = torch.randn(1, 1, h_th, w_th, device=device)
    dummy_inputs = (dummy_rgb, dummy_thermal)

    if args.n_tiles > 1:
        print(f"[INFO] n_tiles={args.n_tiles} — FLOPs di bawah ini PER TILE, "
              f"kalikan manual dengan n_tiles untuk dapat FLOPs per frame penuh.")

    flops, method = count_flops(model, dummy_inputs)
    if flops is not None:
        print(f"[INFO] FLOPs (per forward, via {method}): {flops:,} (~{flops/1e9:.3f} GFLOPs)")
    else:
        print("[INFO] FLOPs: gagal dihitung otomatis, isi manual di CSV kalau perlu.")

    # --- Simpan hasil ---
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    write_header = not os.path.isfile(args.out)
    with open(args.out, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "checkpoint", "total_params", "trainable_params", "file_size_mb",
                "flops_per_forward", "flops_method", "n_tiles", "rgb_size", "thermal_size",
            ])
        writer.writerow([
            os.path.basename(args.checkpoint), total_params, trainable_params,
            f"{file_size_mb:.2f}", flops if flops is not None else "N/A",
            method if method else "N/A", args.n_tiles,
            f"{h_rgb}x{w_rgb}", f"{h_th}x{w_th}",
        ])
    print(f"[DONE] Hasil ditambahkan ke: {args.out}")
    print("[REMINDER] Cek angka di atas masuk akal (params & FLOPs) sebelum lanjut ke "
          "01_export_onnx.py — kalau ada yang aneh (mis. 0 params), kemungkinan besar "
          "load_state_dict gagal diam-diam, cek ulang struktur checkpoint.")


if __name__ == "__main__":
    main()