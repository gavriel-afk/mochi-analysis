"""
Mochi API integration for fetching conversation data.
"""

import json
import logging
import os
from datetime import date
from typing import Any

import httpx
from json_repair import repair_json
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MochiAPIError(Exception):
    """Raised when Mochi API returns an error."""
    pass


class MochiConfig(BaseModel):
    """Configuration for Mochi API."""

    session_id: str = Field(..., description="Django session ID")
    base_url: str = Field(
        default="https://api.themochi.app",
        description="Mochi API base URL"
    )
    timeout: int = Field(default=120, description="Request timeout in seconds")


class MochiClient:
    """Client for interacting with Mochi API."""

    def __init__(self, config: MochiConfig | None = None):
        """
        Initialize Mochi API client.

        Args:
            config: Optional configuration. If not provided, reads from environment.
        """
        if config is None:
            session_id = os.getenv("MOCHI_SESSION_ID")
            if not session_id:
                raise ValueError("MOCHI_SESSION_ID environment variable is required")
            config = MochiConfig(session_id=session_id)

        self.config = config
        self.client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={
                "Cookie": f"sessionid={config.session_id}"
            }
        )

    def fetch_conversations(
        self,
        org_id: str,
        date_from: date | str,
        date_to: date | str
    ) -> list[dict[str, Any]]:
        """
        Fetch conversation data from Mochi API.

        Args:
            org_id: Organization UUID
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            List of conversation objects

        Raises:
            MochiAPIError: If API request fails
        """
        # Convert dates to strings if needed
        if isinstance(date_from, date):
            date_from = date_from.isoformat()
        if isinstance(date_to, date):
            date_to = date_to.isoformat()

        # Build request
        endpoint = "/mochi-team-dashboard/conversations/detailed-export/"
        params = {
            "org_id": org_id,
            "date_from": date_from,
            "date_to": date_to
        }

        try:
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()

            # Try to parse JSON, with auto-repair on failure
            try:
                data = response.json()
            except json.JSONDecodeError as json_err:
                logger.warning(f"JSON parse error: {json_err}. Attempting auto-repair...")
                text = response.text.rstrip()

                # Quick fix: if it's a truncated array, try adding closing brackets
                if text.startswith("[") and not text.endswith("]"):
                    logger.info("Detected truncated JSON array, attempting bracket fix...")
                    # Find last complete object by looking for "}," or "}" pattern
                    # and add closing bracket
                    last_brace = text.rfind("}")
                    if last_brace > 0:
                        fixed = text[:last_brace + 1] + "]"
                        try:
                            data = json.loads(fixed)
                            logger.info("JSON bracket fix successful")
                        except json.JSONDecodeError:
                            # If simple fix didn't work, try json_repair
                            try:
                                repaired = repair_json(text)
                                data = json.loads(repaired)
                                logger.info("JSON auto-repair successful")
                            except Exception as repair_err:
                                raise MochiAPIError(
                                    f"JSON parsing failed and auto-repair unsuccessful: {json_err}"
                                ) from repair_err
                    else:
                        raise MochiAPIError(f"JSON parsing failed: {json_err}") from json_err
                else:
                    # Not a truncated array, try json_repair
                    try:
                        repaired = repair_json(text)
                        data = json.loads(repaired)
                        logger.info("JSON auto-repair successful")
                    except Exception as repair_err:
                        raise MochiAPIError(
                            f"JSON parsing failed and auto-repair unsuccessful: {json_err}"
                        ) from repair_err

            if not isinstance(data, list):
                raise MochiAPIError(f"Expected list response, got {type(data)}")

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                raise MochiAPIError(
                    "Authentication failed. MOCHI_SESSION_ID may be expired. "
                    "Update the session ID and try again."
                ) from e
            raise MochiAPIError(f"HTTP {e.response.status_code}: {e.response.text}") from e

        except httpx.TimeoutException as e:
            raise MochiAPIError(
                f"Request timed out after {self.config.timeout} seconds"
            ) from e

        except httpx.RequestError as e:
            raise MochiAPIError(f"Request failed: {e}") from e

        except Exception as e:
            raise MochiAPIError(f"Unexpected error: {e}") from e

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function
def fetch_conversations(
    org_id: str,
    date_from: date | str,
    date_to: date | str,
    session_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Fetch conversations from Mochi API (convenience function).

    Args:
        org_id: Organization UUID
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        session_id: Optional session ID (uses env var if not provided)

    Returns:
        List of conversation objects
    """
    config = None
    if session_id:
        config = MochiConfig(session_id=session_id)

    with MochiClient(config=config) as client:
        return client.fetch_conversations(org_id, date_from, date_to)
