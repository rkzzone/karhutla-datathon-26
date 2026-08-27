"""Endpoint sensor darat simulasi (Stage 12).

Semua respons di router ini membawa header `X-Data-Simulated: true` dan field
`simulasi: true` di badan. UI wajib melabelinya "SIMULASI".
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from ..services import iot_simulator

router = APIRouter(prefix="/api/iot", tags=["iot-simulation"])


@router.get("/nodes")
def daftar_node(respons: Response) -> dict:
    respons.headers["X-Data-Simulated"] = "true"
    return iot_simulator.ambil_node()


@router.get("/nodes/{node_id}/history")
def riwayat_node(
    node_id: str,
    respons: Response,
    menit: int = Query(default=60, ge=10, le=240),
) -> dict:
    hasil = iot_simulator.ambil_riwayat(node_id, menit=menit)
    if not hasil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "alasan": "node_tidak_ditemukan",
                "pesan": f"Node {node_id} tidak terdaftar di jaringan simulasi.",
            },
        )
    respons.headers["X-Data-Simulated"] = "true"
    return hasil
