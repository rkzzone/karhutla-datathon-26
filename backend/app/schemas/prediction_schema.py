"""Skema respons inference.

SUMBER KEBENARAN: ../../API_CONTRACT.md (salinan kanonik di root repo).
Jangan tambah/kurangi field top-level di sini tanpa mengubah API_CONTRACT.md lebih
dulu, menyalin ke direktori tim model, dan mencatat di CHANGELOG.md kedua pihak.

Aturan validasi yang ditegakkan file ini (API_CONTRACT.md Bagian "Aturan validasi"):
1. `label` hanya salah satu dari tiga string persis.
2. confidence & modality_reliability selalu float [0.0, 1.0] — bukan persen.
3. `null` hanya untuk field yang tabel status menyatakan belum tersedia.
4. `timestamp` ISO 8601 dengan timezone eksplisit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PredictionLabel = Literal["fire_smoke", "fire_no_smoke", "no_fire"]
LocalizationMethod = Literal["attention_rollout", "segmentation_head"]
SourceTrigger = Literal["satellite_firms", "iot_ground", "patrol_scheduled"]
OperatorDecision = Literal["ditindaklanjuti", "ditunda", "alarm_palsu"]

Unit = Field(ge=0.0, le=1.0)


class StrictModel(BaseModel):
    """Tolak field asing — pagar keras terhadap drift kontrak."""

    model_config = ConfigDict(extra="forbid")


class Location(StrictModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class Prediction(StrictModel):
    label: PredictionLabel
    confidence: float = Unit


class ModalityReliability(StrictModel):
    """Nilai nyata baru terisi setelah Stage 5 tim model selesai.

    Sebelum itu kedua field `null`. Frontend WAJIB merender "—", bukan 0%.
    """

    rgb: Optional[float] = Unit
    thermal: Optional[float] = Unit


class Localization(StrictModel):
    """Nilai nyata baru terisi setelah Stage 6 tim model selesai."""

    heatmap_path: Optional[str] = None
    method: Optional[LocalizationMethod] = None

    @field_validator("method")
    @classmethod
    def _method_requires_path(
        cls, method: Optional[str], info
    ) -> Optional[str]:
        # Method tanpa heatmap tidak punya arti — cegah kombinasi setengah jadi
        # yang akan membuat overlay merender kotak kosong di Halaman 3.
        if method is not None and not info.data.get("heatmap_path"):
            raise ValueError("localization.method diisi tapi heatmap_path null")
        return method


class Images(StrictModel):
    rgb_url: str = Field(min_length=1)
    thermal_url: str = Field(min_length=1)


class AlertPrediction(StrictModel):
    """Satu objek alert — bentuk persis yang dikonsumsi frontend."""

    alert_id: str = Field(min_length=1)
    timestamp: datetime
    location: Location
    prediction: Prediction
    modality_reliability: ModalityReliability
    localization: Localization
    images: Images
    source_trigger: SourceTrigger
    operator_decision: Optional[OperatorDecision] = None

    @field_validator("timestamp")
    @classmethod
    def _timezone_wajib_eksplisit(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp wajib ISO 8601 dengan timezone eksplisit")
        return value


class DecisionPatch(StrictModel):
    """Body `PATCH /api/alerts/{alert_id}/decision`."""

    operator_decision: Optional[OperatorDecision] = None
