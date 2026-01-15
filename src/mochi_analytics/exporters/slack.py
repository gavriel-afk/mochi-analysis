"""
Slack Block Kit export formatter.
"""

from typing import Any

from mochi_analytics.core.models import AnalysisResult


def format_hours(seconds: int | float) -> str:
    """Format seconds as human-readable hours/minutes."""
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def build_metrics_text(
    result: AnalysisResult,
    stages_filter: list[str] | None = None
) -> str:
    """
    Build markdown metrics text for Slack.

    Args:
        result: Analysis result
        stages_filter: Optional list of stages to include

    Returns:
        Markdown formatted text
    """
    summary = result.summary
    lines = ["*Key Metrics*\n"]

    # Core metrics
    lines.append(f"• *Conversations:* {summary.total_conversations}")
    lines.append(f"• *Messages Sent:* {summary.total_messages_sent}")
    lines.append(f"• *Messages Received:* {summary.total_messages_received}")

    # Reply rate
    if summary.creator_message_reply_rate_within_48h is not None:
        lines.append(f"• *Reply Rate (48h):* {summary.creator_message_reply_rate_within_48h:.1f}%")

    # Median reply time
    if summary.median_reply_delay_seconds is not None:
        formatted = format_hours(summary.median_reply_delay_seconds)
        lines.append(f"• *Median Reply Time:* {formatted}")

    return "\n".join(lines)


def build_stage_changes_text(
    result: AnalysisResult,
    stages_filter: list[str] | None = None
) -> str:
    """
    Build stage changes text for Slack.

    Args:
        result: Analysis result
        stages_filter: Optional list of stages to include (if None, includes all non-zero)

    Returns:
        Markdown formatted text
    """
    stage_changes = result.summary.stage_changes
    lines = ["*Stage Changes*\n"]

    if stages_filter:
        # Use filtered list
        for stage in stages_filter:
            count = stage_changes.get(stage, 0)
            stage_name = stage.replace("_", " ").title()
            lines.append(f"• {stage_name}: {count}")
    else:
        # Include all non-zero stages
        for stage, count in stage_changes.items():
            if count > 0:
                stage_name = stage.replace("_", " ").title()
                lines.append(f"• {stage_name}: {count}")

    if len(lines) == 1:  # Only header
        lines.append("• No stage changes")

    return "\n".join(lines)


def build_setter_performance_text(result: AnalysisResult, top_n: int = 5) -> str:
    """
    Build setter performance text for Slack.

    Args:
        result: Analysis result
        top_n: Number of top setters to include (default: 5)

    Returns:
        Markdown formatted text
    """
    setters_data = result.setters_by_assignment
    if not setters_data or not setters_data.get("setters"):
        return "*Setter Performance*\n\n• No setter data available"

    setters = setters_data["setters"][:top_n]
    lines = [f"*Top {top_n} Setters*\n"]

    for i, setter in enumerate(setters, 1):
        email = setter.get("setter_email", "Unknown")
        convos = setter.get("total_conversations", 0)
        msgs = setter.get("messages_sent", 0)
        reply_rate = setter.get("reply_rate_within_48h")

        text = f"{i}. {email} - {convos} convos, {msgs} msgs"
        if reply_rate is not None:
            text += f", {reply_rate:.1f}% reply rate"

        lines.append(text)

    return "\n".join(lines)


def export_slack_blocks(
    result: AnalysisResult,
    org_name: str,
    instagram_username: str | None = None,
    stages_filter: list[str] | None = None,
    include_setters: bool = True,
    date_range: str | None = None
) -> list[dict[str, Any]]:
    """
    Export analysis result as Slack Block Kit blocks.

    Args:
        result: Analysis result
        org_name: Organization name
        instagram_username: Instagram handle (optional)
        stages_filter: List of stages to include (optional)
        include_setters: Whether to include setter performance (default: True)
        date_range: Date range string (e.g., "Jan 8 - Jan 14")

    Returns:
        List of Block Kit blocks
    """
    # Build header text
    header_text = f"Daily Update - {org_name}"
    if instagram_username:
        header_text = f"Daily Update - @{instagram_username}"

    # Build blocks
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text
            }
        }
    ]

    # Add date range if provided
    if date_range:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Period:* {date_range}"
                }
            ]
        })

    # Add divider
    blocks.append({"type": "divider"})

    # Add metrics section
    metrics_text = build_metrics_text(result, stages_filter)
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": metrics_text
        }
    })

    # Add stage changes
    blocks.append({"type": "divider"})
    stage_text = build_stage_changes_text(result, stages_filter)
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": stage_text
        }
    })

    # Add setter performance if requested
    if include_setters:
        blocks.append({"type": "divider"})
        setter_text = build_setter_performance_text(result, top_n=5)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": setter_text
            }
        })

    return blocks


def export_slack_message(
    result: AnalysisResult,
    org_name: str,
    instagram_username: str | None = None,
    stages_filter: list[str] | None = None,
    include_setters: bool = True,
    date_range: str | None = None
) -> dict[str, Any]:
    """
    Export analysis result as complete Slack message payload.

    Args:
        result: Analysis result
        org_name: Organization name
        instagram_username: Instagram handle (optional)
        stages_filter: List of stages to include (optional)
        include_setters: Whether to include setter performance (default: True)
        date_range: Date range string (e.g., "Jan 8 - Jan 14")

    Returns:
        Complete message payload with blocks and text
    """
    blocks = export_slack_blocks(
        result=result,
        org_name=org_name,
        instagram_username=instagram_username,
        stages_filter=stages_filter,
        include_setters=include_setters,
        date_range=date_range
    )

    fallback_text = f"Daily update for {org_name}"
    if date_range:
        fallback_text += f" ({date_range})"

    return {
        "blocks": blocks,
        "text": fallback_text
    }
