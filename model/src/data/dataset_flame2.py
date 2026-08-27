"""src/data/dataset_flame2.py

Dataset loader untuk Stage 1 (pra-pelatihan encoder termal).

RIWAYAT PERBAIKAN PENTING (baca sebelum ubah file ini lagi):
Versi awal modul ini mengindex file gambar dengan cara SCAN FOLDER + tebak pola
nama file (ekstrak digit dari nama file, lalu coba versi "posisi setelah sort").
Kedua pendekatan itu SALAH -- akar masalahnya baru ketahuan setelah manifest asli
dari tim data (`flame2_train.csv`) diperiksa: nama file aslinya
`254p RGB Frame (1).jpg` -- prefix "254p" ikut ter-ekstrak jadi digit ("254" + "1"
= "2541"), bikin ID yang diekstrak SALAH TOTAL untuk hampir semua frame. Fix
"posisi setelah sort" yang dicoba berikutnya JUGA salah (sort alfabetis beda
dengan urutan angka: "(10)" tersort sebelum "(2)").

FIX YANG BENAR (dipakai di modul ini sekarang): baca `flame2_train.csv` (manifest
resmi dari tim data, Stage 0) LANGSUNG -- manifest itu sudah punya pemetaan
frame_index -> path yang pasti benar (dibuat tim data dari sumber data asli,
bukan ditebak dari nama file). Diverifikasi: 53.451 total - 440 excluded = 53.011
unique frame_index di manifest, PERSIS cocok, dan setiap frame_index punya
pasangan rgb+thermal lengkap.

ATURAN KERAS #1 -- pencegahan kebocoran evaluasi:
Dataset ini WAJIB memfilter ID yang ada di `flame2_excluded_leakage.csv` (dari tim data,
Stage 0) sebelum membentuk training split. Manifest `flame2_train.csv` SUDAH
post-exclude (diverifikasi di atas), tapi filter tetap dijalankan di sini sbg
pengaman kalau versi manifest lain di masa depan belum ter-exclude -- exclude ini
yang mencegah kebocoran evaluasi. Kalau file exclude belum ada, dataset ini
menolak dibentuk (assert), BUKAN diam-diam jalan tanpa filter -- sesuai Gerbang 1.

Label yang diproduksi SESUAI KONTRAK API (Bagian 3.4): satu label 3-kelas gabungan
("fire_smoke" | "fire_no_smoke" | "no_fire"), BUKAN dua label biner terpisah (Fire,
Smoke) -- supaya head klasifikasi Stage 1 bisa dipanggil langsung oleh inference
service tanpa konversi tambahan.
"""
from __future__ import annotations

import csv
import random
import re
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

RGB_MEAN, RGB_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]  # statistik ImageNet -- dipakai DINOv2
THERMAL_MEAN, THERMAL_STD = [0.5], [0.5]  # TODO-VERIFIKASI: ganti dgn statistik asli FLAME2 kalau sudah dihitung

CLASS_TO_IDX = {"no_fire": 0, "fire_no_smoke": 1, "fire_smoke": 2}  # HARUS sinkron dgn src/metrics.py CLASS_LABELS
IDX_TO_CLASS = {v: k for k, v in CLASS_TO_IDX.items()}

# Marker folder yang KONSISTEN ada baik di path manifest (gaya Windows, mesin lokal
# Tim data) maupun di struktur folder Kaggle -- dipakai buat "memotong" prefix path
# lokal yang tidak relevan (mis. "raw\flame2\") tanpa perlu tau persis prefix-nya.
_PATH_MARKER = "254p "


def derive_class_label(fire: int, smoke: int) -> str:
    """Gabungkan flag Fire/Smoke biner jadi satu label 3-kelas sesuai kontrak API."""
    if fire and smoke:
        return "fire_smoke"
    if fire and not smoke:
        return "fire_no_smoke"
    return "no_fire"  # termasuk kasus smoke=1,fire=0 -- dianggap no_fire per definisi label produk


def load_frame_labels_raw(labels_path: Path) -> Dict[str, Dict[str, int]]:
    """Parse `Frame Pair Labels.txt` FLAME2 asli -- format per BLOK rentang frame,
    dipisah tab, flag Y/N nempel tanpa spasi: '<first>\\t<last>\\t<FireFlag><SmokeFlag>'.
    Baris header/deskripsi otomatis dilewati (tidak match pola)."""
    pattern = re.compile(r"^\s*(\d+)\s+(\d+)\s+([YyNn])([YyNn])")
    labels: Dict[str, Dict[str, int]] = {}
    with open(labels_path, encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line)
            if not m:
                continue
            first, last, fire_flag, smoke_flag = m.groups()
            fire = 1 if fire_flag.upper() == "Y" else 0
            smoke = 1 if smoke_flag.upper() == "Y" else 0
            for idx in range(int(first), int(last) + 1):
                labels[str(idx)] = {"fire": fire, "smoke": smoke}
    return labels


def load_flame2_manifest(manifest_path: Path) -> Dict[str, Dict[str, str]]:
    """Baca flame2_train.csv (manifest RESMI dari tim data, Stage 0). Kolom yang
    dipakai: `frame_index`, `modality` (nilainya "rgb" atau "thermal" utk FLAME2 --
    BEDA dari manifest RFFNet yang pakai "ir", jangan disamakan), `path`.

    Return: {frame_index: {"rgb": path_mentah, "thermal": path_mentah}} -- path
    MASIH mentah (gaya Windows, relatif ke mesin lokal tim data), belum di-resolve
    ke lokasi Kaggle. Pakai resolve_manifest_path() buat itu."""
    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows, f"Manifest kosong: {manifest_path}"

    required_cols = {"frame_index", "modality", "path"}
    missing = required_cols - set(rows[0].keys())
    assert not missing, (
        f"Kolom wajib tidak ada di {manifest_path}: {missing}. Header asli: {list(rows[0].keys())}. "
        "Format manifest mungkin berubah -- sesuaikan load_flame2_manifest()."
    )

    by_frame: Dict[str, Dict[str, str]] = {}
    for row in rows:
        by_frame.setdefault(row["frame_index"], {})[row["modality"]] = row["path"]

    # buang frame yang tidak punya pasangan rgb+thermal lengkap (defensif -- di
    # data yang sudah diverifikasi, ini harusnya 0, tapi jangan asumsikan manifest
    # masa depan selalu selengkap ini)
    complete = {fid: d for fid, d in by_frame.items() if "rgb" in d and "thermal" in d}
    dropped = len(by_frame) - len(complete)
    if dropped:
        print(f"[dataset_flame2] PERINGATAN: {dropped} frame_index di manifest tidak "
              f"punya pasangan rgb+thermal lengkap, dibuang.")
    return complete


def resolve_manifest_path(raw_path: str, dataset_root: Path) -> Path:
    """Manifest pakai path relatif gaya Windows dari mesin lokal tim data, mis.
    'raw\\flame2\\254p RGB Images\\254p RGB Frame (1).jpg'. Prefix sebelum '254p '
    (mis. 'raw\\flame2\\') itu struktur folder LOKAL tim data, tidak ada relevansinya
    di Kaggle -- dipotong, sisanya di-join ke dataset_root (folder Kaggle yang
    langsung berisi '254p RGB Images/' dan '254p Thermal Images/')."""
    normalized = raw_path.replace("\\", "/")
    idx = normalized.find(_PATH_MARKER)
    assert idx >= 0, (
        f"Path manifest tidak mengandung marker '{_PATH_MARKER}': {raw_path!r} -- "
        "struktur path manifest mungkin berubah, sesuaikan resolve_manifest_path()."
    )
    relative = normalized[idx:]
    return dataset_root / relative


def load_excluded_ids(excluded_csv_path: Path) -> set:
    """Baca flame2_excluded_leakage.csv (dari tim data, Stage 0) -> set frame_id (str).
    Kolom pertama dikonfirmasi bernama `frame_index` (diverifikasi dari file asli)."""
    assert excluded_csv_path.exists(), (
        f"WAJIB: {excluded_csv_path} belum ada. Tidak boleh "
        "mulai training sebelum file exclude ini tersedia dari tim data. Jangan bypass ini."
    )
    with open(excluded_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        id_col = reader.fieldnames[0]  # dikonfirmasi = "frame_index" di file asli
        excluded = {row[id_col].strip() for row in reader}
    return excluded


class PairedAugment:
    """Augmentasi geometris IDENTIK di RGB & termal -- wajib sama persis (Bagian 3.2
    concept paper: alignment spasial harus terjaga)."""

    def __init__(self, train: bool, image_size: int = 224):
        self.train = train
        self.image_size = image_size

    def __call__(self, rgb_img: Image.Image, thermal_img: Image.Image):
        if self.train:
            if random.random() < 0.5:
                rgb_img = rgb_img.transpose(Image.FLIP_LEFT_RIGHT)
                thermal_img = thermal_img.transpose(Image.FLIP_LEFT_RIGHT)
            angle = random.uniform(-10, 10)
            rgb_img = rgb_img.rotate(angle)
            thermal_img = thermal_img.rotate(angle)
        rgb_img = rgb_img.resize((self.image_size, self.image_size))
        thermal_img = thermal_img.resize((self.image_size, self.image_size))
        return rgb_img, thermal_img


class FLAME2ClassificationDataset(Dataset):
    """Stage 1: RGB+termal berpasangan -> label 3-kelas (fire_smoke/fire_no_smoke/no_fire).

    WAJIB dipanggil lewat `build_flame2_datasets()` di bawah, bukan diinstansiasi manual,
    supaya filter exclude & resolusi path manifest selalu diterapkan konsisten.
    """

    def __init__(
        self,
        frame_ids: List[str],
        labels: Dict[str, Dict[str, int]],
        rgb_paths: Dict[str, Path],
        thermal_paths: Dict[str, Path],
        train: bool,
        image_size: int = 224,
    ):
        self.frame_ids = frame_ids
        self.labels = labels
        self.rgb_paths = rgb_paths
        self.thermal_paths = thermal_paths
        self.augment = PairedAugment(train, image_size)
        self.rgb_norm = T.Compose([T.ToTensor(), T.Normalize(RGB_MEAN, RGB_STD)])
        self.thermal_norm = T.Compose([T.ToTensor(), T.Normalize(THERMAL_MEAN, THERMAL_STD)])

    def __len__(self) -> int:
        return len(self.frame_ids)

    def __getitem__(self, idx: int):
        fid = self.frame_ids[idx]
        rgb = Image.open(self.rgb_paths[fid]).convert("RGB")
        thermal = Image.open(self.thermal_paths[fid]).convert("L")
        rgb, thermal = self.augment(rgb, thermal)
        rgb_t = self.rgb_norm(rgb)
        thermal_t = self.thermal_norm(thermal)
        lbl = self.labels[fid]
        class_name = derive_class_label(lbl["fire"], lbl["smoke"])
        target = torch.tensor(CLASS_TO_IDX[class_name], dtype=torch.long)
        return rgb_t, thermal_t, target


def frame_id_to_video(frame_id: str, video_frame_ranges: Dict[int, Tuple[int, int]]) -> int:
    """Defensif thd batas rentang (off-by-one pernah kejadian di produksi): idx di
    luar semua rentang otomatis di-clamp ke video PERTAMA (kalau di bawah batas
    terendah) atau video TERAKHIR (kalau di atas/persis di batas tertinggi),
    bukan crash. Ini defensif thd VIDEO_FRAME_RANGES yang memang masih placeholder
    (lihat DEFAULT_VIDEO_FRAME_RANGES di bawah, TODO-VERIFIKASI)."""
    idx = int(frame_id)
    for vid, (lo, hi) in video_frame_ranges.items():
        if lo <= idx < hi:
            return vid
    min_vid = min(video_frame_ranges.keys(), key=lambda v: video_frame_ranges[v][0])
    max_vid = max(video_frame_ranges.keys(), key=lambda v: video_frame_ranges[v][1])
    if idx < video_frame_ranges[min_vid][0]:
        return min_vid
    return max_vid


def split_by_scene(
    frame_ids: List[str], video_frame_ranges: Dict[int, Tuple[int, int]], val_fraction: float = 0.1, seed: int = 42
):
    """Split train/val di level VIDEO. DIPERTAHANKAN untuk rujukan, tetapi
    TIDAK dipakai lagi pada FLAME 2 karena menghasilkan validasi berkelas
    tunggal. Lihat split_by_block() dan penjelasannya."""
    by_video: Dict[int, List[str]] = {}
    for fid in frame_ids:
        by_video.setdefault(frame_id_to_video(fid, video_frame_ranges), []).append(fid)

    video_ids = sorted(by_video.keys())
    rng = random.Random(seed)
    rng.shuffle(video_ids)
    n_val = max(1, round(len(video_ids) * val_fraction))
    val_videos = set(video_ids[:n_val])

    train_ids, val_ids = [], []
    for vid, fids in by_video.items():
        (val_ids if vid in val_videos else train_ids).extend(fids)
    return train_ids, val_ids, val_videos


def split_by_block(
    frame_ids: List[str],
    frame_labels: Dict[str, str],
    video_frame_ranges: Dict[int, Tuple[int, int]],
    val_fraction: float = 0.1,
    seed: int = 42,
    block_size: int = 250,
    buffer_size: int = 50,
):
    """[PATCH P6] Split terstratifikasi berbasis blok bingkai berurutan.

    KENAPA BUKAN PER VIDEO. Pada FLAME 2, api dinyalakan di antara video 2 dan
    video 3. Akibatnya kelas no_fire hanya ada pada video 1-2 (13.699 bingkai,
    seluruhnya no_fire) dan kelas berapi hanya pada video 3-7 (39.752 bingkai,
    hanya 1 di antaranya no_fire). Kelas terkonfound sempurna dengan urutan
    perekaman, sehingga split per-video pasti menghasilkan validasi berkelas
    tunggal dan val_acc yang tidak dapat ditafsirkan.

    CARA KERJA.
      1. Bingkai dipotong menjadi blok berurutan berukuran `block_size`, dan
         blok TIDAK PERNAH melintasi batas video.
      2. Tiap blok diberi label mayoritas isinya.
      3. Blok dipilih ke validasi secara terstratifikasi per kelas, sehingga
         ketiga kelas dijamin hadir di kedua sisi.
      4. `buffer_size` bingkai di kedua sisi tiap blok validasi DIBUANG dari
         latih, supaya bingkai berdekatan yang nyaris identik tidak bocor.

    Yang tersisa sebagai keterbatasan dan wajib dinyatakan: bingkai di dalam
    satu blok tetap sangat berkorelasi, sehingga val_acc di sini mengukur
    generalisasi antar-segmen rekaman, bukan antar-lokasi kebakaran.
    """
    # [PERBAIKAN] build_flame2_datasets mengoper label MENTAH berbentuk
    # {fid: {"fire": 0/1, "smoke": 0/1}}, bukan string kelas. Normalkan dulu,
    # sekaligus tetap menerima bentuk yang sudah berupa string.
    kelas_per_fid: Dict[str, str] = {}
    for f in frame_ids:
        lbl = frame_labels[f]
        kelas_per_fid[f] = (lbl if isinstance(lbl, str)
                            else derive_class_label(lbl["fire"], lbl["smoke"]))
    frame_labels = kelas_per_fid

    urut = sorted(frame_ids, key=int)
    per_video: Dict[int, List[str]] = {}
    for fid in urut:
        per_video.setdefault(frame_id_to_video(fid, video_frame_ranges), []).append(fid)

    blok = []  # (video, indeks_blok, [fid...], kelas_mayoritas)
    for vid, fids in sorted(per_video.items()):
        for i in range(0, len(fids), block_size):
            potong = fids[i:i + block_size]
            if len(potong) < block_size // 2:      # sisa terlalu pendek, gabung ke blok sebelumnya
                if blok and blok[-1][0] == vid:
                    blok[-1][2].extend(potong)
                    continue
            hitung: Dict[str, int] = {}
            for f in potong:
                hitung[frame_labels[f]] = hitung.get(frame_labels[f], 0) + 1
            blok.append([vid, i // block_size, potong, max(hitung, key=hitung.get)])

    for b in blok:
        hitung = {}
        for f in b[2]:
            hitung[frame_labels[f]] = hitung.get(frame_labels[f], 0) + 1
        b[3] = max(hitung, key=hitung.get)

    per_kelas: Dict[str, List[int]] = {}
    for idx, b in enumerate(blok):
        per_kelas.setdefault(b[3], []).append(idx)

    rng = random.Random(seed)
    val_blok = set()
    for kelas, idxs in sorted(per_kelas.items()):
        acak = list(idxs)
        rng.shuffle(acak)
        n = max(1, round(len(acak) * val_fraction))
        val_blok.update(acak[:n])

    val_ids, val_int = [], set()
    for idx in val_blok:
        for f in blok[idx][2]:
            val_ids.append(f)
            val_int.add(int(f))

    # penyangga: buang bingkai latih yang terlalu dekat dengan blok validasi
    zona = set()
    for i in val_int:
        for d in range(-buffer_size, buffer_size + 1):
            zona.add(i + d)

    train_ids, dibuang = [], 0
    for idx, b in enumerate(blok):
        if idx in val_blok:
            continue
        for f in b[2]:
            if int(f) in zona:
                dibuang += 1
            else:
                train_ids.append(f)

    ringkas: Dict[str, Dict[str, int]] = {"train": {}, "val": {}}
    for f in train_ids:
        k = frame_labels[f]; ringkas["train"][k] = ringkas["train"].get(k, 0) + 1
    for f in val_ids:
        k = frame_labels[f]; ringkas["val"][k] = ringkas["val"].get(k, 0) + 1

    print(f"[dataset_flame2][P6] blok={len(blok)} (ukuran {block_size}, penyangga {buffer_size})")
    print(f"[dataset_flame2][P6] train={len(train_ids)}  val={len(val_ids)}  "
          f"dibuang sebagai penyangga={dibuang}")
    print(f"[dataset_flame2][P6] distribusi train: {ringkas['train']}")
    print(f"[dataset_flame2][P6] distribusi val  : {ringkas['val']}")

    n_kelas_val = sum(1 for v in ringkas["val"].values() if v > 0)
    assert n_kelas_val >= 2, (
        f"validasi hanya memuat {n_kelas_val} kelas. val_acc tidak akan bermakna. "
        "Turunkan block_size atau naikkan val_fraction."
    )
    return train_ids, val_ids, sorted({b[0] for i, b in enumerate(blok) if i in val_blok})


def build_flame2_datasets(
    labels_path: Path,
    manifest_path: Path,
    dataset_root: Path,
    excluded_csv_path: Path,
    video_frame_ranges: Dict[int, Tuple[int, int]],
    val_fraction: float = 0.1,
    seed: int = 42,
    image_size: int = 224,
) -> Tuple[FLAME2ClassificationDataset, FLAME2ClassificationDataset]:
    """Entry point utama modul ini -- bangun train/val dataset Stage 1 dengan SEMUA
    aturan wajib diterapkan (baca manifest resmi tim data, exclude leakage, split
    per-scene). GANTI dari versi sebelumnya: parameter `rgb_dir`/`thermal_dir`
    (scan folder + tebak nama file) diganti `manifest_path`/`dataset_root` (baca
    manifest resmi -- lihat riwayat perbaikan di docstring modul ini).
    """
    frame_labels = load_frame_labels_raw(labels_path)
    manifest = load_flame2_manifest(manifest_path)
    print(f"[dataset_flame2] Manifest: {len(manifest)} frame_index dgn pasangan rgb+thermal lengkap")

    excluded = load_excluded_ids(excluded_csv_path)
    before_exclude = len(frame_labels)
    frame_labels = {fid: lbl for fid, lbl in frame_labels.items() if fid not in excluded}
    print(f"[dataset_flame2] Exclude leakage: {before_exclude} -> {len(frame_labels)} "
          f"({before_exclude - len(frame_labels)} frame dibuang, cocok dgn flame2_excluded_leakage.csv)")

    before_filter = len(frame_labels)
    frame_labels = {fid: lbl for fid, lbl in frame_labels.items() if fid in manifest}
    print(f"[dataset_flame2] Filter ke frame yg ada di manifest: {before_filter} -> {len(frame_labels)}")
    # PENTING: cek FRAKSI yang tersisa, bukan cuma > 0 -- bug nyata pernah kejadian
    # (99/53451 frame overlap gara-gara ekstraksi digit dari nama file salah).
    # Threshold 80% dipilih longgar, tapi cukup ketat utk menangkap kegagalan
    # pairing kalau format manifest berubah lagi di masa depan.
    retained_fraction = len(frame_labels) / before_filter if before_filter > 0 else 0
    assert retained_fraction > 0.8, (
        f"Cuma {retained_fraction*100:.1f}% frame tersisa setelah filter ke manifest "
        f"({len(frame_labels)}/{before_filter}) -- ini tanda ketidakcocokan frame_index "
        "antara Frame Pair Labels.txt dan flame2_train.csv. JANGAN lanjut training, "
        "cek ulang kedua sumber data ini."
    )

    rgb_paths = {fid: resolve_manifest_path(manifest[fid]["rgb"], dataset_root) for fid in frame_labels}
    thermal_paths = {fid: resolve_manifest_path(manifest[fid]["thermal"], dataset_root) for fid in frame_labels}

    train_ids, val_ids, val_videos = split_by_block(   # [PATCH P6]
        list(frame_labels.keys()), frame_labels, video_frame_ranges, val_fraction, seed
    )
    print(f"[dataset_flame2] Split per-scene: train={len(train_ids)}  val={len(val_ids)}  "
          f"(video di val: {sorted(val_videos)})")

    train_set = FLAME2ClassificationDataset(train_ids, frame_labels, rgb_paths, thermal_paths, True, image_size)
    val_set = FLAME2ClassificationDataset(val_ids, frame_labels, rgb_paths, thermal_paths, False, image_size)
    return train_set, val_set


# TODO-VERIFIKASI: batas index frame per video BELUM dikonfirmasi -- ambil dari
# README FLAME 2 (Item #11/#12) sebelum training beneran. Placeholder di bawah
# proporsional terhadap total ~53.451 frame, BUKAN angka asli.
# [PATCH P5] Batas video NYATA, direkonstruksi 23 Agustus 2026.
#
# Versi sebelumnya berisi angka karangan bertanda TODO-VERIFIKASI, dan itu
# membelah data latih/validasi Stage 1 sehingga val_acc-nya tidak dapat
# ditafsirkan. Rekonstruksi ini memakai dua sumber yang saling menguatkan:
#
#   1. README FLAME 2 item #8 menyatakan 13.700 bingkai RGB beresolusi
#      3840x2160 dan 39.751 beresolusi 1920x1080. Dari item #1-#7, hanya
#      video 1 dan 2 yang 4K, jadi bingkai 1..13.700 = video 1+2. Angka ini
#      juga cocok persis dengan akhir segmen label pertama.
#   2. Batas per video diprediksi proporsional terhadap durasi README di
#      dalam tiap kelompok resolusi, lalu dipasangkan ke diskontinuitas
#      antar-bingkai terdekat yang terdeteksi pada citra 254p.
#      Lihat analisis/04_deteksi_batas_video.py.
#
# Verifikasi: total 53.451 bingkai persis; video 1+2 = 13.699 (meleset satu
# karena konvensi batas setengah terbuka); FPS efektif ketujuh video berada
# di 26,86 sampai 30,09, konsisten dengan sumber 30 FPS.
#
# Catatan kejujuran: batas 33.930 berimpit dengan transisi label, sehingga
# hanya batas itu yang tidak dapat dipastikan murni potongan video. Lima
# batas lainnya jatuh di dalam segmen label homogen.
DEFAULT_VIDEO_FRAME_RANGES = {
    1: (1, 8601), 2: (8601, 13700), 3: (13700, 25696), 4: (25696, 33930),
    5: (33930, 41101), 6: (41101, 46260), 7: (46260, 53452),
}


if __name__ == "__main__":
    # Sanity check logic tanpa data asli.
    assert derive_class_label(1, 1) == "fire_smoke"
    assert derive_class_label(1, 0) == "fire_no_smoke"
    assert derive_class_label(0, 0) == "no_fire"
    assert derive_class_label(0, 1) == "no_fire"
    print("Tes derive_class_label: OK")

    ranges = {1: (0, 100), 2: (100, 200)}
    assert frame_id_to_video("50", ranges) == 1
    assert frame_id_to_video("150", ranges) == 2
    assert frame_id_to_video("200", ranges) == 2, "idx persis di batas atas tertinggi harus masuk video terakhir"
    assert frame_id_to_video("500", ranges) == 2, "idx jauh di atas semua rentang harus tetap masuk video terakhir"
    assert frame_id_to_video("0", ranges) == 1, "idx di bawah batas terendah harus masuk video pertama"
    print("Tes frame_id_to_video (termasuk boundary): OK")

    # Tes resolve_manifest_path dgn contoh PERSIS dari flame2_train.csv asli
    raw = "raw\\flame2\\254p RGB Images\\254p RGB Frame (1).jpg"
    resolved = resolve_manifest_path(raw, Path("/kaggle/input/flame2-254p-rgb-thermal"))
    expected = Path("/kaggle/input/flame2-254p-rgb-thermal/254p RGB Images/254p RGB Frame (1).jpg")
    assert resolved == expected, f"{resolved} != {expected}"
    print("Tes resolve_manifest_path: OK ->", resolved)

    # Tes load_flame2_manifest dgn manifest tiruan (format persis kolom asli)
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "frame_index", "modality", "path", "split"])
        writer.writerow(["flame2_rgb_1", "1", "rgb", "raw\\flame2\\254p RGB Images\\254p RGB Frame (1).jpg", "train"])
        writer.writerow(["flame2_thermal_1", "1", "thermal", "raw\\flame2\\254p Thermal Images\\254p Thermal Frame (1).jpg", "train"])
        writer.writerow(["flame2_rgb_2", "2", "rgb", "raw\\flame2\\254p RGB Images\\254p RGB Frame (2).jpg", "train"])
        writer.writerow(["flame2_thermal_2", "2", "thermal", "raw\\flame2\\254p Thermal Images\\254p Thermal Frame (2).jpg", "train"])
        # frame 3 SENGAJA cuma ada rgb (tidak lengkap) -- harus dibuang otomatis
        writer.writerow(["flame2_rgb_3", "3", "rgb", "raw\\flame2\\254p RGB Images\\254p RGB Frame (3).jpg", "train"])
        tmp_path = Path(f.name)
    manifest = load_flame2_manifest(tmp_path)
    assert set(manifest.keys()) == {"1", "2"}, manifest.keys()
    assert manifest["1"]["rgb"].endswith("Frame (1).jpg")
    tmp_path.unlink()
    print("Tes load_flame2_manifest (termasuk buang frame tidak lengkap): OK ->", manifest)

    print("\nSemua sanity check src/data/dataset_flame2.py LOLOS (tanpa data asli).")
