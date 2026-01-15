"""
Jobs API routes.
"""

from fastapi import APIRouter, HTTPException, Query

from mochi_analytics.api.models import JobListResponse, JobResponse, JobStatus, JobStatusResponse
from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Job

router = APIRouter()


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: JobStatus | None = None
) -> JobListResponse:
    """
    List all jobs with optional filtering.
    """
    session = get_session()
    try:
        query = session.query(Job).order_by(Job.created_at.desc())

        # Filter by status if provided
        if status:
            query = query.filter(Job.status == status.value)

        # Get total count
        total = query.count()

        # Apply pagination
        jobs_db = query.limit(limit).offset(offset).all()

        # Convert to response models
        jobs = []
        for job in jobs_db:
            result = None
            if job.status == JobStatus.COMPLETED.value and job.result:
                from mochi_analytics.core.models import AnalysisResult
                result = AnalysisResult.model_validate(job.result)

            jobs.append(
                JobStatusResponse(
                    job_id=job.id,
                    status=JobStatus(job.status),
                    created_at=job.created_at,
                    completed_at=job.completed_at,
                    result=result,
                    error=job.error
                )
            )

        return JobListResponse(jobs=jobs, total=total)

    finally:
        session.close()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    """
    Get job status and details.
    """
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

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


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str) -> JobResponse:
    """
    Retry a failed job.
    """
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != JobStatus.FAILED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Can only retry failed jobs. Current status: {job.status}"
            )

        # Reset job status
        job.status = JobStatus.QUEUED.value
        job.error = None
        job.completed_at = None
        session.commit()

        # TODO: Queue job for processing by worker

        return JobResponse(job_id=job.id, status=JobStatus.QUEUED)

    finally:
        session.close()
