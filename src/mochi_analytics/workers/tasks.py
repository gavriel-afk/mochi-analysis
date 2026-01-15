"""
Background task definitions.
"""

import logging
from datetime import datetime, timedelta
import pytz

from mochi_analytics.core.models import Conversation, AnalysisConfig
from mochi_analytics.core.analyzer import analyze_conversations, analyze_conversations_simplified
from mochi_analytics.integrations import fetch_conversations, get_slack_configs, send_daily_digest
from mochi_analytics.exporters.charts import generate_all_charts
from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Chart

logger = logging.getLogger(__name__)


def run_analysis_task(
    conversations_data: list[dict],
    config_dict: dict
) -> dict:
    """
    Run full analysis task (executed in background worker).

    Args:
        conversations_data: List of conversation dictionaries
        config_dict: Analysis configuration dictionary

    Returns:
        Analysis result as dictionary
    """
    logger.info(f"Starting analysis task for {len(conversations_data)} conversations")

    # Parse conversations
    conversations = [Conversation.model_validate(c) for c in conversations_data]

    # Parse config
    config = AnalysisConfig.model_validate(config_dict)

    # Run analysis
    result = analyze_conversations(conversations, config)

    logger.info(f"Analysis complete: {result.summary.total_conversations} conversations")

    # Generate and store charts if time series data available
    if result.time_series and result.time_series.stage_changes_by_day:
        try:
            from pathlib import Path
            chart_config_path = Path(__file__).parent.parent.parent.parent / "config" / "charts.toml"

            charts = generate_all_charts(
                time_series_data=result.time_series.stage_changes_by_day,
                config_path=str(chart_config_path)
            )

            # Store charts in database
            session = get_session()
            try:
                job_id = config_dict.get("job_id")  # If passed in
                for chart_id, png_base64 in charts.items():
                    chart = Chart(
                        job_id=job_id,
                        chart_id=chart_id,
                        png_base64=png_base64,
                        created_at=datetime.utcnow()
                    )
                    session.add(chart)
                session.commit()
                logger.info(f"Stored {len(charts)} charts in database")
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to generate/store charts: {e}")

    return result.model_dump()


def run_daily_updates_task(dry_run: bool = False, org_filter: str | None = None, force_send: bool = False) -> dict:
    """
    Run daily Slack updates for all configured organizations.

    This checks which organizations are due for updates based on:
    - Current hour matches their schedule_time (in their timezone)
    - Sends simplified analysis (metrics + setters only)

    Args:
        dry_run: If True, don't actually send Slack messages
        org_filter: Optional organization name filter (case-insensitive substring match)
        force_send: If True, ignore schedule_time and send immediately (for manual runs)

    Returns:
        Summary of updates sent
    """
    logger.info(f"Running daily updates task (force_send={force_send})")

    # Get all active Slack configurations
    try:
        slack_configs = get_slack_configs(active_only=True)
    except Exception as e:
        logger.error(f"Failed to get Slack configs: {e}")
        return {"error": str(e), "updates_sent": 0}

    updates_sent = 0
    errors = []
    skipped = 0

    # Filter by organization name if specified
    if org_filter:
        from mochi_analytics.integrations import get_organization_by_id
        filtered_configs = []
        for config in slack_configs:
            org = get_organization_by_id(config.organization_id)
            if org and org_filter.lower() in org.organization_name.lower():
                filtered_configs.append(config)
        slack_configs = filtered_configs
        logger.info(f"Filtered to {len(slack_configs)} orgs matching '{org_filter}'")

    for config in slack_configs:
        # Check schedule time unless force_send is True
        if not force_send:
            # Get org timezone and check if current hour matches schedule_time
            from mochi_analytics.integrations import get_organization_by_id
            org = get_organization_by_id(config.organization_id)

            if org:
                try:
                    # Parse schedule time (HH:MM format)
                    schedule_hour, schedule_minute = map(int, config.schedule_time.split(':'))

                    # Get current time in org's timezone
                    org_tz = pytz.timezone(org.timezone)
                    current_time = datetime.now(org_tz)

                    # Check if current hour matches (allow ±5 minute window)
                    if current_time.hour != schedule_hour:
                        logger.debug(f"Skipping {org.organization_name}: current hour {current_time.hour} != schedule hour {schedule_hour}")
                        skipped += 1
                        continue

                    # Optional: check minute window
                    minute_diff = abs(current_time.minute - schedule_minute)
                    if minute_diff > 5:  # Allow 5-minute window
                        logger.debug(f"Skipping {org.organization_name}: outside 5-minute window")
                        skipped += 1
                        continue

                except Exception as e:
                    logger.warning(f"Failed to parse schedule for {config.organization_id}: {e}, sending anyway")

        try:
            org_id = config.organization_id

            # Calculate date range (yesterday)
            today = datetime.utcnow().date()
            yesterday = today - timedelta(days=1)

            # Fetch conversations
            try:
                conversations_data = fetch_conversations(
                    org_id=org_id,
                    date_from=yesterday,
                    date_to=yesterday
                )
            except Exception as e:
                logger.error(f"Failed to fetch conversations for {org_id}: {e}")
                errors.append(f"{org_id}: {e}")
                continue

            if not conversations_data:
                logger.info(f"No conversations for {org_id} on {yesterday}")
                continue

            # Parse conversations
            conversations = [Conversation.model_validate(c) for c in conversations_data]

            # Run simplified analysis (no LLM features)
            result = analyze_conversations_simplified(
                conversations,
                timezone="UTC",
                start_date=yesterday,
                end_date=yesterday
            )

            # Send Slack digest
            if not dry_run:
                from mochi_analytics.integrations import get_organization_by_id

                org = get_organization_by_id(org_id)
                if org:
                    send_daily_digest(
                        channel=config.slack_channel,
                        org_name=org.organization_name,
                        instagram_handle=org.instagram_username,
                        summary=result.summary.model_dump(),
                        setters=result.setters_by_sent_by if result.setters_by_sent_by else None,
                        date_range=str(yesterday)
                    )
                    logger.info(f"Sent daily digest for {org_id} to {config.slack_channel}")
                    updates_sent += 1
                else:
                    logger.warning(f"Organization {org_id} not found in Airtable")
            else:
                logger.info(f"[DRY RUN] Would send digest for {org_id}")
                updates_sent += 1

        except Exception as e:
            logger.error(f"Failed to process daily update for {config.organization_id}: {e}")
            errors.append(f"{config.organization_id}: {e}")

    return {
        "updates_sent": updates_sent,
        "total_configs": len(slack_configs),
        "skipped": skipped,
        "errors": errors
    }
