"""
Slack integration for sending daily digest messages.
"""

import os
from typing import Any

import httpx
from pydantic import BaseModel, Field


class SlackAPIError(Exception):
    """Raised when Slack API returns an error."""
    pass


class SlackConfig(BaseModel):
    """Configuration for Slack API."""

    bot_token: str = Field(..., description="Slack bot token (xoxb-...)")
    api_url: str = Field(
        default="https://slack.com/api",
        description="Slack API base URL"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")


class SlackClient:
    """Client for interacting with Slack API."""

    def __init__(self, config: SlackConfig | None = None):
        """
        Initialize Slack client.

        Args:
            config: Optional configuration. If not provided, reads from environment.
        """
        if config is None:
            bot_token = os.getenv("SLACK_BOT_TOKEN")
            if not bot_token:
                raise ValueError("SLACK_BOT_TOKEN environment variable is required")
            config = SlackConfig(bot_token=bot_token)

        self.config = config
        self.client = httpx.Client(
            base_url=config.api_url,
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.bot_token}",
                "Content-Type": "application/json"
            }
        )

    def post_message(
        self,
        channel: str,
        blocks: list[dict[str, Any]],
        text: str | None = None
    ) -> dict[str, Any]:
        """
        Post a message to a Slack channel using Block Kit.

        Args:
            channel: Slack channel ID (e.g., "C01234567")
            blocks: List of Block Kit blocks
            text: Fallback text for notifications (optional)

        Returns:
            API response with channel, ts (timestamp), and ok status

        Raises:
            SlackAPIError: If API request fails
        """
        payload = {
            "channel": channel,
            "blocks": blocks
        }
        if text:
            payload["text"] = text

        try:
            response = self.client.post("/chat.postMessage", json=payload)
            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):
                error = data.get("error", "unknown_error")
                raise SlackAPIError(f"Slack API error: {error}")

            return data

        except httpx.HTTPStatusError as e:
            raise SlackAPIError(f"HTTP {e.response.status_code}: {e.response.text}") from e

        except httpx.TimeoutException as e:
            raise SlackAPIError(
                f"Request timed out after {self.config.timeout} seconds"
            ) from e

        except httpx.RequestError as e:
            raise SlackAPIError(f"Request failed: {e}") from e

        except Exception as e:
            raise SlackAPIError(f"Unexpected error: {e}") from e

    def send_daily_digest(
        self,
        channel: str,
        org_name: str,
        instagram_handle: str | None,
        summary: dict[str, Any],
        setters: dict[str, Any] | None = None,
        date_range: str | None = None
    ) -> dict[str, Any]:
        """
        Send a formatted daily digest message.

        Args:
            channel: Slack channel ID
            org_name: Organization name
            instagram_handle: Instagram username (optional)
            summary: Analysis summary with metrics
            setters: Setter analysis data (optional)
            date_range: Date range string (e.g., "Jan 8 - Jan 14")

        Returns:
            API response
        """
        # Build header text
        if instagram_handle:
            header_text = f"@{instagram_handle} - What happened yesterday in Mochi:"
        else:
            header_text = f"{org_name} - What happened yesterday in Mochi:"

        # Build blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                    "emoji": True
                }
            }
        ]

        # Add total stage changes at the top
        stage_changes = summary.get('stage_changes', {})
        if stage_changes:
            stage_text = ""
            for stage, count in sorted(stage_changes.items()):
                if count > 0:
                    stage_name = stage.replace('_', ' ').title()
                    stage_text += f"*{stage_name}:* {count}\n"

            stage_text += "\n_Below is the breakdown per setter:_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": stage_text
                }
            })

        # Add setter performance if available
        if setters:
            # setters is a dict like {"setter@email.com": {...metrics...}}
            for setter_email, metrics in setters.items():
                # Ensure metrics is a dict
                if not isinstance(metrics, dict):
                    metrics = dict(metrics) if hasattr(metrics, '__dict__') else {}

                # Add divider before each setter
                blocks.append({"type": "divider"})

                # Add setter name in bold using rich_text
                blocks.append({
                    "type": "rich_text",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {
                                    "type": "text",
                                    "text": setter_email,
                                    "style": {"bold": True}
                                }
                            ]
                        }
                    ]
                })

                # Add messages sent count
                messages_sent = metrics.get('total_messages_sent_from_mochi', 0) if isinstance(metrics, dict) else 0
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Messages sent from Mochi:* {messages_sent}"
                    }
                })

                # Add stage breakdown in 2-column format
                setter_stages = metrics.get('stage_changes', {}) if isinstance(metrics, dict) else {}
                if setter_stages:
                    fields = []
                    for stage, count in sorted(setter_stages.items()):
                        if count > 0:
                            stage_name = stage.replace('_', ' ').title()
                            fields.append({
                                "type": "mrkdwn",
                                "text": f"*{stage_name}:* {count}"
                            })

                    if fields:
                        blocks.append({
                            "type": "section",
                            "fields": fields[:10]  # Slack max 10 fields
                        })

        # Send message
        fallback_text = f"Daily update for {org_name}"
        return self.post_message(channel, blocks, fallback_text)

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
def send_daily_digest(
    channel: str,
    org_name: str,
    instagram_handle: str | None,
    summary: dict[str, Any],
    setters: dict[str, Any] | None = None,
    date_range: str | None = None,
    bot_token: str | None = None
) -> dict[str, Any]:
    """
    Send daily digest message (convenience function).

    Args:
        channel: Slack channel ID
        org_name: Organization name
        instagram_handle: Instagram username (optional)
        summary: Analysis summary
        setters: Setter analysis (optional)
        date_range: Date range string (optional)
        bot_token: Bot token (uses env var if not provided)

    Returns:
        API response
    """
    config = None
    if bot_token:
        config = SlackConfig(bot_token=bot_token)

    with SlackClient(config=config) as client:
        return client.send_daily_digest(
            channel=channel,
            org_name=org_name,
            instagram_handle=instagram_handle,
            summary=summary,
            setters=setters,
            date_range=date_range
        )
