# server/engine/main.py
# FastAPI application — Phase 8.2
# Endpoints:
#   POST /reports/save        — accepts ReportModel JSON, echoes id
#   POST /reports/export-pdf  — accepts ReportModel JSON + data, returns PDF bytes

from __future__ import annotations

import io
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from engine.models.report_models import parse_report

app = FastAPI(title="Report Engine", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Angular dev server to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ── POST /reports/save ────────────────────────────────────────────────────────


@app.post("/reports/save")
async def save_report(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and acknowledge a report definition.
    Phase 8: no persistence yet — returns id + saved: true.
    Phase 9+: write to database / file system.
    """
    try:
        report = parse_report(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {"id": report.id, "saved": True}


# ── POST /reports/export-pdf ──────────────────────────────────────────────────


@app.post("/reports/export-pdf")
async def export_pdf(payload: dict[str, Any]) -> StreamingResponse:
    """
    Generate a PDF from a ReportModel payload.
    The frontend merges report design + data before POSTing here.
    Returns raw PDF bytes with Content-Type: application/pdf.
    """
    try:
        report = parse_report(payload)

    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:

        from engine.renderers.pdf_renderer import PDFRenderer

        pdf_bytes = PDFRenderer().render(report)
        print(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Render error: {exc}")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report.name}.pdf"'},
    )
