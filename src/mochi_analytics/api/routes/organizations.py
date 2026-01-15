"""
Organizations API routes.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from mochi_analytics.api.models import (
    JobResponse,
    JobStatus,
    OrganizationAnalysisRequest,
    OrganizationListResponse,
    OrganizationResponse,
)
from mochi_analytics.core.analyzer import analyze_conversations
from mochi_analytics.core.models import AnalysisConfig, Conversation
from mochi_analytics.integrations import MochiAPIError, fetch_conversations, get_organization_by_id, get_organizations
from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Job

router = APIRouter()


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_organizations(active_only: bool = True) -> OrganizationListResponse:
    """
    List all organizations from Airtable.
    """
    try:
        orgs = get_organizations(active_only=active_only)

        org_responses = [
            OrganizationResponse(
                record_id=org.record_id,
                organization_name=org.organization_name,
                organization_id=org.organization_id,
                timezone=org.timezone,
                instagram_username=org.instagram_username,
                active=org.active
            )
            for org in orgs
        ]

        return OrganizationListResponse(
            organizations=org_responses,
            total=len(org_responses)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch organizations: {e}")


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: str) -> OrganizationResponse:
    """
    Get organization details by ID.
    """
    try:
        org = get_organization_by_id(org_id)

        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        return OrganizationResponse(
            record_id=org.record_id,
            organization_name=org.organization_name,
            organization_id=org.organization_id,
            timezone=org.timezone,
            instagram_username=org.instagram_username,
            active=org.active
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch organization: {e}")


@router.post("/organizations/{org_id}/analyze", response_model=JobResponse)
async def analyze_organization(org_id: str, request: OrganizationAnalysisRequest) -> JobResponse:
    """
    Fetch data from Mochi API and run analysis for an organization.
    """
    # Get organization config
    org = get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job record
    session = get_session()
    try:
        job = Job(
            id=job_id,
            status=JobStatus.PROCESSING.value,
            created_at=datetime.utcnow()
        )
        session.add(job)
        session.commit()

        # Fetch conversations from Mochi API
        try:
            conversations_data = fetch_conversations(
                org_id=org_id,
                date_from=request.date_from,
                date_to=request.date_to
            )

            # Parse conversations
            conversations = [Conversation.model_validate(c) for c in conversations_data]

            # Build config
            config = request.config or AnalysisConfig(
                timezone=org.timezone,
                start_date=request.date_from,
                end_date=request.date_to
            )

            # Run analysis
            result = analyze_conversations(
                conversations=conversations,
                config=config
            )

            # Update job with result
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            job.result = result.model_dump()
            session.commit()

            return JobResponse(job_id=job_id, status=JobStatus.COMPLETED)

        except MochiAPIError as e:
            # Update job with error
            job.status = JobStatus.FAILED.value
            job.completed_at = datetime.utcnow()
            job.error = f"Mochi API error: {e}"
            session.commit()

            raise HTTPException(status_code=502, detail=f"Failed to fetch data from Mochi: {e}")

        except Exception as e:
            # Update job with error
            job.status = JobStatus.FAILED.value
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            session.commit()

            raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    finally:
        session.close()
