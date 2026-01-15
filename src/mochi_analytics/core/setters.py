"""Setter analysis - per-setter performance metrics."""

from typing import List, Dict
from collections import Counter, defaultdict
from mochi_analytics.core.models import Conversation, SetterMetrics
from mochi_analytics.core.metrics import parse_timestamp, calculate_time_difference_seconds
from mochi_analytics.core.constants import TIME_BINS
import statistics


def analyze_setters_by_sender(conversations: List[Conversation]) -> Dict[str, SetterMetrics]:
    """
    Analyze setter performance based on who sent each message.

    Each message is attributed to the person who sent it.
    Shows individual message-sending performance.
    """
    setter_data = defaultdict(lambda: {
        'conversations': set(),
        'messages_sent': 0,
        'creator_messages_with_reply': 0,
        'total_creator_messages': 0,
        'reply_delays': [],
        'stage_changes': Counter(),
        'setter_activity': Counter(),
        'lead_activity': Counter(),
        'delayed_responses': Counter()
    })

    for conv in conversations:
        # Track stage for each setter involved
        setters_in_conv = set()

        for i, msg in enumerate(conv.messages):
            if msg.sender == "CREATOR":
                # Attribute to sender (could extract from msg if available, or use setter_email)
                setter = conv.setter_email  # Default to conversation owner
                setters_in_conv.add(setter)

                data = setter_data[setter]
                data['conversations'].add(conv.id)
                data['messages_sent'] += 1
                data['total_creator_messages'] += 1

                # Time bin
                msg_time = parse_timestamp(msg.timestamp)
                time_bin = get_time_bin(msg_time.hour)
                data['setter_activity'][time_bin] += 1

                # Check for reply
                reply_found = False
                for future_msg in conv.messages[i+1:]:
                    if future_msg.sender == "LEAD":
                        future_time = parse_timestamp(future_msg.timestamp)
                        time_diff = (future_time - msg_time).total_seconds()

                        if time_diff <= 48 * 3600:
                            reply_found = True
                            data['reply_delays'].append(time_diff)
                        break

                if reply_found:
                    data['creator_messages_with_reply'] += 1

            elif msg.sender == "LEAD":
                # Track lead activity (for all setters in conversation)
                msg_time = parse_timestamp(msg.timestamp)
                time_bin = get_time_bin(msg_time.hour)

                for setter in setters_in_conv:
                    setter_data[setter]['lead_activity'][time_bin] += 1

        # Add stage changes for all setters involved
        if conv.stage:
            for setter in setters_in_conv:
                setter_data[setter]['stage_changes'][conv.stage] += 1

    # Convert to SetterMetrics
    result = {}
    for setter, data in setter_data.items():
        reply_rate = (
            (data['creator_messages_with_reply'] / data['total_creator_messages'] * 100)
            if data['total_creator_messages'] > 0 else 0.0
        )

        median_delay = int(statistics.median(data['reply_delays'])) if data['reply_delays'] else 0

        result[setter] = SetterMetrics(
            total_conversations=len(data['conversations']),
            total_messages_sent_from_mochi=data['messages_sent'],
            creator_messages_with_reply_within_48h=data['creator_messages_with_reply'],
            creator_message_reply_rate_within_48h=round(reply_rate, 2),
            median_reply_delay_seconds=median_delay,
            stage_changes=dict(data['stage_changes']),
            setter_activity_by_time=dict(data['setter_activity']),
            lead_activity_by_time=dict(data['lead_activity']),
            delayed_responses_by_time=dict(data['delayed_responses'])
        )

    return result


def analyze_setters_by_assignment(conversations: List[Conversation]) -> Dict[str, SetterMetrics]:
    """
    Analyze setter performance based on conversation assignment.

    Entire conversation is attributed to assigned setter (setter_email).
    Shows overall conversation ownership.
    """
    setter_data = defaultdict(lambda: {
        'conversations': set(),
        'messages_sent': 0,
        'creator_messages_with_reply': 0,
        'total_creator_messages': 0,
        'reply_delays': [],
        'stage_changes': Counter(),
        'setter_activity': Counter(),
        'lead_activity': Counter(),
        'delayed_responses': Counter()
    })

    for conv in conversations:
        setter = conv.setter_email
        data = setter_data[setter]

        # Add conversation
        data['conversations'].add(conv.id)

        # Add stage
        if conv.stage:
            data['stage_changes'][conv.stage] += 1

        # Process messages
        for i, msg in enumerate(conv.messages):
            if msg.sender == "CREATOR":
                data['messages_sent'] += 1
                data['total_creator_messages'] += 1

                # Time bin
                msg_time = parse_timestamp(msg.timestamp)
                time_bin = get_time_bin(msg_time.hour)
                data['setter_activity'][time_bin] += 1

                # Check for reply
                reply_found = False
                for future_msg in conv.messages[i+1:]:
                    if future_msg.sender == "LEAD":
                        future_time = parse_timestamp(future_msg.timestamp)
                        time_diff = (future_time - msg_time).total_seconds()

                        if time_diff <= 48 * 3600:
                            reply_found = True
                            data['reply_delays'].append(time_diff)
                        break

                if reply_found:
                    data['creator_messages_with_reply'] += 1

            elif msg.sender == "LEAD":
                # Track lead activity
                msg_time = parse_timestamp(msg.timestamp)
                time_bin = get_time_bin(msg_time.hour)
                data['lead_activity'][time_bin] += 1

    # Convert to SetterMetrics
    result = {}
    for setter, data in setter_data.items():
        reply_rate = (
            (data['creator_messages_with_reply'] / data['total_creator_messages'] * 100)
            if data['total_creator_messages'] > 0 else 0.0
        )

        median_delay = int(statistics.median(data['reply_delays'])) if data['reply_delays'] else 0

        result[setter] = SetterMetrics(
            total_conversations=len(data['conversations']),
            total_messages_sent_from_mochi=data['messages_sent'],
            creator_messages_with_reply_within_48h=data['creator_messages_with_reply'],
            creator_message_reply_rate_within_48h=round(reply_rate, 2),
            median_reply_delay_seconds=median_delay,
            stage_changes=dict(data['stage_changes']),
            setter_activity_by_time=dict(data['setter_activity']),
            lead_activity_by_time=dict(data['lead_activity']),
            delayed_responses_by_time=dict(data['delayed_responses'])
        )

    return result


def get_time_bin(hour: int) -> str:
    """
    Convert hour (0-23) to time bin (e.g., '09_12').

    Args:
        hour: Hour of day (0-23)

    Returns:
        Time bin string (e.g., '09_12' for 9 AM - 12 PM)
    """
    if 0 <= hour < 3:
        return "00_03"
    elif 3 <= hour < 6:
        return "03_06"
    elif 6 <= hour < 9:
        return "06_09"
    elif 9 <= hour < 12:
        return "09_12"
    elif 12 <= hour < 15:
        return "12_15"
    elif 15 <= hour < 18:
        return "15_18"
    elif 18 <= hour < 21:
        return "18_21"
    else:  # 21-24
        return "21_24"
