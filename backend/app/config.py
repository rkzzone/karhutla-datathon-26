"""Konfigurasi runtime — semua rahasia lewat environment variable.

MAP_KEY (API key FIRMS) TIDAK BOLEH di-hardcode di mana pun.
`.env` ada di .gitignore; `.env.example` yang di-commit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

load_dotenv(BASE_DIR.parent / ".env")


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, ""))
    except ValueError:
        return default


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def as_firms_area(self) -> str:
        """Format area FIRMS: west,south,east,north."""
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"


class Settings:
    """Dibaca sekali saat import. Restart server kalau .env berubah."""

    map_key: str | None = os.getenv("MAP_KEY") or None
    model_service_url: str | None = os.getenv("MODEL_SERVICE_URL") or None
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    @property
    def origin_diizinkan(self) -> list[str]:
        """Daftar origin CORS.

        `FRONTEND_ORIGIN` menerima beberapa nilai dipisah koma — di produksi
        perlu setidaknya dua: domain produksi Vercel dan domain preview-nya.
        Localhost selalu ikut supaya pengembangan tidak perlu setelan terpisah.
        """
        dari_env = [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]
        lokal = ["http://localhost:5173", "http://127.0.0.1:5173"]
        return list(dict.fromkeys(dari_env + lokal))

    # Fixture FIRMS untuk dev/screenshot saat MAP_KEY belum ada. Respons yang
    # dihasilkan selalu ditandai is_fixture=true supaya UI bisa melabelinya —
    # jangan pernah menyajikannya sebagai data satelit sungguhan.
    firms_fixture: bool = _flag("FIRMS_FIXTURE", default=False)

    aoi = BoundingBox(
        min_lat=_float("AOI_MIN_LAT", -4.5),
        max_lat=_float("AOI_MAX_LAT", 1.5),
        min_lon=_float("AOI_MIN_LON", 100.0),
        max_lon=_float("AOI_MAX_LON", 117.0),
    )

    @property
    def memakai_model_nyata(self) -> bool:
        """False = Stage 9 (mock). True = Stage 10 (inference service tim model)."""
        return bool(self.model_service_url)


settings = Settings()
