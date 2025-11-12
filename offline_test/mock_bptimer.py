"""Mock BP Timer ingestion API used for offline validation."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
app = FastAPI(title="Mock BP Timer API", version="1.0.0")


class HPReport(BaseModel):
    monster_id: int = Field(..., ge=1)
    hp_pct: float = Field(..., ge=0, le=100)
    line: int = Field(..., ge=1, le=1000)
    instance_id: Optional[str] = None
    map_id: Optional[int] = Field(default=None, ge=0)
    boss_name: Optional[str] = None
    event_type: Optional[str] = Field(default=None, pattern="^(start|tick|end)$")
    timestamp_ms: Optional[int] = Field(default=None, ge=0)

    @field_validator("boss_name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        return value


@app.post("/api/create-hp-report")
async def create_hp_report(report: HPReport, request: Request, x_api_key: Optional[str] = Header(default=None)) -> dict:
    if x_api_key and x_api_key.startswith("deny"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    logger.info("Received HP report: %s", report.model_dump())
    return {"success": True, "data": report.model_dump()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
