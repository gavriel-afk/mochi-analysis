"""Main analysis orchestrator."""

from typing import List
from datetime import datetime, date
from mochi_analytics.core.models import (
    Conversation,
    AnalysisConfig,
    AnalysisResult
)
from mochi_analytics.core.metrics import calculate_core_metrics
from mochi_analytics.core.setters import (
    analyze_setters_by_sender,
    analyze_setters_by_assignment
)
from mochi_analytics.core.time_series import analyze_time_series


def analyze_conversations(
    conversations: List[Conversation],
    config: AnalysisConfig
) -> AnalysisResult:
    """
    Main entry point for conversation analysis.

    Args:
        conversations: List of conversations to analyze
        config: Analysis configuration

    Returns:
        AnalysisResult with all analysis features
    """
    # Determine date range
    if config.start_date and config.end_date:
        start_date = config.start_date
        end_date = config.end_date
    else:
        # Auto-detect from conversations
        start_date, end_date = detect_date_range(conversations)

    # Core metrics
    summary = calculate_core_metrics(conversations)

    # Time series
    time_series = analyze_time_series(
        conversations,
        start_date,
        end_date,
        config.timezone
    )

    # Setter analysis (both modes)
    setters_by_sender = analyze_setters_by_sender(conversations)
    setters_by_assignment = analyze_setters_by_assignment(conversations)

    # Convert SetterMetrics to dict for JSON serialization
    setters_by_sender_dict = {
        k: v.model_dump() for k, v in setters_by_sender.items()
    }
    setters_by_assignment_dict = {
        k: v.model_dump() for k, v in setters_by_assignment.items()
    }

    # Build metadata
    metadata = {
        "organization_id": conversations[0].organization if conversations else None,
        "organization_name": "Unknown",  # Will be filled by caller
        "timezone": config.timezone,
        "analysis_period": {
            "start": start_date.isoformat() if isinstance(start_date, date) else start_date,
            "end": end_date.isoformat() if isinstance(end_date, date) else end_date
        },
        "config": {
            "similarity_threshold": config.similarity_threshold,
            "include_avatars": config.include_avatars,
            "include_scripts": config.include_scripts,
            "include_objections": config.include_objections
        }
    }

    # Build result
    result = AnalysisResult(
        metadata=metadata,
        summary=summary,
        time_series=time_series,
        setters_by_sent_by=setters_by_sender_dict,
        setters_by_assignment=setters_by_assignment_dict,
        scripts=None,  # Will be added in Phase 3 (LLM features)
        objections=None,  # Will be added in Phase 3
        avatars=None  # Will be added in Phase 3
    )

    return result


def detect_date_range(conversations: List[Conversation]) -> tuple[date, date]:
    """
    Auto-detect date range from conversations.

    Returns:
        (start_date, end_date) tuple
    """
    if not conversations:
        today = date.today()
        return today, today

    # Parse all timestamps
    dates = []
    for conv in conversations:
        try:
            from mochi_analytics.core.metrics import parse_timestamp
            conv_time = parse_timestamp(conv.created_at)
            dates.append(conv_time.date())
        except Exception:
            continue

    if not dates:
        today = date.today()
        return today, today

    return min(dates), max(dates)


def analyze_conversations_simplified(
    conversations: List[Conversation],
    timezone: str = "UTC",
    start_date: date = None,
    end_date: date = None
) -> AnalysisResult:
    """
    Simplified analysis for daily Slack digests.

    Only runs:
    - Core metrics
    - Setters by_sent_by

    Skips:
    - Time series (not needed for Slack)
    - Setters by_assignment (not needed for Slack)
    - Scripts (LLM, expensive)
    - Objections (LLM, expensive)
    - Avatars (LLM, expensive)
    """
    # Auto-detect dates if not provided
    if not start_date or not end_date:
        start_date, end_date = detect_date_range(conversations)

    # Core metrics
    summary = calculate_core_metrics(conversations)

    # Setter analysis (by sender only)
    setters_by_sender = analyze_setters_by_sender(conversations)
    setters_by_sender_dict = {
        k: v.model_dump() for k, v in setters_by_sender.items()
    }

    # Minimal time series (for metadata)
    time_series = analyze_time_series(
        conversations,
        start_date,
        end_date,
        timezone
    )

    # Build metadata
    metadata = {
        "organization_id": conversations[0].organization if conversations else None,
        "organization_name": "Unknown",
        "timezone": timezone,
        "analysis_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "config": {
            "simplified": True,
            "include_avatars": False,
            "include_scripts": False,
            "include_objections": False
        }
    }

    return AnalysisResult(
        metadata=metadata,
        summary=summary,
        time_series=time_series,
        setters_by_sent_by=setters_by_sender_dict,
        setters_by_assignment={},  # Empty for simplified analysis
        scripts=None,
        objections=None,
        avatars=None
    )
