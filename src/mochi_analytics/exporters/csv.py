"""
CSV export for Framer CMS format.
"""

import csv
import io
from pathlib import Path

try:
    import tomli as tomllib  # Python < 3.11
except ImportError:
    import tomllib  # Python >= 3.11

from mochi_analytics.core.models import AnalysisResult


def load_cms_templates() -> dict:
    """Load CMS templates from config file."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "cms_templates.toml"

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def format_hours(seconds: int | float) -> str:
    """Format seconds as human-readable hours/minutes."""
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def build_setter_table_html(setters_data: dict | None) -> str:
    """Build HTML table for setter performance."""
    if not setters_data or not setters_data.get("setters"):
        return "<p>No setter data available</p>"

    setters = setters_data["setters"]

    html = ['<table style="width:100%; border-collapse: collapse;">']
    html.append("<thead>")
    html.append("<tr>")
    html.append('<th style="text-align:left; padding:8px; border-bottom:2px solid #ddd;">Setter</th>')
    html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Conversations</th>')
    html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Messages Sent</th>')
    html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Reply Rate</th>')
    html.append("</tr>")
    html.append("</thead>")
    html.append("<tbody>")

    for setter in setters[:10]:  # Top 10
        email = setter.get("setter_email", "Unknown")
        convos = setter.get("total_conversations", 0)
        msgs = setter.get("messages_sent", 0)
        reply_rate = setter.get("reply_rate_within_48h")

        reply_display = f"{reply_rate:.1f}%" if reply_rate is not None else "N/A"

        html.append("<tr>")
        html.append(f'<td style="padding:8px; border-bottom:1px solid #eee;">{email}</td>')
        html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{convos}</td>')
        html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{msgs}</td>')
        html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{reply_display}</td>')
        html.append("</tr>")

    html.append("</tbody>")
    html.append("</table>")

    return "".join(html)


def build_scripts_table_html(scripts_data: dict | None) -> str:
    """Build HTML table for script analysis."""
    if not scripts_data:
        return "<p>No script data available</p>"

    html = ['<div style="margin-bottom: 20px;">']

    for category in ["opener", "follow_up", "nurture_discovery", "cta"]:
        patterns = scripts_data.get(category, [])
        if not patterns:
            continue

        category_name = category.replace("_", " ").title()
        html.append(f"<h4>{category_name}</h4>")
        html.append('<table style="width:100%; border-collapse: collapse; margin-bottom:20px;">')
        html.append("<thead>")
        html.append("<tr>")
        html.append('<th style="text-align:left; padding:8px; border-bottom:2px solid #ddd;">Script</th>')
        html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Uses</th>')
        html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Reply Rate</th>')
        html.append("</tr>")
        html.append("</thead>")
        html.append("<tbody>")

        for pattern in patterns[:5]:  # Top 5 per category
            script = pattern.get("representative_text", "")[:100]
            count = pattern.get("total_occurrences", 0)
            reply_rate = pattern.get("reply_rate")

            # reply_rate might be string (e.g., "87.5%") or float
            if reply_rate is not None:
                if isinstance(reply_rate, str):
                    reply_display = reply_rate
                else:
                    reply_display = f"{reply_rate:.1f}%"
            else:
                reply_display = "N/A"

            html.append("<tr>")
            html.append(f'<td style="padding:8px; border-bottom:1px solid #eee;">{script}...</td>')
            html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{count}</td>')
            html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{reply_display}</td>')
            html.append("</tr>")

        html.append("</tbody>")
        html.append("</table>")

    html.append("</div>")
    return "".join(html)


def build_objections_table_html(objections_data: dict | None) -> str:
    """Build HTML table for objection analysis."""
    if not objections_data or not objections_data.get("objection_groups"):
        return "<p>No objection data available</p>"

    groups = objections_data["objection_groups"]
    total = objections_data.get("total_analyzed", 1)

    html = ['<table style="width:100%; border-collapse: collapse;">']
    html.append("<thead>")
    html.append("<tr>")
    html.append('<th style="text-align:left; padding:8px; border-bottom:2px solid #ddd;">Objection Type</th>')
    html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Count</th>')
    html.append('<th style="text-align:right; padding:8px; border-bottom:2px solid #ddd;">Percentage</th>')
    html.append("</tr>")
    html.append("</thead>")
    html.append("<tbody>")

    for group in groups:
        category = group.get("category", "").replace("_", " ").title()
        count = group.get("count", 0)
        percentage = (count / total * 100) if total > 0 else 0

        html.append("<tr>")
        html.append(f'<td style="padding:8px; border-bottom:1px solid #eee;">{category}</td>')
        html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{count}</td>')
        html.append(f'<td style="text-align:right; padding:8px; border-bottom:1px solid #eee;">{percentage:.1f}%</td>')
        html.append("</tr>")

    html.append("</tbody>")
    html.append("</table>")

    return "".join(html)


def export_framer_csv(result: AnalysisResult) -> str:
    """
    Export analysis result as CSV for Framer CMS.

    Args:
        result: Analysis result to export

    Returns:
        CSV string
    """
    templates = load_cms_templates()

    # Extract metadata
    org_name = result.metadata.get("organization_name", "Unknown Organization")
    period = result.metadata.get("analysis_period", {})
    start_date = period.get("start", "")
    end_date = period.get("end", "")

    # Extract metrics
    summary = result.summary
    new_leads = summary.stage_changes.get("NEW_LEAD", 0)
    qualified = summary.stage_changes.get("QUALIFIED", 0)
    booked = summary.stage_changes.get("BOOKED_CALL", 0)

    # Calculate booking rate
    booking_rate = (booked / new_leads * 100) if new_leads > 0 else 0

    # Build title
    title = templates["title"]["template"].format(
        org_name=org_name,
        start_date=start_date,
        end_date=end_date
    )

    # Build description
    description = templates["description"]["template"]

    # Build metrics
    total_inbound_text = templates["total_inbound"]["text"].format(value=new_leads)
    total_qualified_text = templates["total_qualified"]["text"].format(value=qualified)
    total_booked_text = templates["total_booked"]["text"].format(value=booked)

    # Format booking rate (avoiding double formatting)
    booking_rate_str = f"{booking_rate:.1f}"
    booking_rate_heading = templates["booking_rate"]["heading"].replace("{value}", booking_rate_str)
    booking_rate_body = templates["booking_rate"]["text"].replace("{value}", booking_rate_str)
    booking_rate_body = booking_rate_body.replace("{booked}", str(booked))
    booking_rate_body = booking_rate_body.replace("{leads}", str(new_leads))
    booking_rate_text = booking_rate_heading + "<br>" + booking_rate_body

    # Build reply rate
    reply_rate = summary.creator_message_reply_rate_within_48h
    reply_rate_text = ""
    if reply_rate is not None:
        reply_rate_str = f"{reply_rate:.1f}"
        reply_rate_text = templates["reply_rate"]["text"].replace("{value}", reply_rate_str)

    # Build median reply time
    median_delay = summary.median_reply_delay_seconds
    median_reply_text = ""
    if median_delay is not None:
        formatted_time = format_hours(median_delay)
        median_reply_text = templates["median_reply_time"]["text"].format(value=formatted_time)

    # Build HTML tables
    setters_html = build_setter_table_html(result.setters_by_assignment)
    scripts_html = build_scripts_table_html(result.scripts)
    objections_html = build_objections_table_html(result.objections)

    # Build charts placeholder (empty for now)
    charts_text = ""

    # Assemble CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Title",
        "Description",
        "New Leads",
        "Qualified",
        "Booked Calls",
        "Booking Rate",
        "Reply Rate",
        "Median Reply Time",
        "Charts",
        "Setters",
        "Scripts",
        "Objections"
    ])

    # Write data row
    writer.writerow([
        title,
        description,
        total_inbound_text,
        total_qualified_text,
        total_booked_text,
        booking_rate_text,
        reply_rate_text,
        median_reply_text,
        charts_text,
        setters_html,
        scripts_html,
        objections_html
    ])

    return output.getvalue()
