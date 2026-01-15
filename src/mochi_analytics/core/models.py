"""Pydantic models for Mochi Analytics."""

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


# ===== Input Models =====

class AnalysisConfig(BaseModel):
    """Configuration for analysis run."""
    timezone: str = "UTC"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    similarity_threshold: float = 85.0
    include_avatars: bool = False
    include_scripts: bool = True
    include_objections: bool = True
    batch_size: int = 50
    max_concurrent_api_calls: int = 5


class Message(BaseModel):
    """Single message in conversation."""
    id: str
    sender: str  # "LEAD" or "CREATOR"
    content: str
    timestamp: str  # ISO format
    media: list[dict] = Field(default_factory=list)


class Conversation(BaseModel):
    """Conversation with messages."""
    id: str
    organization: str
    stage: str  # One of STAGE_TYPES
    setter_email: str
    created_at: str
    messages: list[Message]


# ===== Output Models =====

class MediaBreakdown(BaseModel):
    """Media attachment breakdown."""
    total: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)


class Summary(BaseModel):
    """Core metrics summary."""
    total_conversations: int = 0
    total_messages_received: int = 0
    total_messages_sent: int = 0
    total_messages_sent_from_mochi: int = 0
    creator_messages_with_reply_within_48h: int = 0
    creator_message_reply_rate_within_48h: float = 0.0
    median_reply_delay_seconds: int = 0
    stage_changes: dict[str, int] = Field(default_factory=dict)
    media: MediaBreakdown = Field(default_factory=MediaBreakdown)


class DayStages(BaseModel):
    """Stage changes for one day."""
    date: str  # "Mon, 01 Jan 24"
    date_iso: str  # "2024-01-01"
    stages: dict[str, int] = Field(default_factory=dict)


class TimeSeries(BaseModel):
    """Time series data."""
    stage_changes_by_day: list[DayStages] = Field(default_factory=list)
    lead_activity_by_time: dict[str, int] = Field(default_factory=dict)
    setter_activity_by_time: dict[str, int] = Field(default_factory=dict)
    delayed_responses_by_time: dict[str, int] = Field(default_factory=dict)


class SetterMetrics(BaseModel):
    """Per-setter metrics."""
    total_conversations: int = 0
    total_messages_sent_from_mochi: int = 0
    creator_messages_with_reply_within_48h: int = 0
    creator_message_reply_rate_within_48h: float = 0.0
    median_reply_delay_seconds: int = 0
    stage_changes: dict[str, int] = Field(default_factory=dict)
    setter_activity_by_time: dict[str, int] = Field(default_factory=dict)
    lead_activity_by_time: dict[str, int] = Field(default_factory=dict)
    delayed_responses_by_time: dict[str, int] = Field(default_factory=dict)


class ScriptPattern(BaseModel):
    """Script cluster."""
    id: str
    example: str
    times_sent: int = 0
    replies: int = 0
    reply_rate: str = "0.0%"
    category: Optional[str] = None  # opener, follow_up, nurture_discovery, cta
    topic: Optional[str] = None


class ObjectionGroup(BaseModel):
    """Objection category."""
    name: str
    description: str
    count: int = 0
    percentage: float = 0.0


class AvatarProfile(BaseModel):
    """Avatar persona profile."""
    id: str
    count: int = 0
    percentage: float = 0.0
    job: Optional[str] = None
    age_range: Optional[str] = None
    motivation: Optional[str] = None
    main_objection: Optional[str] = None


class AnalysisResult(BaseModel):
    """Complete analysis output."""
    metadata: dict
    summary: Summary
    time_series: TimeSeries
    setters_by_sent_by: dict[str, SetterMetrics] = Field(default_factory=dict)
    setters_by_assignment: dict[str, SetterMetrics] = Field(default_factory=dict)
    scripts: Optional[dict] = None  # Script patterns
    objections: Optional[dict] = None  # Objection analysis
    avatars: Optional[dict] = None  # Avatar profiles
