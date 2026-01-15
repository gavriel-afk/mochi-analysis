"""
Reports API routes (Framer CMS integration).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from mochi_analytics.api.models import ReportResponse
from mochi_analytics.core.models import AnalysisResult
from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Report

router = APIRouter()


@router.post("/reports", response_model=ReportResponse)
async def create_report(result: AnalysisResult) -> ReportResponse:
    """
    Create a new report from analysis result.

    Stores the report in database queue for Framer CMS integration.
    """
    slug = str(uuid.uuid4())

    session = get_session()
    try:
        report = Report(
            slug=slug,
            data=result.model_dump(),
            created_at=datetime.utcnow()
        )
        session.add(report)
        session.commit()

        # Get queue size
        queue_size = session.query(Report).count()

        # Extract chart IDs if available (from metadata or result)
        chart_ids = []
        # TODO: Extract chart IDs from result or generate them

        return ReportResponse(
            slug=slug,
            queue_size=queue_size,
            chart_ids=chart_ids
        )

    finally:
        session.close()


@router.get("/reports")
async def list_reports(limit: int = 50, offset: int = 0):
    """
    List all reports.
    """
    session = get_session()
    try:
        reports = (
            session.query(Report)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return [
            {
                "slug": report.slug,
                "created_at": report.created_at,
                "pushed_at": report.pushed_at
            }
            for report in reports
        ]

    finally:
        session.close()


@router.get("/reports/{slug}")
async def get_report(slug: str):
    """
    Get a specific report by slug.
    """
    session = get_session()
    try:
        report = session.query(Report).filter(Report.slug == slug).first()

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        return report.data

    finally:
        session.close()
