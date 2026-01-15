"""Unit tests for core metrics calculation."""

import pytest
import json
from pathlib import Path
from mochi_analytics.core.models import Conversation
from mochi_analytics.core.metrics import calculate_core_metrics


@pytest.fixture
def sample_conversations():
    """Load sample conversations from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_conversations.json"
    with open(fixture_path, 'r') as f:
        data = json.load(f)
    return [Conversation(**conv) for conv in data]


def test_calculate_core_metrics_total_conversations(sample_conversations):
    """Test total conversation count."""
    result = calculate_core_metrics(sample_conversations)
    assert result.total_conversations == 3


def test_calculate_core_metrics_message_counts(sample_conversations):
    """Test message counting (sent/received)."""
    result = calculate_core_metrics(sample_conversations)

    # Manually count from sample data
    # Conv 1: 2 LEAD, 1 CREATOR
    # Conv 2: 2 LEAD, 1 CREATOR
    # Conv 3: 1 LEAD, 1 CREATOR
    # Total: 5 LEAD, 3 CREATOR

    assert result.total_messages_received == 5
    assert result.total_messages_sent == 3
    assert result.total_messages_sent_from_mochi == 3


def test_calculate_core_metrics_reply_rate(sample_conversations):
    """Test 48-hour reply rate calculation."""
    result = calculate_core_metrics(sample_conversations)

    # All 3 CREATOR messages got replies within 48h
    assert result.creator_messages_with_reply_within_48h == 3
    assert result.creator_message_reply_rate_within_48h == 100.0


def test_calculate_core_metrics_stage_changes(sample_conversations):
    """Test stage change counting."""
    result = calculate_core_metrics(sample_conversations)

    assert result.stage_changes["NEW_LEAD"] == 1
    assert result.stage_changes["QUALIFIED"] == 1
    assert result.stage_changes["BOOKED_CALL"] == 1


def test_calculate_core_metrics_media(sample_conversations):
    """Test media breakdown."""
    result = calculate_core_metrics(sample_conversations)

    # Only 1 image in conv_002
    assert result.media.total == 1
    assert result.media.by_type.get("image", 0) == 1


def test_calculate_core_metrics_empty_list():
    """Test with empty conversation list."""
    result = calculate_core_metrics([])

    assert result.total_conversations == 0
    assert result.total_messages_received == 0
    assert result.total_messages_sent == 0
    assert result.creator_message_reply_rate_within_48h == 0.0
