"""
API request and response models.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from mochi_analytics.core.models import AnalysisConfig, AnalysisResult, Conversation


class JobStatus(str, Enum):
    """Job status enum."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Request models
class AnalysisRequest(BaseModel):
    """Request model for analysis endpoint."""

    conversations: list[Conversation] = Field(..., description="List of conversations to analyze")
    config: AnalysisConfig = Field(..., description="Analysis configuration")


class OrganizationAnalysisRequest(BaseModel):
    """Request model for organization-based analysis."""

    date_from: str = Field(..., description="Start date (YYYY-MM-DD)")
    date_to: str = Field(..., description="End date (YYYY-MM-DD)")
    config: AnalysisConfig | None = Field(None, description="Optional analysis configuration")


class TaskRequest(BaseModel):
    """Request model for scheduled tasks."""

    org_filter: str | None = Field(None, description="Optional organization name filter")
    dry_run: bool = Field(default=False, description="If true, don't actually perform actions")


# Response models
class JobResponse(BaseModel):
    """Response model for job creation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Job status")


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")
    result: AnalysisResult | None = Field(None, description="Analysis result (if completed)")
    error: str | None = Field(None, description="Error message (if failed)")


class JobListResponse(BaseModel):
    """Response model for job list."""

    jobs: list[JobStatusResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Current timestamp")
    version: str = Field(default="2.0.0", description="API version")


class ReportResponse(BaseModel):
    """Response model for report creation."""

    slug: str = Field(..., description="Unique report identifier")
    queue_size: int = Field(..., description="Number of reports in queue")
    chart_ids: list[str] = Field(default_factory=list, description="List of chart IDs")


class TaskResponse(BaseModel):
    """Response model for task execution."""

    status: str = Field(..., description="Task status")
    message: str | None = Field(None, description="Additional information")
    jobs_created: int = Field(default=0, description="Number of jobs created")
    errors: list[str] = Field(default_factory=list, description="List of errors encountered")


class OrganizationResponse(BaseModel):
    """Response model for organization."""

    record_id: str = Field(..., description="Airtable record ID")
    organization_name: str = Field(..., description="Display name")
    organization_id: str = Field(..., description="Mochi org UUID")
    timezone: str = Field(..., description="IANA timezone")
    instagram_username: str | None = Field(None, description="Instagram handle")
    active: bool = Field(..., description="Whether org is active")


class OrganizationListResponse(BaseModel):
    """Response model for organization list."""

    organizations: list[OrganizationResponse] = Field(..., description="List of organizations")
    total: int = Field(..., description="Total number of organizations")
