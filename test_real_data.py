#!/usr/bin/env python3
"""Test analysis on real Mochi export data."""

import json
import sys
from pathlib import Path
from datetime import date

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mochi_analytics.core.models import Conversation, AnalysisConfig
from mochi_analytics.core.analyzer import analyze_conversations


def main():
    """Run analysis on real Mochi export."""
    # Load real data
    data_path = Path(__file__).parent.parent / "conversations_detailed_report_created_consulting_2026-01-04_2026-01-12.json"

    print(f"Loading data from: {data_path}")

    with open(data_path, 'r') as f:
        export_data = json.load(f)

    print(f"Loaded {len(export_data)} conversations")

    # Convert to our model (now works directly!)
    conversations = [Conversation(**conv) for conv in export_data]
    print(f"Converted {len(conversations)} conversations")

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
        # metrics is a dict from model_dump()
        total_convs = metrics.get('total_conversations', 0) if isinstance(metrics, dict) else metrics.total_conversations
        msgs_sent = metrics.get('total_messages_sent_from_mochi', 0) if isinstance(metrics, dict) else metrics.total_messages_sent_from_mochi
        reply_rate = metrics.get('creator_message_reply_rate_within_48h', 0) if isinstance(metrics, dict) else metrics.creator_message_reply_rate_within_48h

        print(f"\n{setter}")
        print(f"  Conversations:    {total_convs}")
        print(f"  Messages Sent:    {msgs_sent}")
        print(f"  Reply Rate:       {reply_rate:.1f}%")

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
    output_path = Path(__file__).parent / "test_analysis_output.json"
    with open(output_path, 'w') as f:
        f.write(result.model_dump_json(indent=2))

    print(f"\n✅ Full results saved to: {output_path}")


if __name__ == "__main__":
    main()
