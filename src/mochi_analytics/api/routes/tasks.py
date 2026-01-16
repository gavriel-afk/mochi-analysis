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

# Store last task result for debugging
_last_task_result = {"status": "no task run yet", "timestamp": None}


def run_daily_updates_background(dry_run: bool, org_filter: str | None, force_send: bool):
    """Run daily updates in background thread."""
    global _last_task_result
    try:
        logger.info(f"Background task started: dry_run={dry_run}, org_filter={org_filter}, force_send={force_send}")
        _last_task_result = {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "org_filter": org_filter
        }
        result = run_daily_updates_task(
            dry_run=dry_run,
            org_filter=org_filter,
            force_send=force_send
        )
        logger.info(f"Background task completed: {result}")
        _last_task_result = {
            "status": "completed",
            "finished_at": datetime.utcnow().isoformat(),
            "result": result
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Background task failed: {e}\n{error_details}")
        _last_task_result = {
            "status": "failed",
            "finished_at": datetime.utcnow().isoformat(),
            "error": str(e),
            "traceback": error_details
        }


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


@router.get("/tasks/status")
async def get_task_status():
    """
    Get the status of the last background task.
    """
    return _last_task_result


@router.get("/tasks/debug-daily/{org_name}")
async def debug_daily_update(org_name: str):
    """
    Debug endpoint to see what data would be sent for a daily update.

    Returns the processed data (summary, scripts, groups) without sending to Slack.
    """
    from datetime import timedelta
    import pytz

    from mochi_analytics.core.models import Conversation
    from mochi_analytics.core.analyzer import analyze_conversations_simplified
    from mochi_analytics.core.script_search import run_script_searches
    from mochi_analytics.integrations import fetch_conversations, get_organization_by_id

    try:
        # Find matching config
        configs = get_slack_configs(active_only=True)
        matching_config = None

        for config in configs:
            org = get_organization_by_id(config.organization_id)
            if org and org_name.lower() in org.organization_name.lower():
                matching_config = config
                matching_org = org
                break

        if not matching_config:
            raise HTTPException(status_code=404, detail=f"No config found for org matching '{org_name}'")

        # Calculate yesterday in org's timezone
        org_tz = pytz.timezone(matching_org.timezone)
        org_now = datetime.now(org_tz)
        yesterday_org_tz = (org_now - timedelta(days=1)).date()

        # Fetch conversations with buffer
        fetch_from = yesterday_org_tz - timedelta(days=1)
        fetch_to = yesterday_org_tz + timedelta(days=1)

        conversations_data = fetch_conversations(
            org_id=matching_config.organization_id,
            date_from=fetch_from,
            date_to=fetch_to
        )

        conversations = [Conversation.model_validate(c) for c in conversations_data]

        # Run analysis
        result = analyze_conversations_simplified(
            conversations,
            timezone=matching_org.timezone,
            start_date=yesterday_org_tz,
            end_date=yesterday_org_tz
        )

        # Run script searches
        script_results_data = []
        if matching_config.script_configs:
            script_results = run_script_searches(
                conversations=conversations,
                script_configs=matching_config.script_configs,
                timezone=matching_org.timezone,
                target_date=yesterday_org_tz
            )
            script_results_data = [
                {"label": r.label, "total_matches": r.total_matches}
                for r in script_results
            ]

        # Run grouped analysis
        grouped_results_data = []
        if matching_config.grouped_configs:
            for group in matching_config.grouped_configs:
                member_results = run_script_searches(
                    conversations=conversations,
                    script_configs=group.member_configs,
                    timezone=matching_org.timezone,
                    target_date=yesterday_org_tz
                )
                total_matches = sum(r.total_matches for r in member_results)
                grouped_results_data.append({
                    "label": group.label,
                    "total_matches": total_matches
                })

        return {
            "org_name": matching_org.organization_name,
            "instagram_handle": matching_org.instagram_username,
            "date_analyzed": str(yesterday_org_tz),
            "total_conversations_fetched": len(conversations),
            "stage_labels": matching_config.stage_labels,
            "stage_changes": result.summary.stage_changes,
            "script_results": script_results_data,
            "grouped_results": grouped_results_data
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}\n{traceback.format_exc()}")


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
                    "script_configs": [s.model_dump() for s in c.script_configs],
                    "schedule_time": c.schedule_time,
                    "active": c.active
                }
                for c in configs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Slack configs: {str(e)}")
