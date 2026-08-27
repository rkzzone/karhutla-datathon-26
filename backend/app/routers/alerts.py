"""Endpoint alert — bentuk respons dikunci API_CONTRACT.md."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..schemas.prediction_schema import AlertPrediction, DecisionPatch
from ..services import model_client

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertPrediction])
def daftar_alert() -> list[AlertPrediction]:
    """Terurut `prediction.confidence` menurun."""
    try:
        return model_client.ambil_semua_alert()
    except model_client.ModelServiceError as galat:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "alasan": "model_service_unavailable",
                "pesan": (
                    "Layanan inference tidak merespons. Coba lagi dalam beberapa "
                    "menit, atau lanjutkan dengan alert yang sudah tersimpan."
                ),
                "detail": str(galat),
            },
        ) from galat


@router.get("/{alert_id}", response_model=AlertPrediction)
def satu_alert(alert_id: str) -> AlertPrediction:
    alert = model_client.ambil_satu_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "alasan": "alert_tidak_ditemukan",
                "pesan": f"Alert {alert_id} tidak ada dalam daftar aktif.",
            },
        )
    return alert


@router.patch("/{alert_id}/decision", response_model=AlertPrediction)
def catat_keputusan(alert_id: str, badan: DecisionPatch) -> AlertPrediction:
    alert = model_client.simpan_keputusan(alert_id, badan.operator_decision)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "alasan": "alert_tidak_ditemukan",
                "pesan": f"Alert {alert_id} tidak ada dalam daftar aktif.",
            },
        )
    return alert
