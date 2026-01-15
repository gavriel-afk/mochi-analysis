"""Objection classification - analyze LEAD objections using Gemini."""

from typing import List, Dict
from mochi_analytics.core.models import Conversation, ObjectionGroup
from mochi_analytics.core.llm import generate_batch_classification, generate_text, parse_json_response
from mochi_analytics.core.constants import OBJECTION_GROUPS
import logging

logger = logging.getLogger(__name__)


def analyze_objections(conversations: List[Conversation]) -> Dict:
    """
    Analyze LEAD messages for objections.

    Uses adaptive batch retry: 50 → 25 → 8 → 1

    Args:
        conversations: List of conversations

    Returns:
        Dict with objection_groups and total_analyzed
    """
    # Extract LEAD messages
    lead_messages = extract_lead_messages(conversations)

    if not lead_messages:
        return build_empty_objections_result()

    logger.info(f"Extracted {len(lead_messages)} LEAD messages")

    # Classify with adaptive batch retry
    classifications = classify_with_adaptive_retry(lead_messages)

    logger.info(f"Classified {len(classifications)} messages")

    # Aggregate by category
    objection_groups = aggregate_objections(classifications)

    return {
        "objection_groups": objection_groups,
        "total_analyzed": len(lead_messages)
    }


def extract_lead_messages(conversations: List[Conversation]) -> List[str]:
    """
    Extract all LEAD messages from conversations.

    Args:
        conversations: List of conversations

    Returns:
        List of message content strings
    """
    messages = []

    for conv in conversations:
        actual_messages = conv.get_actual_messages()

        for msg in actual_messages:
            if msg.sender == "LEAD":
                content = msg.content.strip()
                if content:  # Skip empty messages
                    messages.append(content)

    return messages


def classify_with_adaptive_retry(
    messages: List[str],
    batch_sizes: List[int] = [50, 25, 8, 1]
) -> List[Dict]:
    """
    Classify messages with adaptive batch retry.

    Starts with batch_size=50, falls back to 25, 8, then 1 on failure.

    Args:
        messages: List of message strings
        batch_sizes: List of batch sizes to try (default: [50, 25, 8, 1])

    Returns:
        List of classification dicts
    """
    all_results = []
    remaining_messages = messages[:]

    while remaining_messages:
        batch_size = batch_sizes[0] if batch_sizes else 1
        batch = remaining_messages[:batch_size]

        try:
            # Try to classify this batch
            results = classify_batch(batch)
            all_results.extend(results)
            remaining_messages = remaining_messages[batch_size:]

            logger.info(f"✓ Classified batch of {len(batch)} (batch_size={batch_size})")

        except Exception as e:
            logger.warning(f"✗ Batch of {batch_size} failed: {e}")

            # Try next smaller batch size
            if len(batch_sizes) > 1:
                batch_sizes = batch_sizes[1:]
                logger.info(f"Retrying with batch_size={batch_sizes[0]}")
            else:
                # Even single message failed - mark as unclassified
                logger.error(f"Failed to classify even single message, skipping")
                all_results.append({"category": "unclassified"})
                remaining_messages = remaining_messages[1:]

    return all_results


def classify_batch(messages: List[str]) -> List[Dict]:
    """
    Classify a batch of messages into objection categories.

    Args:
        messages: List of message strings

    Returns:
        List of dicts with {"category": str}

    Raises:
        Exception: If classification fails
    """
    categories_str = "\n".join([f"- {cat}" for cat in OBJECTION_GROUPS])
    messages_str = "\n".join([f"{i+1}. {msg[:200]}" for i, msg in enumerate(messages)])

    prompt = f"""Classify each message into ONE objection category or "none" if no objection.

Categories:
{categories_str}
- none (not an objection)

Messages:
{messages_str}

Return a JSON array:
[
  {{"message_index": 1, "category": "category_name"}},
  {{"message_index": 2, "category": "none"}},
  ...
]

Return ONLY the JSON array."""

    response = generate_text(prompt, temperature=0.3, max_retries=2)
    parsed = parse_json_response(response)

    # Convert to list of category dicts
    results = []
    for item in parsed:
        category = item.get("category", "unclassified")
        results.append({"category": category})

    return results


def aggregate_objections(classifications: List[Dict]) -> List[ObjectionGroup]:
    """
    Aggregate classifications into objection groups.

    Args:
        classifications: List of classification dicts

    Returns:
        List of ObjectionGroup models
    """
    # Count by category
    counts = {}
    for item in classifications:
        category = item.get("category", "unclassified")
        if category != "none":  # Skip non-objections
            counts[category] = counts.get(category, 0) + 1

    total = sum(counts.values())

    # Build ObjectionGroup list
    groups = []
    for category in OBJECTION_GROUPS:
        count = counts.get(category, 0)
        percentage = (count / total * 100) if total > 0 else 0.0

        # Get description for this category
        description = get_objection_description(category)

        groups.append(ObjectionGroup(
            name=category,
            description=description,
            count=count,
            percentage=round(percentage, 1)
        ))

    # Sort by count descending
    groups.sort(key=lambda x: x.count, reverse=True)

    return groups


def get_objection_description(category: str) -> str:
    """
    Get description for objection category.

    Args:
        category: Objection category name

    Returns:
        Human-readable description
    """
    descriptions = {
        "Financial Objection": "Concerns about price, budget, or cost",
        "Timing Objection": "Not the right time, too busy, need more time",
        "Decision Making Objection": "Need to consult with others, can't decide alone",
        "Self Confidence Objection": "Doubts about ability to succeed or commit",
        "Lack of Trust/Authority Objection": "Skepticism about credibility or expertise",
        "Competitor Objection": "Considering alternatives or competitors",
        "Lack of Information Objection": "Need more details or clarity before deciding"
    }
    return descriptions.get(category, "")


def build_empty_objections_result() -> Dict:
    """Build empty result structure."""
    return {
        "objection_groups": [
            ObjectionGroup(
                name=cat,
                description=get_objection_description(cat),
                count=0,
                percentage=0.0
            )
            for cat in OBJECTION_GROUPS
        ],
        "total_analyzed": 0
    }
