"""
Airtable integration for organization configuration and Slack channel mappings.
"""

import os
from typing import Any

from pydantic import BaseModel, Field
from pyairtable import Api


class OrganizationConfig(BaseModel):
    """Configuration for a Mochi organization."""

    record_id: str = Field(..., description="Airtable record ID")
    organization_name: str = Field(..., description="Display name")
    organization_id: str = Field(..., description="Mochi org UUID")
    timezone: str = Field(..., description="IANA timezone (e.g., Asia/Dubai)")
    instagram_username: str | None = Field(None, description="Instagram handle")
    active: bool = Field(default=True, description="Whether org is active")


class SlackDailyConfig(BaseModel):
    """Configuration for daily Slack updates."""

    record_id: str = Field(..., description="Airtable record ID")
    organization_id: str = Field(..., description="Mochi org UUID from linked record")
    slack_channel: str = Field(..., description="Slack channel ID (e.g., C01234567)")
    stages: list[str] = Field(
        default_factory=list,
        description="Stage types to report (e.g., ['NEW_LEAD', 'QUALIFIED'])"
    )
    schedule_time: str = Field(
        default="12:00",
        description="Time to send update in HH:MM format (org timezone)"
    )
    active: bool = Field(default=True, description="Whether Slack updates are enabled")


class AirtableConfig(BaseModel):
    """Configuration for Airtable API."""

    api_key: str = Field(..., description="Airtable API key")
    base_id: str = Field(..., description="Airtable base ID")


class AirtableClient:
    """Client for interacting with Airtable API."""

    def __init__(self, config: AirtableConfig | None = None):
        """
        Initialize Airtable client.

        Args:
            config: Optional configuration. If not provided, reads from environment.
        """
        if config is None:
            api_key = os.getenv("AIRTABLE_API_KEY")
            base_id = os.getenv("AIRTABLE_BASE_ID")
            if not api_key or not base_id:
                raise ValueError(
                    "AIRTABLE_API_KEY and AIRTABLE_BASE_ID environment variables are required"
                )
            config = AirtableConfig(api_key=api_key, base_id=base_id)

        self.config = config
        self.api = Api(config.api_key)
        self.orgs_table = self.api.table(config.base_id, "Mochi Organization")
        self.slack_table = self.api.table(config.base_id, "Slack Daily")

    def get_organizations(self, active_only: bool = True) -> list[OrganizationConfig]:
        """
        Get all organization configurations.

        Args:
            active_only: If True, only return active organizations

        Returns:
            List of organization configurations
        """
        formula = "{Active} = TRUE()" if active_only else None
        records = self.orgs_table.all(formula=formula)

        orgs = []
        for record in records:
            fields = record["fields"]
            orgs.append(
                OrganizationConfig(
                    record_id=record["id"],
                    organization_name=fields.get("Organization Name", ""),
                    organization_id=fields.get("Organization ID", ""),
                    timezone=fields.get("Timezone", "UTC"),
                    instagram_username=fields.get("Instagram Username"),
                    active=fields.get("Active", False)
                )
            )

        return orgs

    def get_organization_by_id(self, org_id: str) -> OrganizationConfig | None:
        """
        Get organization configuration by org ID.

        Args:
            org_id: Mochi organization UUID

        Returns:
            Organization configuration or None if not found
        """
        formula = f"{{Organization ID}} = '{org_id}'"
        records = self.orgs_table.all(formula=formula)

        if not records:
            return None

        record = records[0]
        fields = record["fields"]
        return OrganizationConfig(
            record_id=record["id"],
            organization_name=fields.get("Organization Name", ""),
            organization_id=fields.get("Organization ID", ""),
            timezone=fields.get("Timezone", "UTC"),
            instagram_username=fields.get("Instagram Username"),
            active=fields.get("Active", False)
        )

    def get_slack_configs(self, active_only: bool = True) -> list[SlackDailyConfig]:
        """
        Get all Slack daily update configurations.

        Args:
            active_only: If True, only return active configurations

        Returns:
            List of Slack configurations
        """
        formula = "{Active} = TRUE()" if active_only else None
        records = self.slack_table.all(formula=formula)

        configs = []
        for record in records:
            fields = record["fields"]

            # Get linked organization ID
            org_links = fields.get("Organization", [])
            if not org_links:
                continue  # Skip if no org linked

            # Fetch the linked organization record to get the org ID
            org_record_id = org_links[0]
            org_record = self.orgs_table.get(org_record_id)
            org_id = org_record["fields"].get("Organization ID", "")

            # Parse stages (comma-separated string or list)
            stages_field = fields.get("Stages", "")
            if isinstance(stages_field, list):
                # If Stages is a multi-select field, it comes as a list
                stages = stages_field
            elif isinstance(stages_field, str):
                # If Stages is a text field, split by comma
                stages = [s.strip() for s in stages_field.split(",") if s.strip()]
            else:
                stages = []

            configs.append(
                SlackDailyConfig(
                    record_id=record["id"],
                    organization_id=org_id,
                    slack_channel=fields.get("Slack Channel", ""),
                    stages=stages,
                    schedule_time=fields.get("Schedule Time", "12:00"),
                    active=fields.get("Active", False)
                )
            )

        return configs

    def get_slack_config_for_org(self, org_id: str) -> SlackDailyConfig | None:
        """
        Get Slack configuration for a specific organization.

        Args:
            org_id: Mochi organization UUID

        Returns:
            Slack configuration or None if not found
        """
        all_configs = self.get_slack_configs(active_only=True)
        for config in all_configs:
            if config.organization_id == org_id:
                return config
        return None


# Convenience functions
def get_organizations(active_only: bool = True) -> list[OrganizationConfig]:
    """Get all organization configurations (convenience function)."""
    client = AirtableClient()
    return client.get_organizations(active_only=active_only)


def get_organization_by_id(org_id: str) -> OrganizationConfig | None:
    """Get organization by ID (convenience function)."""
    client = AirtableClient()
    return client.get_organization_by_id(org_id)


def get_slack_configs(active_only: bool = True) -> list[SlackDailyConfig]:
    """Get all Slack configurations (convenience function)."""
    client = AirtableClient()
    return client.get_slack_configs(active_only=active_only)


def get_slack_config_for_org(org_id: str) -> SlackDailyConfig | None:
    """Get Slack config for organization (convenience function)."""
    client = AirtableClient()
    return client.get_slack_config_for_org(org_id)
