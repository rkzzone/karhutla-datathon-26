"""Stage 10 — jalankan model fusi ke frame terpilih, hasilkan alert nyata.

Ini menggantikan `sample_predictions.json` mock dengan keluaran model sungguhan:
`prediction`, `modality_reliability`, dan `localization` seluruhnya berasal dari
`fusion_v3_localization.pth`, bukan angka karangan.

Dijalankan SEKALI, hasilnya di-commit. Bukan dipanggil saat runtime — untuk demo
yang harus stabil dan bisa diulang, batch offline jauh lebih aman daripada
bergantung pada layanan inference yang hidup saat rekaman.

    python backend/scripts/jalankan_inference.py

Praproses disalin persis dari `src/data/dataset_rffnet.py` milik tim model
(resize 224, ImageNet mean/std untuk RGB, 0.5/0.5 untuk termal). Kalau praproses
di sisi tim model berubah, ubah juga di sini — kalau tidak, angka yang tampil di UI
tidak akan cocok dengan angka di Halaman 4.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms as T

warnings.filterwarnings('ignore')

AKAR = Path(__file__).resolve().parents[2]
# Bobot model tidak disimpan di repositori ini (lihat README akar) — unduh dari
# Hugging Face, taruh di `model/weights/`, atau tunjuk lewat env MODEL_DIR.
MODEL_DIR = Path(os.environ.get('MODEL_DIR') or AKAR / 'model' / 'weights')
CHECKPOINT = MODEL_DIR / 'weights_final/fusion_v3_localization.pth'
FRAME_JSON = AKAR / 'backend/app/mock_data/frame_provenance.json'
SAMPLES = AKAR / 'frontend/public/media/samples'
HEATMAPS = AKAR / 'frontend/public/media/heatmaps'
KELUAR = AKAR / 'backend/app/mock_data/sample_predictions.json'

sys.path.insert(0, str(MODEL_DIR))

from src.models.encoder_rgb import RGBEncoder  # noqa: E402
from src.models.encoder_thermal import ThermalEncoder  # noqa: E402
from src.models.fusion_cross_attention import CrossAttentionFusion  # noqa: E402
from src.models.head_classification import CLASS_LABELS, ClassificationHead  # noqa: E402
from src.models.head_segmentation import SegmentationHead  # noqa: E402
from src.models.reliability_gate import DualReliabilityGate  # noqa: E402

UKURAN = 224
RGB_MEAN, RGB_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
TRM_MEAN, TRM_STD = [0.5], [0.5]

WIB = timezone(timedelta(hours=7))

# ---------------------------------------------------------------------------
# Lokasi penempatan.
#
# Citra FLAME2 direkam di hutan pinus Arizona, BUKAN gambut Indonesia. Koordinat
# di bawah adalah lokasi patroli/sensor tempat konsol ini disimulasikan bekerja —
# model dan seluruh angkanya nyata, penempatan geografisnya simulasi.
# UI menandai setiap bingkai dengan sumber datasetnya supaya tidak ada yang
# mengira ini citra lapangan Indonesia.
#
# Model tidak menghasilkan koordinat; sampai ada perangkat/telemetri yang
# memasoknya, pemetaan ini yang dipakai. Lihat CHANGELOG 2026-08-08.
# ---------------------------------------------------------------------------
LOKASI = [
    (-2.7148, 114.2213, 'satellite_firms', 'Pulang Pisau, Kalteng'),
    (-3.3821, 105.4467, 'iot_ground', 'Ogan Komering Ilir, Sumsel'),
    (-1.5602, 103.6011, 'satellite_firms', 'Muaro Jambi, Jambi'),
    (1.4854, 102.1032, 'patrol_scheduled', 'Bengkalis, Riau'),
    (-0.2913, 109.4204, 'satellite_firms', 'Kubu Raya, Kalbar'),
    (-2.1044, 113.4008, 'patrol_scheduled', 'Katingan, Kalteng'),
    (0.8123, 101.9155, 'iot_ground', 'Siak, Riau'),
    (-2.6301, 114.0955, 'iot_ground', 'Pulang Pisau utara, Kalteng'),
    (-3.4110, 105.3902, 'satellite_firms', 'OKI selatan, Sumsel'),
    (-1.6015, 103.6533, 'patrol_scheduled', 'Muaro Jambi timur, Jambi'),
]

# Ramp Ironbow — HARUS sama dengan DESIGN_BRIEF Bagian 2.3 dan bg-ironbow.
RAMP = [(0.0, (107, 98, 89)), (0.38, (193, 57, 43)), (0.70, (232, 117, 44)), (1.0, (245, 194, 66))]


def warna_ramp(t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    for i in range(len(RAMP) - 1):
        t0, c0 = RAMP[i]
        t1, c1 = RAMP[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return tuple(round(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
    return RAMP[-1][1]


def muat_model(device):
    ck = torch.load(CHECKPOINT, map_location=device, weights_only=False)
    rgb_enc, trm_enc = RGBEncoder().to(device), ThermalEncoder().to(device)
    fusion, head = CrossAttentionFusion().to(device), ClassificationHead().to(device)
    gate, seg = DualReliabilityGate().to(device), SegmentationHead().to(device)
    rgb_enc.load_state_dict(ck['rgb_encoder'])
    trm_enc.load_state_dict(ck['thermal_encoder'])
    fusion.load_state_dict(ck['fusion'])
    head.load_state_dict(ck['head_classification'])
    gate.load_state_dict(ck['gate'])
    seg.load_state_dict(ck['segmentation_head'])
    for m in (rgb_enc, trm_enc, fusion, head, gate, seg):
        m.eval()
    return rgb_enc, trm_enc, fusion, head, gate, seg


norm_rgb = T.Compose([T.ToTensor(), T.Normalize(RGB_MEAN, RGB_STD)])
norm_trm = T.Compose([T.ToTensor(), T.Normalize(TRM_MEAN, TRM_STD)])


def siapkan(path_rgb: Path, path_trm: Path, device):
    rgb = Image.open(path_rgb).convert('RGB').resize((UKURAN, UKURAN))
    trm = Image.open(path_trm).convert('L').resize((UKURAN, UKURAN))
    return (norm_rgb(rgb).unsqueeze(0).to(device), norm_trm(trm).unsqueeze(0).to(device))


# Ambang persentil untuk mengubah peta jadi overlay. Nilainya mengikuti
# `configs/stage6_localization.yaml` milik tim model (threshold_percentile: 90).
#
# Ini bukan pemanis: sigmoid keluaran segmentation head punya median ~0.69, jadi
# lebih dari separuh bingkai terbaca "panas". Tanpa ambang, overlay menutupi
# seluruh citra dan justru tidak melokalisasi apa pun — operator kehilangan
# konteks visual tanpa mendapat informasi apa-apa sebagai gantinya.
PERSENTIL = 0.90


def tulis_heatmap(peta: torch.Tensor, tujuan: Path) -> None:
    """Simpan peta atensi jadi PNG RGBA memakai ramp Ironbow.

    Di bawah ambang persentil, alpha = 0 (benar-benar transparan). Di atasnya,
    nilai di-rescale ke [0,1] sehingga gradasi Ironbow terpakai penuh hanya pada
    area yang benar-benar menonjol.
    """
    p = peta.detach().cpu()
    ambang = float(torch.quantile(p.flatten(), PERSENTIL))
    p = ((p - ambang) / (p.max() - ambang + 1e-8)).clamp(0.0, 1.0)
    h, w = p.shape
    img = Image.new('RGBA', (w, h))
    piksel = img.load()
    for y in range(h):
        for x in range(w):
            v = float(p[y, x])
            if v <= 0.0:
                continue  # di bawah ambang: biarkan citra dasar terlihat utuh
            r, g, b = warna_ramp(v)
            piksel[x, y] = (r, g, b, int(255 * min(1.0, 0.25 + 0.75 * v)))
    img.resize((448, 448), Image.BILINEAR).save(tujuan, 'PNG', optimize=True)


def main() -> None:
    device = torch.device('cpu')
    print(f'memuat {CHECKPOINT.name} …')
    rgb_enc, trm_enc, fusion, head, gate, seg = muat_model(device)
    HEATMAPS.mkdir(parents=True, exist_ok=True)

    frames = json.loads(FRAME_JSON.read_text(encoding='utf-8'))
    dasar = datetime(2026, 8, 8, 8, 40, tzinfo=WIB)
    alerts, cocok = [], 0

    for i, fr in enumerate(frames):
        rgb, trm = siapkan(SAMPLES / Path(fr['rgb']).name, SAMPLES / Path(fr['thermal']).name, device)
        with torch.no_grad():
            tok_rgb, tok_trm = rgb_enc(rgb), trm_enc(trm)
            r_rgb, r_trm = gate(tok_rgb, tok_trm)
            fused = fusion(tok_rgb, tok_trm, r_rgb, r_trm)
            logits = head(fused)
            prob = torch.softmax(logits, dim=-1)[0]
            idx = int(prob.argmax())
            seg_logit = seg(fused)[0]

        label = CLASS_LABELS[idx]
        conf = round(float(prob[idx]), 4)
        rel_rgb, rel_trm = round(float(r_rgb[0]), 4), round(float(r_trm[0]), 4)
        cocok += label == fr['kelas_label']

        # Peta atensi hanya bermakna kalau model memang melihat api.
        heatmap_path = None
        metode = None
        if label != 'no_fire':
            # Kanal kelas yang DIPREDIKSI, bukan maksimum lintas kelas — yang
            # ingin ditunjukkan ke operator adalah "di mana model melihat hal
            # yang ia putuskan", bukan "di mana ada sesuatu".
            kanal = seg_logit[idx] if seg_logit.shape[0] > idx else seg_logit[-1]
            nama = f"attn_{fr['urut']:03d}.png"
            tulis_heatmap(torch.sigmoid(kanal), HEATMAPS / nama)
            heatmap_path, metode = f'heatmaps/{nama}', 'segmentation_head'

        lat, lon, pemicu, _ = LOKASI[i % len(LOKASI)]
        alerts.append({
            'alert_id': str(uuid.uuid5(uuid.NAMESPACE_URL, f"karhutla/frame/{fr['frame_index']}")),
            'timestamp': (dasar - timedelta(minutes=17 * i)).isoformat(timespec='seconds'),
            'location': {'lat': lat, 'lon': lon},
            'prediction': {'label': label, 'confidence': conf},
            'modality_reliability': {'rgb': rel_rgb, 'thermal': rel_trm},
            'localization': {'heatmap_path': heatmap_path, 'method': metode},
            'images': {'rgb_url': fr['rgb'], 'thermal_url': fr['thermal']},
            'source_trigger': pemicu,
            'operator_decision': None,
        })
        # ASCII saja: konsol Windows default cp1252 dan akan crash pada glif Unicode.
        tanda = 'OK  ' if label == fr['kelas_label'] else 'BEDA'
        print(f"  {fr['urut']:2}. frame {fr['frame_index']:>6}  label={label:14} conf={conf:.4f}  "
              f"rgb={rel_rgb:.3f} trm={rel_trm:.3f}  {tanda} (acuan {fr['kelas_label']})")

    alerts.sort(key=lambda a: a['prediction']['confidence'], reverse=True)
    KELUAR.write_text(json.dumps(alerts, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    # Penanda sumber untuk deployment statis (Vercel), yang tidak punya backend
    # untuk ditanyai. Tanpa ini, header di sana melapor "mock" padahal angkanya
    # keluaran model — persis kebohongan yang sudah diperbaiki di sisi backend.
    # Ditulis oleh skrip ini supaya otomatis benar: kalau seseorang kembali ke
    # data karangan tanpa menjalankan skrip ini, berkasnya tidak ikut berubah.
    status = {
        'sumber': 'batch',
        'model_service_url': None,
        'batch': {
            'jumlah_bingkai': len(alerts),
            'checkpoint': CHECKPOINT.name,
            'dataset': 'FLAME2 254p — split RFFNet val',
        },
    }
    (AKAR / 'frontend/public/mock/status_sumber.json').write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'\n{len(alerts)} alert ditulis ke {KELUAR.relative_to(AKAR)}')
    print(f'cocok dengan label acuan FLAME2: {cocok}/{len(frames)}')


if __name__ == '__main__':
    main()
