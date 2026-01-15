"""
Analysis API routes.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from mochi_analytics.api.models import (
    AnalysisRequest,
    JobResponse,
    JobStatus,
    JobStatusResponse,
)
from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Job
from mochi_analytics.workers import submit_job, run_analysis_task

router = APIRouter()


@router.post("/analysis", response_model=JobResponse)
async def create_analysis_job(request: AnalysisRequest) -> JobResponse:
    """
    Submit a new analysis job.

    Accepts conversation data and configuration, runs analysis, and returns job ID.
    """
    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job record with queued status
    session = get_session()
    try:
        job = Job(
            id=job_id,
            status=JobStatus.QUEUED.value,
            created_at=datetime.utcnow()
        )
        session.add(job)
        session.commit()
    finally:
        session.close()

    # Submit job to background worker queue
    conversations_data = [c.model_dump() for c in request.conversations]
    config_dict = request.config.model_dump()
    config_dict["job_id"] = job_id  # Pass job_id for chart storage

    submit_job(
        run_analysis_task,
        conversations_data,
        config_dict,
        job_id=job_id
    )

    return JobResponse(job_id=job_id, status=JobStatus.QUEUED)


@router.get("/analysis/{job_id}", response_model=JobStatusResponse)
async def get_analysis_status(job_id: str) -> JobStatusResponse:
    """
    Get analysis job status and results.
    """
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Parse result if completed
        result = None
        if job.status == JobStatus.COMPLETED.value and job.result:
            from mochi_analytics.core.models import AnalysisResult
            result = AnalysisResult.model_validate(job.result)

        return JobStatusResponse(
            job_id=job.id,
            status=JobStatus(job.status),
            created_at=job.created_at,
            completed_at=job.completed_at,
            result=result,
            error=job.error
        )

    finally:
        session.close()
