"""
Framer CMS integration for pushing analytics reports.
"""

import os
from typing import Any

import httpx
from pydantic import BaseModel, Field


class FramerAPIError(Exception):
    """Raised when Framer API returns an error."""
    pass


class FramerConfig(BaseModel):
    """Configuration for Framer CMS API."""

    api_url: str = Field(
        default="http://localhost:8502",
        description="Framer API base URL"
    )
    timeout: int = Field(default=60, description="Request timeout in seconds")


class FramerClient:
    """Client for interacting with Framer CMS API."""

    def __init__(self, config: FramerConfig | None = None):
        """
        Initialize Framer CMS client.

        Args:
            config: Optional configuration. If not provided, reads from environment.
        """
        if config is None:
            api_url = os.getenv("FRAMER_API_URL", "http://localhost:8502")
            config = FramerConfig(api_url=api_url)

        self.config = config
        self.client = httpx.Client(
            base_url=config.api_url,
            timeout=config.timeout,
            headers={
                "Content-Type": "application/json"
            }
        )

    def push_report(self, report_data: dict[str, Any]) -> dict[str, Any]:
        """
        Push an analytics report to Framer CMS.

        Args:
            report_data: Complete analysis result with metadata, summary, etc.

        Returns:
            API response with slug, queue_size, and chart_ids

        Raises:
            FramerAPIError: If API request fails
        """
        try:
            response = self.client.post("/api/report", json=report_data)
            response.raise_for_status()

            data = response.json()
            return data

        except httpx.HTTPStatusError as e:
            raise FramerAPIError(
                f"HTTP {e.response.status_code}: {e.response.text}"
            ) from e

        except httpx.TimeoutException as e:
            raise FramerAPIError(
                f"Request timed out after {self.config.timeout} seconds"
            ) from e

        except httpx.RequestError as e:
            raise FramerAPIError(f"Request failed: {e}") from e

        except Exception as e:
            raise FramerAPIError(f"Unexpected error: {e}") from e

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
def push_report(
    report_data: dict[str, Any],
    api_url: str | None = None
) -> dict[str, Any]:
    """
    Push report to Framer CMS (convenience function).

    Args:
        report_data: Complete analysis result
        api_url: Framer API URL (uses env var if not provided)

    Returns:
        API response
    """
    config = None
    if api_url:
        config = FramerConfig(api_url=api_url)

    with FramerClient(config=config) as client:
        return client.push_report(report_data)
