"""Script analysis - clustering and categorization of CREATOR messages."""

from typing import List, Dict, Optional
from collections import defaultdict
from rapidfuzz import fuzz
from mochi_analytics.core.models import Conversation, ScriptPattern
from mochi_analytics.core.llm import generate_text
from mochi_analytics.core.constants import SCRIPT_CATEGORIES
import logging

logger = logging.getLogger(__name__)


def analyze_scripts(
    conversations: List[Conversation],
    similarity_threshold: float = 85.0,
    min_cluster_size: int = 2
) -> Dict[str, List[ScriptPattern]]:
    """
    Analyze and cluster CREATOR messages into script patterns.

    Steps:
    1. Extract all CREATOR messages
    2. Cluster similar messages using RapidFuzz
    3. Calculate reply rates for each cluster
    4. Categorize clusters using Gemini
    5. Generate topics using Gemini

    Args:
        conversations: List of conversations to analyze
        similarity_threshold: Fuzzy match threshold (0-100)
        min_cluster_size: Minimum messages for a cluster

    Returns:
        Dict with categorized script patterns
    """
    # Step 1: Extract CREATOR messages with context
    creator_messages = extract_creator_messages(conversations)

    if not creator_messages:
        return build_empty_scripts_result()

    logger.info(f"Extracted {len(creator_messages)} CREATOR messages")

    # Step 2: Cluster similar messages
    clusters = cluster_messages(creator_messages, similarity_threshold)

    # Filter by min size
    clusters = [c for c in clusters if c['count'] >= min_cluster_size]

    logger.info(f"Created {len(clusters)} clusters (min_size={min_cluster_size})")

    if not clusters:
        return build_empty_scripts_result()

    # Step 3: Calculate reply rates
    clusters = calculate_reply_rates(clusters)

    # Step 4 & 5: Categorize and generate topics
    clusters = categorize_and_generate_topics(clusters)

    # Convert to ScriptPattern models and group by category
    return group_by_category(clusters)


def extract_creator_messages(conversations: List[Conversation]) -> List[Dict]:
    """
    Extract CREATOR messages with reply tracking context.

    Returns:
        List of dicts with message, conv_id, index, has_reply
    """
    messages = []

    for conv in conversations:
        actual_messages = conv.get_actual_messages()

        for i, msg in enumerate(actual_messages):
            if msg.sender != "CREATOR":
                continue

            # Check if LEAD replied after this message
            has_reply = False
            for future_msg in actual_messages[i+1:]:
                if future_msg.sender == "LEAD":
                    has_reply = True
                    break

            # Get context (previous messages)
            context = []
            for prev_msg in actual_messages[max(0, i-3):i]:
                context.append({
                    "sender": prev_msg.sender,
                    "content": prev_msg.content.strip()
                })

            messages.append({
                "text": msg.content.strip(),
                "conv_id": conv.id,
                "index": i,
                "has_reply": has_reply,
                "context": context
            })

    return messages


def cluster_messages(
    messages: List[Dict],
    threshold: float
) -> List[Dict]:
    """
    Cluster similar messages using RapidFuzz fuzzy matching.

    Args:
        messages: List of message dicts
        threshold: Similarity threshold (0-100)

    Returns:
        List of cluster dicts with example, messages, count
    """
    clusters = []

    for msg in messages:
        matched = False
        text = msg["text"]

        for cluster in clusters:
            similarity = fuzz.token_set_ratio(text, cluster['example'])

            if similarity >= threshold:
                cluster['messages'].append(msg)
                cluster['count'] += 1
                matched = True
                break

        if not matched:
            clusters.append({
                'example': text,
                'messages': [msg],
                'count': 1
            })

    return clusters


def calculate_reply_rates(clusters: List[Dict]) -> List[Dict]:
    """
    Calculate reply rates for each cluster.

    Args:
        clusters: List of cluster dicts

    Returns:
        Clusters with replies, reply_rate added
    """
    for cluster in clusters:
        replies = sum(1 for msg in cluster['messages'] if msg['has_reply'])
        total = cluster['count']
        reply_rate = (replies / total * 100) if total > 0 else 0.0

        cluster['replies'] = replies
        cluster['reply_rate'] = f"{reply_rate:.1f}%"

    return clusters


def categorize_and_generate_topics(clusters: List[Dict]) -> List[Dict]:
    """
    Use Gemini to categorize scripts and generate topics in batches.

    Categories:
    - opener: Reply to lead's first message - initial greeting/engagement
    - follow_up: Message to revive dead chats or chase leads who have gone AFK
    - nurture_discovery: Qualifying leads, getting to know them, building trust
    - cta: Call to action - inviting/pushing leads to take final step

    Batching strategy:
    - Initial batch size: 20 scripts
    - Retry strategy: Failed batches retry as individual items (batch size 1)
    - Rate limiting: 0.3s between initial batches, 0.5s for retries

    Args:
        clusters: List of cluster dicts

    Returns:
        Clusters with category and topic added
    """
    import time

    # Phase 1: Initial batching with size 20
    initial_batch_size = 20
    retry_queue = []

    # Split into batches of 20
    initial_batches = [
        clusters[i:i + initial_batch_size]
        for i in range(0, len(clusters), initial_batch_size)
    ]

    logger.info(f"Processing {len(clusters)} clusters in {len(initial_batches)} batches of {initial_batch_size}")

    for batch_idx, batch in enumerate(initial_batches):
        try:
            logger.info(f"Processing batch {batch_idx + 1}/{len(initial_batches)} ({len(batch)} scripts)")
            results = categorize_batch_with_context(batch)

            # Apply results to this batch
            for idx, cluster in enumerate(batch):
                script_id = f"script_{idx}"
                if script_id in results:
                    cluster['category'] = results[script_id].get('category')
                    cluster['topic'] = results[script_id].get('topic')
                else:
                    cluster['category'] = None
                    cluster['topic'] = None

            logger.info(f"✓ Batch {batch_idx + 1} succeeded")

        except Exception as e:
            logger.warning(f"✗ Batch {batch_idx + 1} failed: {e}")
            # Add all items from this batch to retry queue
            retry_queue.extend(batch)

        # Rate limiting between batches
        if batch_idx < len(initial_batches) - 1:
            time.sleep(0.3)

    # Phase 2: Retry failed items individually
    if retry_queue:
        logger.info(f"Retrying {len(retry_queue)} failed scripts individually...")

        for retry_idx, cluster in enumerate(retry_queue):
            try:
                logger.info(f"Retrying script {retry_idx + 1}/{len(retry_queue)}")
                results = categorize_batch_with_context([cluster])

                # Apply result (single item batch)
                script_id = "script_0"
                if script_id in results:
                    cluster['category'] = results[script_id].get('category')
                    cluster['topic'] = results[script_id].get('topic')
                else:
                    cluster['category'] = None
                    cluster['topic'] = None

            except Exception as e:
                logger.warning(f"✗ Individual retry failed: {e}")
                cluster['category'] = None
                cluster['topic'] = None

            # Slower rate limiting for retries
            if retry_idx < len(retry_queue) - 1:
                time.sleep(0.5)

    return clusters


def categorize_batch_with_context(clusters: List[Dict]) -> Dict:
    """
    Categorize a batch of scripts with conversation context.

    Args:
        clusters: List of cluster dicts with 'example' and 'messages'

    Returns:
        Dict mapping script_id to {"category": str, "topic": str}
    """
    # Build prompt with context for each script
    scripts_section = []

    for idx, cluster in enumerate(clusters):
        # Get a sample message with context (first one from cluster)
        sample_msg = cluster['messages'][0]
        context = sample_msg.get('context', [])

        # Format context (previous messages)
        context_lines = []
        for ctx_msg in context[-3:]:  # Last 3 messages for context
            sender = ctx_msg.get('sender', 'UNKNOWN')
            content = ctx_msg.get('content', '')[:100]  # Truncate long messages
            context_lines.append(f"  [{sender}]: {content}")

        context_str = "\n".join(context_lines) if context_lines else "  [No previous messages]"

        scripts_section.append(f"""Script ID: script_{idx}
Previous messages:
{context_str}
Script message (CREATOR): {cluster['example']}
""")

    scripts_text = "\n\n".join(scripts_section)

    prompt = f"""You are classifying sales/setter scripts into categories and generating short topic descriptions.

Categories:
- opener: Reply to lead's first message - initial greeting/engagement (NOT follow-up)
- follow_up: Message to revive dead chats or chase leads who have gone AFK/unresponsive
- nurture_discovery: Messages for qualifying leads, getting to know them, building trust/authority
- cta: Call to action - inviting/pushing leads to take final step (payment, booking, registration)

For each script below, determine:
1. Its category based on the script content and conversation context
2. A short topic description (3-6 words) summarizing what the script is about

Important category rules:
- "opener" is ONLY for first response to a new lead's initial message
- "follow_up" is for re-engaging leads who haven't responded
- "nurture_discovery" is for ongoing conversation, qualifying, building rapport
- "cta" is for pushing toward a specific action (book call, pay, sign up)

Topic examples:
- "Keyword BnB greeting"
- "Financial qualification question"
- "Booking call invitation"
- "Check-in after no response"
- "Investment amount discovery"

Scripts to classify:

{scripts_text}

Respond with ONLY a JSON object. Each script ID maps to an object with "category" and "topic". Example:
{{"script_0": {{"category": "opener", "topic": "Keyword BnB greeting"}}, "script_1": {{"category": "nurture_discovery", "topic": "Financial qualification"}}}}

JSON response:"""

    from mochi_analytics.core.llm import parse_json_response

    response = generate_text(prompt, temperature=0.3)
    return parse_json_response(response)


def categorize_script(script: str) -> str:
    """
    Categorize a single script using Gemini.

    Args:
        script: Script text

    Returns:
        Category name (opener, follow_up, nurture_discovery, cta)
    """
    prompt = f"""Classify this sales/outreach script into ONE of these 4 categories:

1. opener - First contact message to a new lead
2. follow_up - Message sent after no response from previous message
3. nurture_discovery - Building rapport, asking questions, discovery
4. cta - Call to action, booking request, scheduling

Script:
{script}

IMPORTANT: Respond with ONLY ONE WORD from this exact list:
- opener
- follow_up
- nurture_discovery
- cta

Do not add punctuation, explanations, or any other text. Just the category word."""

    response = generate_text(prompt, temperature=0.2)
    category = response.strip().lower().replace(".", "").replace(",", "").split()[0]

    # Validate category
    if category not in SCRIPT_CATEGORIES:
        logger.warning(f"Invalid category '{category}', defaulting to follow_up")
        return "follow_up"  # Default to most common category

    return category


def generate_topic(script: str) -> str:
    """
    Generate a concise topic/summary for a script.

    Args:
        script: Script text

    Returns:
        Short topic string (1-5 words)
    """
    prompt = f"""Generate a very short topic summary (1-5 words) for this message:

{script}

Return ONLY the topic phrase, no other text.
Examples: "Free consultation offer", "Follow-up after call", "Booking request"."""

    response = generate_text(prompt, temperature=0.5)
    return response.strip()


def group_by_category(clusters: List[Dict]) -> Dict[str, List[ScriptPattern]]:
    """
    Group clusters by category and convert to ScriptPattern models.

    Args:
        clusters: List of cluster dicts

    Returns:
        Dict with category as key, list of ScriptPattern as value
    """
    grouped = defaultdict(list)

    for i, cluster in enumerate(clusters):
        pattern = ScriptPattern(
            id=f"script_{i+1}",
            example=cluster['example'],
            times_sent=cluster['count'],
            replies=cluster['replies'],
            reply_rate=cluster['reply_rate'],
            category=cluster.get('category'),
            topic=cluster.get('topic')
        )

        category = cluster.get('category') or 'uncategorized'
        grouped[category].append(pattern)

    return dict(grouped)


def build_empty_scripts_result() -> Dict[str, List[ScriptPattern]]:
    """Build empty result structure."""
    return {cat: [] for cat in SCRIPT_CATEGORIES}
