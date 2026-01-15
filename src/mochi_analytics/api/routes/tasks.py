"""
Scheduled tasks API routes.
"""

import logging
import threading
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException

from mochi_analytics.api.models import TaskRequest, TaskResponse
from mochi_analytics.integrations import get_organizations, get_slack_configs
from mochi_analytics.workers import run_daily_updates_task

router = APIRouter()
logger = logging.getLogger(__name__)


def run_daily_updates_background(dry_run: bool, org_filter: str | None, force_send: bool):
    """Run daily updates in background thread."""
    try:
        logger.info(f"Background task started: dry_run={dry_run}, org_filter={org_filter}, force_send={force_send}")
        result = run_daily_updates_task(
            dry_run=dry_run,
            org_filter=org_filter,
            force_send=force_send
        )
        logger.info(f"Background task completed: {result}")
    except Exception as e:
        logger.error(f"Background task failed: {e}")


@router.post("/tasks/daily-updates", response_model=TaskResponse)
async def run_daily_updates(request: TaskRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    """
    Run daily Slack update task.

    Set force_send=True for manual runs (send immediately, ignore schedule).
    Set force_send=False for automated cron (respect each org's schedule_time).

    Task runs in background - returns immediately.
    """
    # Run in background to avoid Render timeout
    background_tasks.add_task(
        run_daily_updates_background,
        request.dry_run,
        request.org_filter,
        request.force_send
    )

    return TaskResponse(
        status="started",
        message=f"Task started in background for org_filter={request.org_filter}",
        jobs_created=0,
        errors=[]
    )


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


@router.get("/tasks/slack-configs")
async def debug_slack_configs():
    """
    Debug endpoint to see what Slack configurations are available.
    """
    try:
        # Get raw records to see what's in Airtable
        from mochi_analytics.integrations.airtable import AirtableClient
        client = AirtableClient()

        # Get ALL records (active and inactive)
        all_records = client.slack_table.all()

        # Get processed configs
        configs = get_slack_configs(active_only=False)  # Get all, not just active

        return {
            "total_raw_records": len(all_records),
            "raw_records": [
                {
                    "record_id": r["id"],
                    "fields": {
                        "Active": r["fields"].get("Active"),
                        "Schedule Time": r["fields"].get("Schedule Time"),
                        "Slack Channel": r["fields"].get("Slack Channel"),
                        "Organization": r["fields"].get("Organization"),
                        "Analysis": r["fields"].get("Analysis")
                    }
                }
                for r in all_records
            ],
            "total_configs": len(configs),
            "configs": [
                {
                    "record_id": c.record_id,
                    "organization_id": c.organization_id,
                    "slack_channel": c.slack_channel,
                    "stage_labels": c.stage_labels,
                    "schedule_time": c.schedule_time,
                    "active": c.active
                }
                for c in configs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Slack configs: {str(e)}")
