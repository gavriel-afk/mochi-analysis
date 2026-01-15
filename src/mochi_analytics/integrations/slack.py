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
        header_text = f"Daily Update - {org_name}"
        if instagram_handle:
            header_text = f"Daily Update - @{instagram_handle}"

        # Build blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text
                }
            }
        ]

        # Add date range if provided
        if date_range:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Period:* {date_range}"
                    }
                ]
            })

        # Add divider
        blocks.append({"type": "divider"})

        # Add metrics section
        metrics_text = "*Yesterday's Metrics*\n\n"
        metrics_text += f"• *Conversations:* {summary.get('total_conversations', 0)}\n"
        metrics_text += f"• *Messages Sent:* {summary.get('total_messages_sent', 0)}\n"
        metrics_text += f"• *Messages Received:* {summary.get('total_messages_received', 0)}\n"

        reply_rate = summary.get('creator_message_reply_rate_within_48h')
        if reply_rate is not None:
            metrics_text += f"• *Reply Rate (48h):* {reply_rate:.1f}%\n"

        median_delay = summary.get('median_reply_delay_seconds')
        if median_delay is not None:
            hours = median_delay / 3600
            metrics_text += f"• *Median Reply Time:* {hours:.1f} hours\n"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": metrics_text
            }
        })

        # Add stage changes if available
        stage_changes = summary.get('stage_changes', {})
        if stage_changes:
            blocks.append({"type": "divider"})

            stage_text = "*Stage Changes*\n\n"
            for stage, count in stage_changes.items():
                if count > 0:
                    stage_name = stage.replace('_', ' ').title()
                    stage_text += f"• {stage_name}: {count}\n"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": stage_text
                }
            })

        # Add setter performance if available
        if setters:
            setter_list = setters.get('setters', [])
            if setter_list:
                blocks.append({"type": "divider"})

                setter_text = "*Top Setters*\n\n"
                for i, setter in enumerate(setter_list[:5], 1):  # Top 5
                    email = setter.get('setter_email', 'Unknown')
                    convos = setter.get('total_conversations', 0)
                    msgs = setter.get('messages_sent', 0)
                    setter_text += f"{i}. {email} - {convos} convos, {msgs} msgs\n"

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": setter_text
                    }
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
