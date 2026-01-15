"""
Exports API routes.
"""

import base64
import io
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from mochi_analytics.api.models import JobStatus
from mochi_analytics.core.models import AnalysisResult
from mochi_analytics.exporters import export_framer_csv, export_json
from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Chart, Job

router = APIRouter()


def get_job_result(job_id: str) -> AnalysisResult:
    """Helper to get job result."""
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != JobStatus.COMPLETED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Job not completed. Current status: {job.status}"
            )

        if not job.result:
            raise HTTPException(status_code=500, detail="Job result is empty")

        return AnalysisResult.model_validate(job.result)

    finally:
        session.close()


@router.get("/exports/{job_id}/json")
async def export_job_json(job_id: str):
    """
    Export job result as JSON file.
    """
    result = get_job_result(job_id)
    json_content = export_json(result)

    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=analysis_{job_id}.json"
        }
    )


@router.get("/exports/{job_id}/csv")
async def export_job_csv(job_id: str):
    """
    Export job result as CSV file (Framer CMS format).
    """
    result = get_job_result(job_id)
    csv_content = export_framer_csv(result)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=framer_import_{job_id}.csv"
        }
    )


@router.get("/exports/{job_id}/charts/{chart_id}.png")
async def export_chart_png(job_id: str, chart_id: str):
    """
    Export a specific chart as PNG image.
    """
    session = get_session()
    try:
        chart = session.query(Chart).filter(
            Chart.job_id == job_id,
            Chart.chart_id == chart_id
        ).first()

        if not chart:
            raise HTTPException(status_code=404, detail="Chart not found")

        # Decode base64 PNG
        png_bytes = base64.b64decode(chart.png_base64)

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename={chart_id}.png"
            }
        )

    finally:
        session.close()


@router.get("/exports/{job_id}/zip")
async def export_job_zip(job_id: str):
    """
    Export job result as ZIP bundle (JSON + CSV + all charts).
    """
    result = get_job_result(job_id)

    # Create in-memory ZIP file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add JSON
        json_content = export_json(result)
        zip_file.writestr(f"analysis_{job_id}.json", json_content)

        # Add CSV
        csv_content = export_framer_csv(result)
        zip_file.writestr(f"framer_import_{job_id}.csv", csv_content)

        # Add all charts
        session = get_session()
        try:
            charts = session.query(Chart).filter(Chart.job_id == job_id).all()

            for chart in charts:
                png_bytes = base64.b64decode(chart.png_base64)
                zip_file.writestr(f"charts/{chart.chart_id}.png", png_bytes)

        finally:
            session.close()

    # Return ZIP
    zip_buffer.seek(0)
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=mochi_analytics_{job_id}.zip"
        }
    )
