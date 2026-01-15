#!/usr/bin/env python3
"""Test analysis on real Mochi export data."""

import json
import sys
from pathlib import Path
from datetime import date

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mochi_analytics.core.models import Conversation, Message, AnalysisConfig
from mochi_analytics.core.analyzer import analyze_conversations


def convert_mochi_export_to_model(export_data: list) -> list[Conversation]:
    """
    Convert real Mochi export format to our Conversation model.

    Real format:
    - conversation_id
    - organization_id
    - current_stage (NEW, QUALIFIED, etc.)
    - messages: list with sender, content, created_at, attachments
    - setter_email

    Our model expects:
    - id
    - organization
    - stage
    - setter_email
    - created_at (conversation creation time)
    - messages: list[Message] with id, sender, content, timestamp, media
    """
    conversations = []

    for conv_data in export_data:
        # Extract conversation-level data
        conv_id = conv_data.get("conversation_id")
        org_id = conv_data.get("organization_id")
        stage = conv_data.get("current_stage", "NEW")
        setter_email = conv_data.get("setter_email", "unknown@example.com")

        # Find conversation creation time (first message timestamp)
        raw_messages = conv_data.get("messages", [])
        if not raw_messages:
            continue

        # Filter out status_change entries, only keep actual messages
        actual_messages = [
            msg for msg in raw_messages
            if "sender" in msg and "content" in msg
        ]

        if not actual_messages:
            continue

        # Use first message timestamp as conversation creation
        created_at = actual_messages[0].get("created_at")

        # Convert messages to our Message model
        messages = []
        for i, msg in enumerate(actual_messages):
            # Generate message ID if not present
            msg_id = f"{conv_id}_msg_{i}"

            sender = msg.get("sender", "UNKNOWN")
            content = msg.get("content", "")
            timestamp = msg.get("created_at")
            attachments = msg.get("attachments", [])

            # Convert attachments to media format
            media = []
            if attachments:
                for attachment in attachments:
                    media.append({
                        "type": attachment.get("type", "file"),
                        "url": attachment.get("url", "")
                    })

            messages.append(Message(
                id=msg_id,
                sender=sender,
                content=content,
                timestamp=timestamp,
                media=media
            ))

        # Map stage names (Mochi uses NEW, QUALIFIED, etc.)
        stage_mapping = {
            "NEW": "NEW_LEAD",
            "QUALIFIED": "QUALIFIED",
            "BOOKED": "BOOKED_CALL",
            "BOOKED_CALL": "BOOKED_CALL",
            "WON": "WON",
            "LOST": "LOST",
            "UNQUALIFIED": "UNQUALIFIED"
        }
        mapped_stage = stage_mapping.get(stage, stage)

        # Create Conversation model
        conversations.append(Conversation(
            id=conv_id,
            organization=org_id,
            stage=mapped_stage,
            setter_email=setter_email,
            created_at=created_at,
            messages=messages
        ))

    return conversations


def main():
    """Run analysis on real Mochi export."""
    # Load real data
    data_path = Path(__file__).parent.parent.parent / "conversations_detailed_report_created_consulting_2026-01-04_2026-01-12.json"

    print(f"Loading data from: {data_path}")

    with open(data_path, 'r') as f:
        export_data = json.load(f)

    print(f"Loaded {len(export_data)} raw conversations")

    # Convert to our model
    conversations = convert_mochi_export_to_model(export_data)
    print(f"Converted {len(conversations)} conversations with messages")

    # Configure analysis
    config = AnalysisConfig(
        timezone="UTC",
        start_date=date(2026, 1, 4),
        end_date=date(2026, 1, 12),
        include_scripts=False,  # Skip for now (no LLM yet)
        include_objections=False,
        include_avatars=False
    )

    print("\n" + "="*60)
    print("Running Analysis...")
    print("="*60)

    # Run analysis
    result = analyze_conversations(conversations, config)

    # Display results
    print("\n📊 CORE METRICS")
    print("-" * 60)
    print(f"Total Conversations:          {result.summary.total_conversations}")
    print(f"Total Messages Received:      {result.summary.total_messages_received}")
    print(f"Total Messages Sent:          {result.summary.total_messages_sent}")
    print(f"Reply Rate (48h):            {result.summary.creator_message_reply_rate_within_48h:.1f}%")
    print(f"Median Reply Delay:          {result.summary.median_reply_delay_seconds // 3600}h {(result.summary.median_reply_delay_seconds % 3600) // 60}m")

    print("\n📈 STAGE CHANGES")
    print("-" * 60)
    for stage, count in sorted(result.summary.stage_changes.items(), key=lambda x: -x[1]):
        print(f"{stage:20s} {count:>5d}")

    print("\n👥 SETTER PERFORMANCE (By Assignment)")
    print("-" * 60)
    for setter, metrics in result.setters_by_assignment.items():
        print(f"\n{setter}")
        print(f"  Conversations:    {metrics['total_conversations']}")
        print(f"  Messages Sent:    {metrics['total_messages_sent_from_mochi']}")
        print(f"  Reply Rate:       {metrics['creator_message_reply_rate_within_48h']:.1f}%")

    print("\n📅 TIME SERIES (First 5 days)")
    print("-" * 60)
    for day in result.time_series.stage_changes_by_day[:5]:
        total = sum(day.stages.values())
        print(f"{day.date:20s} Total: {total:>3d}  {day.stages}")

    print("\n⏰ ACTIVITY BY TIME OF DAY")
    print("-" * 60)
    print("Lead Activity:")
    for time_bin, count in sorted(result.time_series.lead_activity_by_time.items()):
        bar = "█" * (count // 5) if count > 0 else ""
        print(f"  {time_bin}:  {count:>4d}  {bar}")

    print("\nSetter Activity:")
    for time_bin, count in sorted(result.time_series.setter_activity_by_time.items()):
        bar = "█" * (count // 5) if count > 0 else ""
        print(f"  {time_bin}:  {count:>4d}  {bar}")

    # Save results
    output_path = Path(__file__).parent.parent / "test_analysis_output.json"
    with open(output_path, 'w') as f:
        f.write(result.model_dump_json(indent=2))

    print(f"\n✅ Full results saved to: {output_path}")


if __name__ == "__main__":
    main()
