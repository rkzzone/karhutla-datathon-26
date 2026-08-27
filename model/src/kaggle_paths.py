"""src/kaggle_paths.py

Satu fungsi utilitas: muat configs/kaggle_paths.yaml (SATU-SATUNYA sumber path
Kaggle asli, lihat file itu) dan timpa field data/model yang relevan di config
stage manapun. Dipanggil dari tiap notebook_kaggle SEBELUM train_stageN()/
run_stageN() -- jadi path Kaggle cuma diedit di SATU tempat, bukan di 6 file
configs/stage*.yaml + 6 notebook terpisah.

Pemakaian di notebook:
    from src.kaggle_paths import load_kaggle_paths, apply_kaggle_paths
    kp = load_kaggle_paths(REPO_PATH)
    config = apply_kaggle_paths(config, kp)
"""
from __future__ import annotations

from pathlib import Path

import yaml


def load_kaggle_paths(repo_path: str) -> dict:
    path = Path(repo_path, "configs", "kaggle_paths.yaml")
    assert path.exists(), (
        f"{path} tidak ada -- ini SATU-SATUNYA sumber path Kaggle, harus ada di repo. "
        "Kalau kehapus, salin ulang dari template di CHANGELOG.md atau minta ke tim."
    )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_kaggle_paths(config: dict, kp: dict) -> dict:
    """Timpa field data/model config stage berdasar nomor stage, pakai isi
    kaggle_paths.yaml. Return config yang sama (dimutasi in-place, juga di-return
    utk kenyamanan chaining)."""
    stage = config["stage"]
    d = config.setdefault("data", {})
    m = config.setdefault("model", {})

    if stage == 1:
        d["dataset_root"] = kp["flame2_53k"]["dataset_root"]
        d["labels_path"] = kp["flame2_53k"]["labels_path"]
        d["manifest_path"] = kp["orang_c_manifests"]["flame2_train"]
        d["excluded_csv"] = kp["orang_c_manifests"]["excluded_csv"]

    elif stage == 2:
        d["rffnet_root"] = kp["rffnet"]["root"]
        m["pretrained_thermal_encoder"] = kp["checkpoints"]["thermal_encoder_pretrained"]

    elif stage == 4:
        d["rffnet_root"] = kp["rffnet"]["root"]
        m["checkpoint"] = kp["checkpoints"]["fusion_v1"]

    elif stage == 5:
        d["rffnet_root"] = kp["rffnet"]["root"]
        m["base_checkpoint"] = kp["checkpoints"]["fusion_v1"]

    elif stage == 6:
        d["rffnet_root"] = kp["rffnet"]["root"]
        m["base_checkpoint"] = kp["checkpoints"]["fusion_v2_gated"]

    elif stage == 7:
        d["flame3_manifest"] = kp["orang_c_manifests"]["flame3_cv_subset"]
        d["flame3_root"] = kp["flame3"]["root"]
        if "domain_gap_lora" in config:
            config["domain_gap_lora"]["base_checkpoint"] = kp["checkpoints"]["fusion_v2_gated"]

    else:
        raise ValueError(f"Stage {stage} tidak dikenali oleh apply_kaggle_paths()")

    config["data"] = d
    config["model"] = m
    return config


if __name__ == "__main__":
    # Sanity check tanpa perlu di Kaggle -- pastikan tiap stage 1-7 bisa di-apply
    # tanpa KeyError, pakai kaggle_paths.yaml yang ada di repo ini.
    import sys
    repo_root = str(Path(__file__).resolve().parent.parent)
    kp = load_kaggle_paths(repo_root)

    dummy_configs = {
        1: {"stage": 1, "data": {}, "model": {}},
        2: {"stage": 2, "data": {}, "model": {}},
        4: {"stage": 4, "data": {}, "model": {}},
        5: {"stage": 5, "data": {}, "model": {}},
        6: {"stage": 6, "data": {}, "model": {}},
        7: {"stage": 7, "data": {}, "model": {}, "domain_gap_lora": {}},
    }
    for stage_num, cfg in dummy_configs.items():
        result = apply_kaggle_paths(cfg, kp)
        print(f"Stage {stage_num}: data={result['data']}  model={result.get('model')}")

    print("\nSemua stage (1,2,4,5,6,7) berhasil di-apply tanpa error.")
