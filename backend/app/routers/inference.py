"""Endpoint inference langsung.

Stage 9: meneruskan ke mock lewat `model_client`. Stage 10: `model_client`
otomatis memanggil service tim model begitu MODEL_SERVICE_URL diisi — router ini
tidak perlu diubah.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from ..config import MOCK_DATA_DIR
from ..schemas.prediction_schema import AlertPrediction
from ..services import model_client

router = APIRouter(prefix="/api/inference", tags=["inference"])

_METRIK_PATH = MOCK_DATA_DIR / "model_metrics.json"


@router.get("/status")
def status_inference() -> dict:
    """Dipakai badge "sumber data" di header UI — mock vs model nyata."""
    return model_client.status_sumber()


@router.get("/latest", response_model=AlertPrediction)
def prediksi_terbaru() -> AlertPrediction:
    """Alert dengan confidence tertinggi — dipakai panel ringkas Halaman 1."""
    try:
        alerts = model_client.ambil_semua_alert()
    except model_client.ModelServiceError as galat:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "alasan": "model_service_unavailable",
                "pesan": "Layanan inference tidak merespons.",
            },
        ) from galat
    if not alerts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"alasan": "kosong", "pesan": "Belum ada alert."},
        )
    return alerts[0]


@router.get("/metrics")
def metrik_model() -> dict:
    """Angka untuk Halaman 4 (juri).

    Selama `status == "placeholder"` seluruh nilai numerik masih `null` dan UI
    WAJIB menampilkan banner bahwa angka belum diukur — jangan pernah mengisi
    angka rekaan demi tampilan grafik yang "penuh".

    Stage 7 (tim model) dan Stage 8 (tim data): timpa `mock_data/model_metrics.json`
    dengan hasil ukur nyata dan ubah `status` jadi "terukur".
    """
    with _METRIK_PATH.open(encoding="utf-8") as berkas:
        return json.load(berkas)
