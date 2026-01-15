"""Time series analysis - daily breakdowns and activity patterns."""

from typing import List
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from mochi_analytics.core.models import Conversation, TimeSeries, DayStages
from mochi_analytics.core.metrics import parse_timestamp
from mochi_analytics.core.setters import get_time_bin
from mochi_analytics.core.constants import STAGE_TYPES
import pytz


def analyze_time_series(
    conversations: List[Conversation],
    start_date: datetime,
    end_date: datetime,
    timezone_str: str = "UTC"
) -> TimeSeries:
    """
    Analyze time series data for conversations.

    Returns:
        TimeSeries with daily stage changes and activity by time of day
    """
    tz = pytz.timezone(timezone_str)

    # Initialize data structures
    daily_stages = defaultdict(Counter)

    # Initialize all time bins with 0
    all_time_bins = ["00_03", "03_06", "06_09", "09_12", "12_15", "15_18", "18_21", "21_24"]
    lead_activity = {bin: 0 for bin in all_time_bins}
    setter_activity = {bin: 0 for bin in all_time_bins}
    delayed_responses = {bin: 0 for bin in all_time_bins}

    # Process conversations
    for conv in conversations:
        # Parse conversation creation time
        conv_time = parse_timestamp(conv.created_at)
        if conv_time.tzinfo is None:
            conv_time = pytz.UTC.localize(conv_time)
        conv_time_local = conv_time.astimezone(tz)
        conv_date = conv_time_local.date()

        # Count stage change on creation date
        if conv.stage:
            daily_stages[conv_date][conv.stage] += 1

        # Get actual messages (filter out status changes)
        messages = conv.get_actual_messages()

        # Process messages for activity patterns
        for i, msg in enumerate(messages):
            msg_time = parse_timestamp(msg.timestamp)
            if msg_time.tzinfo is None:
                msg_time = pytz.UTC.localize(msg_time)
            msg_time_local = msg_time.astimezone(tz)

            time_bin = get_time_bin(msg_time_local.hour)

            if msg.sender == "LEAD":
                lead_activity[time_bin] = lead_activity.get(time_bin, 0) + 1
            elif msg.sender == "CREATOR":
                setter_activity[time_bin] = setter_activity.get(time_bin, 0) + 1

                # Check for delayed response (> 24h before creator replied)
                if i > 0:
                    prev_msg = messages[i-1]
                    if prev_msg.sender == "LEAD":
                        prev_time = parse_timestamp(prev_msg.timestamp)
                        if prev_time.tzinfo is None:
                            prev_time = pytz.UTC.localize(prev_time)

                        delay = (msg_time - prev_time).total_seconds()
                        if delay > 24 * 3600:  # More than 24 hours
                            delayed_responses[time_bin] = delayed_responses.get(time_bin, 0) + 1

    # Build day-by-day breakdown
    stage_changes_by_day = []
    current_date = start_date.date() if isinstance(start_date, datetime) else start_date

    if isinstance(end_date, datetime):
        end_date = end_date.date()

    while current_date <= end_date:
        # Format date
        date_str = current_date.strftime("%a, %d %b %y")  # "Mon, 01 Jan 24"
        date_iso = current_date.isoformat()  # "2024-01-01"

        # Initialize all stages with 0
        stages = {stage: 0 for stage in STAGE_TYPES}

        # Update with actual counts for this day
        day_stages = daily_stages.get(current_date, {})
        for stage, count in day_stages.items():
            if stage in stages:
                stages[stage] = count

        stage_changes_by_day.append(DayStages(
            date=date_str,
            date_iso=date_iso,
            stages=stages
        ))

        current_date += timedelta(days=1)

    return TimeSeries(
        stage_changes_by_day=stage_changes_by_day,
        lead_activity_by_time=lead_activity,
        setter_activity_by_time=setter_activity,
        delayed_responses_by_time=delayed_responses
    )
