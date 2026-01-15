"""LLM utilities wrapper for Google Gemini integration."""

from google import genai
from google.genai import types
from typing import Any, Optional
import json
import time
import os


# Global client instance
_client: Optional[genai.Client] = None


def configure_gemini(api_key: str):
    """Initialize Gemini with API key."""
    global _client
    _client = genai.Client(api_key=api_key)


def _get_client() -> genai.Client:
    """Get configured client or raise error."""
    if _client is None:
        raise RuntimeError("Gemini not configured. Call configure_gemini() first.")
    return _client


def generate_embedding(text: str, model: str = "models/text-embedding-004") -> list[float]:
    """
    Generate embedding for text.

    Args:
        text: Text to embed
        model: Embedding model to use

    Returns:
        List of float embeddings
    """
    client = _get_client()
    result = client.models.embed_content(
        model=model,
        contents=text
    )
    return result.embeddings[0].values


def generate_text(
    prompt: str,
    model: str = "models/gemini-2.0-flash",
    temperature: float = 0.7,
    max_retries: int = 3
) -> str:
    """
    Generate text completion with retry logic.

    Args:
        prompt: The prompt to send to the model
        model: Model name to use
        temperature: Sampling temperature
        max_retries: Maximum number of retry attempts

    Returns:
        Generated text response

    Raises:
        Exception: If all retries fail
    """
    client = _get_client()

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature
                )
            )
            return response.text
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed after {max_retries} attempts: {e}")
            # Exponential backoff
            time.sleep(2 ** attempt)


def generate_batch_classification(
    messages: list[str],
    categories: list[str],
    model: str = "models/gemini-2.0-flash",
    max_retries: int = 3
) -> list[dict]:
    """
    Classify batch of messages into categories.

    Args:
        messages: List of messages to classify
        categories: List of category names
        model: Model to use
        max_retries: Maximum retry attempts

    Returns:
        List of dicts with {"message": str, "category": str}
    """
    prompt = build_classification_prompt(messages, categories)

    for attempt in range(max_retries):
        try:
            response = generate_text(prompt, model, temperature=0.3)
            return parse_json_response(response)
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Classification failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)


def build_classification_prompt(messages: list[str], categories: list[str]) -> str:
    """
    Build prompt for batch classification.

    Args:
        messages: Messages to classify
        categories: Available categories

    Returns:
        Formatted prompt string
    """
    categories_str = "\n".join([f"- {cat}" for cat in categories])
    messages_str = "\n".join([f"{i+1}. {msg}" for i, msg in enumerate(messages)])

    prompt = f"""Classify each message into ONE of these categories:
{categories_str}

Messages to classify:
{messages_str}

Return a JSON array with format:
[
  {{"message_index": 1, "category": "category_name"}},
  {{"message_index": 2, "category": "category_name"}},
  ...
]

Return ONLY the JSON array, no other text."""

    return prompt


def parse_json_response(response: str) -> list[dict]:
    """
    Parse JSON from LLM response.

    Handles common issues:
    - Markdown code blocks
    - Extra whitespace
    - Non-JSON text

    Args:
        response: Raw LLM response

    Returns:
        Parsed JSON data
    """
    # Remove markdown code blocks
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]

    # Strip whitespace
    response = response.strip()

    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response: {e}\nResponse: {response}")


def generate_structured_output(
    prompt: str,
    expected_fields: list[str],
    model: str = "models/gemini-2.0-flash",
    max_retries: int = 3
) -> dict:
    """
    Generate structured JSON output with expected fields.

    Args:
        prompt: The prompt (should instruct to return JSON)
        expected_fields: List of expected field names
        model: Model to use
        max_retries: Maximum retry attempts

    Returns:
        Parsed JSON dict
    """
    for attempt in range(max_retries):
        try:
            response = generate_text(prompt, model, temperature=0.3)
            data = parse_json_response(response)

            # Validate expected fields
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data)}")

            missing_fields = [f for f in expected_fields if f not in data]
            if missing_fields:
                raise ValueError(f"Missing fields: {missing_fields}")

            return data
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Structured output failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)
