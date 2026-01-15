"""Unit tests for main analyzer orchestrator."""

import pytest
import json
from pathlib import Path
from datetime import date
from mochi_analytics.core.models import Conversation, AnalysisConfig
from mochi_analytics.core.analyzer import analyze_conversations, detect_date_range


@pytest.fixture
def sample_conversations():
    """Load sample conversations from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_conversations.json"
    with open(fixture_path, 'r') as f:
        data = json.load(f)
    return [Conversation(**conv) for conv in data]


def test_analyze_conversations_returns_result(sample_conversations):
    """Test that analyzer returns AnalysisResult."""
    config = AnalysisConfig(
        timezone="UTC",
        start_date=date(2025, 1, 15),
        end_date=date(2025, 1, 16)
    )

    result = analyze_conversations(sample_conversations, config)

    assert result is not None
    assert result.summary.total_conversations == 3
    assert result.metadata is not None
    assert result.metadata["timezone"] == "UTC"


def test_analyze_conversations_includes_setters(sample_conversations):
    """Test that setter analysis is included."""
    config = AnalysisConfig(timezone="UTC")

    result = analyze_conversations(sample_conversations, config)

    # Should have both setter analysis modes
    assert len(result.setters_by_sent_by) > 0
    assert len(result.setters_by_assignment) > 0

    # john@example.com appears in 2 conversations
    assert "john@example.com" in result.setters_by_assignment


def test_analyze_conversations_time_series(sample_conversations):
    """Test that time series analysis is included."""
    config = AnalysisConfig(
        timezone="UTC",
        start_date=date(2025, 1, 15),
        end_date=date(2025, 1, 16)
    )

    result = analyze_conversations(sample_conversations, config)

    # Should have daily breakdowns for 2 days
    assert len(result.time_series.stage_changes_by_day) == 2


def test_detect_date_range(sample_conversations):
    """Test auto-detection of date range."""
    start, end = detect_date_range(sample_conversations)

    assert start == date(2025, 1, 15)
    assert end == date(2025, 1, 16)


def test_detect_date_range_empty():
    """Test date range detection with empty list."""
    start, end = detect_date_range([])

    # Should return today's date
    today = date.today()
    assert start == today
    assert end == today
