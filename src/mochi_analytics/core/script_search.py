"""Script search analysis - find messages matching query patterns using fuzzy matching."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pytz
from rapidfuzz import fuzz

from mochi_analytics.core.metrics import parse_timestamp
from mochi_analytics.core.models import Conversation

logger = logging.getLogger(__name__)


@dataclass
class ScriptSearchResult:
    """Result of script search analysis."""

    query: str
    label: str
    total_matches: int
    total_replies: int
    reply_rate: float
    setters_breakdown: dict[str, dict[str, int | float]]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "label": self.label,
            "total_matches": self.total_matches,
            "total_replies": self.total_replies,
            "reply_rate": self.reply_rate,
            "setters_breakdown": self.setters_breakdown
        }


def find_similar_messages(
    conversations: list[Conversation],
    query_message: str,
    timezone: str = "UTC",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    similarity_threshold: float = 85.0,
    sender_filter: str = "CREATOR",
    match_type: str = "token_set"
) -> dict:
    """
    Find messages similar to a query using fuzzy matching.

    Args:
        conversations: List of conversations to search
        query_message: The message pattern to search for
        timezone: IANA timezone for date filtering
        date_from: Start date filter (optional)
        date_to: End date filter (optional)
        similarity_threshold: Minimum similarity score (0-100)
        sender_filter: Filter by sender type ("CREATOR" or "LEAD")
        match_type: Fuzzy match type ("ratio", "token_set", "partial")

    Returns:
        Dict with total_matches, total_replies, reply_rate, setters breakdown
    """
    tz = pytz.timezone(timezone)

    # Select matching function based on match_type
    if match_type == "ratio":
        match_func = fuzz.ratio
    elif match_type == "partial":
        match_func = fuzz.partial_ratio
    else:  # default: token_set
        match_func = fuzz.token_set_ratio

    total_matches = 0
    total_replies = 0
    setters_breakdown: dict[str, dict[str, int | float]] = defaultdict(
        lambda: {"matches": 0, "replies": 0, "reply_rate": 0.0}
    )
    all_matches = []

    query_normalized = query_message.lower().strip()

    for conv in conversations:
        messages = conv.get_actual_messages()

        for i, msg in enumerate(messages):
            # Filter by sender
            if msg.sender != sender_filter:
                continue

            # Date filtering
            if date_from or date_to:
                try:
                    msg_time = parse_timestamp(msg.timestamp)
                    msg_date = msg_time.astimezone(tz).date()

                    if date_from and msg_date < date_from:
                        continue
                    if date_to and msg_date > date_to:
                        continue
                except Exception:
                    continue

            # Fuzzy match
            content_normalized = msg.content.lower().strip()
            similarity = match_func(query_normalized, content_normalized)

            if similarity >= similarity_threshold:
                total_matches += 1

                # Track setter (use sent_by if available, else setter_email from conversation)
                setter = msg.sent_by or conv.setter_email or "Unknown"
                setters_breakdown[setter]["matches"] += 1

                # Check for reply (next LEAD message)
                has_reply = False
                for future_msg in messages[i + 1:]:
                    if future_msg.sender == "LEAD":
                        has_reply = True
                        break

                if has_reply:
                    total_replies += 1
                    setters_breakdown[setter]["replies"] += 1

                all_matches.append({
                    "conversation_id": conv.id,
                    "message_content": msg.content[:100],
                    "similarity": similarity,
                    "has_reply": has_reply,
                    "setter": setter
                })

    # Calculate reply rate
    reply_rate = (total_replies / total_matches * 100) if total_matches > 0 else 0.0

    # Add reply_rate to setters breakdown
    for setter, data in setters_breakdown.items():
        matches = data["matches"]
        replies = data["replies"]
        data["reply_rate"] = (replies / matches * 100) if matches > 0 else 0.0

    return {
        "total_matches": total_matches,
        "total_replies": total_replies,
        "reply_rate": round(reply_rate, 1),
        "setters_breakdown": dict(setters_breakdown),
        "all_matches": all_matches
    }


def run_script_searches(
    conversations: list[Conversation],
    script_configs: list,  # List of ScriptAnalysisConfig objects
    timezone: str = "UTC",
    target_date: Optional[date] = None
) -> list[ScriptSearchResult]:
    """
    Run multiple script searches and return results.

    Args:
        conversations: Conversations to search
        script_configs: List of ScriptAnalysisConfig objects
        timezone: IANA timezone
        target_date: Specific date to analyze (usually yesterday)

    Returns:
        List of ScriptSearchResult objects
    """
    results = []

    for config in script_configs:
        try:
            search_result = find_similar_messages(
                conversations=conversations,
                query_message=config.query,
                timezone=timezone,
                date_from=target_date,
                date_to=target_date,
                similarity_threshold=config.threshold,
                sender_filter="CREATOR",
                match_type=config.match_type
            )

            results.append(ScriptSearchResult(
                query=config.query,
                label=config.label,
                total_matches=search_result["total_matches"],
                total_replies=search_result["total_replies"],
                reply_rate=search_result["reply_rate"],
                setters_breakdown=search_result["setters_breakdown"]
            ))

            logger.info(
                f"Script search '{config.label}': "
                f"{search_result['total_matches']} matches, "
                f"{search_result['reply_rate']}% reply rate"
            )

        except Exception as e:
            logger.error(f"Script search failed for '{config.label}': {e}")

    return results
