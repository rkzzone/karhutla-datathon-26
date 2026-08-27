"""Satu-satunya tempat yang tahu dari mana prediksi datang.

=============================================================================
 STAGE 10 — GANTI MOCK KE DATA ASLI DI SINI, TIDAK DI TEMPAT LAIN
=============================================================================
Yang perlu dilakukan begitu tim model share inference service:

  1. Isi `MODEL_SERVICE_URL` di `backend/.env`
     (mis. MODEL_SERVICE_URL=http://localhost:8100)
  2. Sudah itu saja. `memakai_model_nyata` otomatis True dan seluruh fungsi di
     bawah beralih dari `_muat_mock()` ke `_ambil_dari_service()`.

Kalau bentuk endpoint tim model berbeda dari asumsi di `_ambil_dari_service()`,
ubah HANYA fungsi itu — router dan frontend tidak boleh ikut berubah, karena
keduanya bicara dalam bentuk `AlertPrediction` dari API_CONTRACT.md.

Checklist smoke test sebelum mengumumkan "sudah pakai data asli" ada di
API_CONTRACT.md bagian paling bawah.
=============================================================================
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from ..config import MOCK_DATA_DIR, settings
from ..schemas.prediction_schema import AlertPrediction, OperatorDecision

logger = logging.getLogger(__name__)

_MOCK_PATH = MOCK_DATA_DIR / "sample_predictions.json"

# Keputusan operator disimpan di memori proses selama Stage 9 supaya Halaman 3
# terasa hidup saat demo. Stage 10: PATCH diteruskan ke service tim model / DB.
_keputusan_lokal: dict[str, Optional[str]] = {}


class ModelServiceError(RuntimeError):
    """Inference service tidak bisa dihubungi atau menjawab dengan bentuk asing."""


def _muat_mock() -> list[AlertPrediction]:
    with _MOCK_PATH.open(encoding="utf-8") as berkas:
        mentah: list[dict[str, Any]] = json.load(berkas)
    # Divalidasi lewat skema yang sama dengan data asli — kalau mock melanggar
    # kontrak, kita tahu sekarang, bukan nanti saat Stage 10.
    return [AlertPrediction.model_validate(item) for item in mentah]


def _ambil_dari_service() -> list[AlertPrediction]:
    url = f"{settings.model_service_url.rstrip('/')}/alerts"
    try:
        respons = httpx.get(url, timeout=10.0)
        respons.raise_for_status()
        mentah = respons.json()
    except httpx.HTTPError as galat:
        raise ModelServiceError(str(galat)) from galat
    return [AlertPrediction.model_validate(item) for item in mentah]


def _terapkan_keputusan_lokal(alerts: list[AlertPrediction]) -> list[AlertPrediction]:
    if not _keputusan_lokal:
        return alerts
    hasil = []
    for alert in alerts:
        if alert.alert_id in _keputusan_lokal:
            alert = alert.model_copy(
                update={"operator_decision": _keputusan_lokal[alert.alert_id]}
            )
        hasil.append(alert)
    return hasil


def ambil_semua_alert() -> list[AlertPrediction]:
    """Terurut `prediction.confidence` menurun — sesuai API_CONTRACT.md."""
    if settings.memakai_model_nyata:
        alerts = _ambil_dari_service()
    else:
        alerts = _muat_mock()
    alerts = _terapkan_keputusan_lokal(alerts)
    return sorted(alerts, key=lambda a: a.prediction.confidence, reverse=True)


def ambil_satu_alert(alert_id: str) -> Optional[AlertPrediction]:
    for alert in ambil_semua_alert():
        if alert.alert_id == alert_id:
            return alert
    return None


def simpan_keputusan(
    alert_id: str, keputusan: Optional[OperatorDecision]
) -> Optional[AlertPrediction]:
    if ambil_satu_alert(alert_id) is None:
        return None
    _keputusan_lokal[alert_id] = keputusan
    return ambil_satu_alert(alert_id)


# Ditulis `backend/scripts/jalankan_inference.py` saat alert dihasilkan dari
# checkpoint sungguhan. Keberadaannya membedakan "mock karangan" dari "keluaran
# model nyata yang dihitung batch" — dua hal yang sangat berbeda di depan juri.
_PROVENANS_PATH = MOCK_DATA_DIR / "frame_provenance.json"


def status_sumber() -> dict[str, Any]:
    """Dipakai `/api/health` dan badge header. TIGA keadaan, bukan dua.

    mock          — data karangan, tidak ada model yang terlibat
    batch         — keluaran model sungguhan, dihitung sekali lalu disimpan
    model_service — layanan inference hidup dipanggil per permintaan

    Membedakan `mock` dari `batch` itu penting: menampilkan "mock" padahal
    angkanya berasal dari `fusion_v3_localization.pth` akan meremehkan pekerjaan
    sendiri, dan menampilkan "model" untuk data karangan akan menipu.
    """
    if settings.memakai_model_nyata:
        sumber = "model_service"
    elif _PROVENANS_PATH.exists():
        sumber = "batch"
    else:
        sumber = "mock"

    hasil: dict[str, Any] = {
        "sumber": sumber,
        "model_service_url": settings.model_service_url,
        "berkas_mock": str(_MOCK_PATH) if sumber != "model_service" else None,
    }
    if sumber == "batch":
        try:
            with _PROVENANS_PATH.open(encoding="utf-8") as berkas:
                provenans = json.load(berkas)
            hasil["batch"] = {
                "jumlah_bingkai": len(provenans),
                "checkpoint": "fusion_v3_localization.pth",
                "dataset": "FLAME2 254p — split RFFNet val",
            }
        except (OSError, json.JSONDecodeError):
            pass
    return hasil
