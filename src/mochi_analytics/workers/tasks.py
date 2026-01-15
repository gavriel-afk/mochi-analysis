"""
Background task definitions.
"""

import logging
from datetime import datetime, timedelta

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


def run_daily_updates_task(dry_run: bool = False) -> dict:
    """
    Run daily Slack updates for all configured organizations.

    This checks which organizations are due for updates based on:
    - Current hour matches their schedule_time (in their timezone)
    - Sends simplified analysis (metrics + setters only)

    Args:
        dry_run: If True, don't actually send Slack messages

    Returns:
        Summary of updates sent
    """
    logger.info("Running daily updates task")

    # Get all active Slack configurations
    try:
        slack_configs = get_slack_configs(active_only=True)
    except Exception as e:
        logger.error(f"Failed to get Slack configs: {e}")
        return {"error": str(e), "updates_sent": 0}

    updates_sent = 0
    errors = []

    for config in slack_configs:
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
            analysis_config = AnalysisConfig(
                timezone="UTC",  # Will be converted in analysis
                start_date=str(yesterday),
                end_date=str(yesterday),
                include_scripts=False,
                include_objections=False,
                include_avatars=False
            )

            result = analyze_conversations_simplified(conversations, analysis_config)

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
                        setters=result.setters_by_assignment.model_dump() if result.setters_by_assignment else None,
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
        "errors": errors
    }
