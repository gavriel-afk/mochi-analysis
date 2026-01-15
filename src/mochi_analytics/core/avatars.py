"""Avatar clustering - identify lead personas using embeddings and K-means."""

from typing import List, Dict, Optional
from sklearn.cluster import KMeans
from mochi_analytics.core.models import Conversation
from mochi_analytics.core.llm import generate_embedding, generate_structured_output
import logging

logger = logging.getLogger(__name__)


def analyze_avatars(
    conversations: List[Conversation],
    n_clusters: int = 5,
    min_messages: int = 3
) -> Dict:
    """
    Cluster conversations by lead characteristics using K-means on embeddings.

    Steps:
    1. Filter out funnel triggers (automated/bot conversations)
    2. Extract first N LEAD messages per conversation
    3. Generate embeddings using Gemini
    4. Cluster using K-means
    5. Generate avatar profiles from cluster samples

    Args:
        conversations: List of conversations
        n_clusters: Number of avatar clusters
        min_messages: Minimum LEAD messages required

    Returns:
        Dict with avatars list and metadata
    """
    # Step 1: Filter funnel triggers
    real_conversations = filter_funnel_triggers(conversations)

    if len(real_conversations) < n_clusters:
        logger.warning(f"Only {len(real_conversations)} conversations, need {n_clusters}")
        return build_empty_avatars_result()

    logger.info(f"Filtered to {len(real_conversations)} real conversations")

    # Step 2: Extract lead text (first 3 messages)
    conversation_texts = []
    valid_conversations = []

    for conv in real_conversations:
        text = extract_lead_text(conv, max_messages=min_messages)
        if text:
            conversation_texts.append(text)
            valid_conversations.append(conv)

    if len(valid_conversations) < n_clusters:
        logger.warning(f"Only {len(valid_conversations)} valid conversations")
        return build_empty_avatars_result()

    logger.info(f"Extracted text from {len(valid_conversations)} conversations")

    # Step 3: Generate embeddings
    try:
        embeddings = [generate_embedding(text) for text in conversation_texts]
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        return build_empty_avatars_result()

    logger.info(f"Generated {len(embeddings)} embeddings")

    # Step 4: K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Step 5: Generate avatar profiles
    avatars = []
    for cluster_id in range(n_clusters):
        # Get conversations in this cluster
        cluster_convs = [
            valid_conversations[i]
            for i in range(len(valid_conversations))
            if labels[i] == cluster_id
        ]

        if not cluster_convs:
            continue

        # Take sample for profile generation
        sample_size = min(3, len(cluster_convs))
        sample = cluster_convs[:sample_size]

        # Generate profile
        try:
            profile = generate_avatar_profile(sample)
        except Exception as e:
            logger.warning(f"Failed to generate profile for cluster {cluster_id}: {e}")
            profile = {
                "job": "Unknown",
                "age_range": "Unknown",
                "motivation": "Unknown",
                "main_objection": "Unknown"
            }

        # Build avatar dict
        percentage = (len(cluster_convs) / len(valid_conversations) * 100)

        avatars.append({
            "id": f"avatar_{cluster_id + 1}",
            "cluster_id": cluster_id,
            "conversation_count": len(cluster_convs),
            "percentage": round(percentage, 1),
            "job": profile.get("job", "Unknown"),
            "age_range": profile.get("age_range", "Unknown"),
            "motivation": profile.get("motivation", "Unknown"),
            "main_objection": profile.get("main_objection", "Unknown"),
            "sample_conversation_ids": [conv.id for conv in sample]
        })

    # Sort by count descending
    avatars.sort(key=lambda x: x["conversation_count"], reverse=True)

    return {
        "avatars": avatars,
        "total_conversations": len(valid_conversations),
        "total_clusters": len(avatars)
    }


def filter_funnel_triggers(conversations: List[Conversation]) -> List[Conversation]:
    """
    Filter out automated funnel triggers.

    Heuristics:
    - Very short conversations (< 2 messages)
    - Only CREATOR messages (no LEAD response)
    - Very short LEAD messages (< 10 chars)

    Args:
        conversations: All conversations

    Returns:
        Filtered list of real conversations
    """
    real_conversations = []

    for conv in conversations:
        messages = conv.get_actual_messages()

        # Must have at least 2 messages
        if len(messages) < 2:
            continue

        # Must have at least one LEAD message
        lead_messages = [m for m in messages if m.sender == "LEAD"]
        if not lead_messages:
            continue

        # LEAD messages must have substance (not just "ok", "hi", etc.)
        substantial = [m for m in lead_messages if len(m.content.strip()) >= 10]
        if not substantial:
            continue

        real_conversations.append(conv)

    return real_conversations


def extract_lead_text(conv: Conversation, max_messages: int = 3) -> Optional[str]:
    """
    Extract first N LEAD messages as combined text.

    Args:
        conv: Conversation
        max_messages: Max number of LEAD messages to include

    Returns:
        Combined text or None if insufficient
    """
    messages = conv.get_actual_messages()
    lead_messages = [m for m in messages if m.sender == "LEAD"]

    if not lead_messages:
        return None

    # Take first N messages
    selected = lead_messages[:max_messages]
    combined = " ".join([m.content.strip() for m in selected])

    return combined if combined else None


def generate_avatar_profile(conversations: List[Conversation]) -> Dict:
    """
    Use Gemini to extract avatar profile from sample conversations.

    Args:
        conversations: Sample conversations from cluster

    Returns:
        Dict with job, age_range, motivation, main_objection
    """
    # Format conversations for prompt
    conv_texts = []
    for i, conv in enumerate(conversations, 1):
        messages = conv.get_actual_messages()
        lead_msgs = [m for m in messages if m.sender == "LEAD"]

        text = f"Conversation {i}:\n"
        for msg in lead_msgs[:3]:  # First 3 LEAD messages
            text += f"  - {msg.content.strip()}\n"

        conv_texts.append(text)

    combined = "\n".join(conv_texts)

    prompt = f"""Analyze these {len(conversations)} lead conversations from the same cluster.
Extract common patterns to create an avatar profile.

Conversations:
{combined}

Return JSON with these fields:
- job: Most likely occupation/role (e.g., "Small business owner", "Fitness enthusiast", "Student")
- age_range: Estimated age range (e.g., "25-35", "35-45", "18-25")
- motivation: Why they reached out (1-2 sentences)
- main_objection: Primary concern or hesitation (1 sentence)

Return ONLY valid JSON, no other text.
Example: {{"job": "Entrepreneur", "age_range": "30-40", "motivation": "...", "main_objection": "..."}}"""

    return generate_structured_output(
        prompt=prompt,
        expected_fields=["job", "age_range", "motivation", "main_objection"]
    )


def build_empty_avatars_result() -> Dict:
    """Build empty result structure."""
    return {
        "avatars": [],
        "total_conversations": 0,
        "total_clusters": 0
    }
