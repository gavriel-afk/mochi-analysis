"""
Scheduled tasks API routes.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from mochi_analytics.api.models import TaskRequest, TaskResponse
from mochi_analytics.integrations import get_organizations, get_slack_configs
from mochi_analytics.workers import run_daily_updates_task

router = APIRouter()


@router.post("/tasks/daily-updates", response_model=TaskResponse)
async def run_daily_updates(request: TaskRequest) -> TaskResponse:
    """
    Run daily Slack update task.

    This endpoint should be called by cron scheduler to send daily digests.
    """
    try:
        result = run_daily_updates_task(dry_run=request.dry_run)

        return TaskResponse(
            status="completed",
            message=f"Sent {result['updates_sent']} updates",
            jobs_created=result['updates_sent'],
            errors=result.get('errors', [])
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task failed: {e}")


@router.post("/tasks/auto-export", response_model=TaskResponse)
async def run_auto_export(request: TaskRequest) -> TaskResponse:
    """
    Run automatic export task for Framer CMS.

    Generates weekly reports and pushes them to Framer.
    """
    try:
        # Get all active organizations
        orgs = get_organizations(active_only=True)

        if request.org_filter:
            # Filter by name
            orgs = [o for o in orgs if request.org_filter.lower() in o.organization_name.lower()]

        jobs_created = 0
        errors = []

        for org in orgs:
            try:
                # TODO: Implement auto-export logic
                # 1. Calculate date range (last 7 days)
                # 2. Fetch conversations
                # 3. Run full analysis
                # 4. Push to Framer CMS
                # 5. Store report in database

                if not request.dry_run:
                    # Actually create and push the report
                    pass

                jobs_created += 1

            except Exception as e:
                errors.append(f"Failed for org {org.organization_name}: {e}")

        return TaskResponse(
            status="completed",
            message=f"Processed {len(orgs)} organizations",
            jobs_created=jobs_created,
            errors=errors
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task failed: {e}")
