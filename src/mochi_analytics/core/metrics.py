"""Core metrics calculation."""

from datetime import datetime, timedelta
from typing import List, Tuple
from collections import Counter
from mochi_analytics.core.models import Conversation, Summary, MediaBreakdown
from mochi_analytics.core.constants import STAGE_TYPES, MEDIA_TYPES
import statistics


def calculate_core_metrics(conversations: List[Conversation]) -> Summary:
    """
    Calculate core metrics from conversations.

    Returns:
        Summary with all core metrics calculated
    """
    total_conversations = len(conversations)

    # Message counts
    messages_received = 0
    messages_sent = 0
    messages_from_mochi = 0

    # Reply tracking
    creator_messages_with_reply = 0
    total_creator_messages = 0
    reply_delays = []

    # Stage changes
    stage_changes = Counter()

    # Media breakdown
    media_count = 0
    media_by_type = Counter()

    for conv in conversations:
        # Count stage
        if conv.stage:
            stage_changes[conv.stage] += 1

        # Get actual messages (filter out status changes)
        messages = conv.get_actual_messages()

        # Process messages
        for i, msg in enumerate(messages):
            # Count by sender
            if msg.sender == "LEAD":
                messages_received += 1
            elif msg.sender == "CREATOR":
                messages_sent += 1
                messages_from_mochi += 1
                total_creator_messages += 1

                # Check if this creator message got a reply within 48h
                reply_found = False
                msg_time = parse_timestamp(msg.timestamp)

                # Look for next LEAD message
                for future_msg in messages[i+1:]:
                    if future_msg.sender == "LEAD":
                        future_time = parse_timestamp(future_msg.timestamp)
                        time_diff = (future_time - msg_time).total_seconds()

                        if time_diff <= 48 * 3600:  # 48 hours in seconds
                            reply_found = True
                            reply_delays.append(time_diff)
                        break

                if reply_found:
                    creator_messages_with_reply += 1

            # Count media
            if msg.media:
                for media_item in msg.media:
                    media_count += 1
                    media_type = media_item.get('type', 'other')
                    if media_type in MEDIA_TYPES:
                        media_by_type[media_type] += 1
                    else:
                        media_by_type['other'] += 1

    # Calculate reply rate
    reply_rate = (
        (creator_messages_with_reply / total_creator_messages * 100)
        if total_creator_messages > 0 else 0.0
    )

    # Calculate median reply delay
    median_delay = int(statistics.median(reply_delays)) if reply_delays else 0

    # Build media breakdown
    media_breakdown = MediaBreakdown(
        total=media_count,
        by_type=dict(media_by_type)
    )

    return Summary(
        total_conversations=total_conversations,
        total_messages_received=messages_received,
        total_messages_sent=messages_sent,
        total_messages_sent_from_mochi=messages_from_mochi,
        creator_messages_with_reply_within_48h=creator_messages_with_reply,
        creator_message_reply_rate_within_48h=round(reply_rate, 2),
        median_reply_delay_seconds=median_delay,
        stage_changes=dict(stage_changes),
        media=media_breakdown
    )


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO format timestamp to datetime.

    Handles multiple formats:
    - 2025-01-15T10:30:00Z
    - 2025-01-15T10:30:00+00:00
    - 2025-01-15T10:30:00
    """
    # Remove 'Z' if present and replace with +00:00
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str[:-1] + '+00:00'

    try:
        # Try parsing with timezone
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        # Fallback: parse without timezone and assume UTC
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            # Last resort: parse date only
            return datetime.fromisoformat(timestamp_str.split('T')[0])


def calculate_time_difference_seconds(start: str, end: str) -> float:
    """Calculate time difference in seconds between two timestamps."""
    start_dt = parse_timestamp(start)
    end_dt = parse_timestamp(end)
    return (end_dt - start_dt).total_seconds()
