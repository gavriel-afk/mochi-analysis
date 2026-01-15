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
    sender: str  # "LEAD" or "CREATOR"
    content: str
    created_at: str  # ISO format timestamp
    attachments: Optional[list[dict]] = None

    # Optional fields from real Mochi export
    sender_id: Optional[str] = None
    recipient_id: Optional[str] = None
    sent_by: Optional[str] = None
    is_sent_from_mochi: Optional[bool] = False
    setter_email: Optional[str] = None
    status_change: Optional[str] = None  # For status change entries

    # Computed field for backwards compatibility
    @property
    def timestamp(self) -> str:
        """Alias for created_at."""
        return self.created_at

    @property
    def media(self) -> list[dict]:
        """Convert attachments to media format."""
        return self.attachments or []


class Conversation(BaseModel):
    """Conversation with messages."""
    conversation_id: str
    organization_id: str
    organization_name: Optional[str] = None
    current_stage: str  # NEW, QUALIFIED, etc.
    setter_email: Optional[str] = "Unassigned"
    messages: list[dict]  # Can contain messages or status changes

    # Optional fields
    setter_name: Optional[str] = None
    closer_email: Optional[str] = None
    closer_name: Optional[str] = None

    # Computed fields for backwards compatibility
    @property
    def id(self) -> str:
        """Alias for conversation_id."""
        return self.conversation_id

    @property
    def organization(self) -> str:
        """Alias for organization_id."""
        return self.organization_id

    @property
    def stage(self) -> str:
        """Map current_stage to standard stage names."""
        stage_mapping = {
            "NEW": "NEW_LEAD",
            "QUALIFIED": "QUALIFIED",
            "BOOKED": "BOOKED_CALL",
            "BOOKED_CALL": "BOOKED_CALL",
            "WON": "WON",
            "LOST": "LOST",
            "UNQUALIFIED": "UNQUALIFIED",
            "IN_CONTACT": "IN_CONTACT",
            "DEPOSIT": "DEPOSIT",
            "NO_SHOW": "NO_SHOW"
        }
        return stage_mapping.get(self.current_stage, self.current_stage)

    @property
    def created_at(self) -> str:
        """Get conversation creation time from first message."""
        actual_messages = [m for m in self.messages if isinstance(m, dict) and "sender" in m]
        if actual_messages:
            return actual_messages[0].get("created_at", "")
        return ""

    def get_actual_messages(self) -> list[Message]:
        """Filter out status changes and return only actual messages."""
        actual = []
        for msg in self.messages:
            if isinstance(msg, dict) and "sender" in msg and "content" in msg:
                try:
                    actual.append(Message(**msg))
                except Exception:
                    continue
        return actual


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
