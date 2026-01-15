"""
Airtable integration for organization configuration and Slack channel mappings.
"""

import logging
import os
from typing import Any

from pydantic import BaseModel, Field
from pyairtable import Api

logger = logging.getLogger(__name__)


class OrganizationConfig(BaseModel):
    """Configuration for a Mochi organization."""

    record_id: str = Field(..., description="Airtable record ID")
    organization_name: str = Field(..., description="Display name")
    organization_id: str = Field(..., description="Mochi org UUID")
    timezone: str = Field(..., description="IANA timezone (e.g., Asia/Dubai)")
    instagram_username: str | None = Field(None, description="Instagram handle")
    active: bool = Field(default=True, description="Whether org is active")


class ScriptAnalysisConfig(BaseModel):
    """Configuration for script similarity analysis."""

    query: str = Field(..., description="Query text to search for (from Name field)")
    label: str = Field(..., description="Display label for Slack message")
    match_type: str = Field(
        default="token_set",
        description="Match type: 'ratio', 'token_set', or 'partial'"
    )
    threshold: float = Field(
        default=85.0,
        description="Similarity threshold percentage (0-100)"
    )


class SlackDailyConfig(BaseModel):
    """Configuration for daily Slack updates."""

    record_id: str = Field(..., description="Airtable record ID")
    organization_id: str = Field(..., description="Mochi org UUID from linked record")
    slack_channel: str = Field(..., description="Slack channel ID (e.g., C01234567)")
    stage_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Stage name to display label mapping from Analysis table (e.g., {'Won': 'closed'})"
    )
    script_configs: list[ScriptAnalysisConfig] = Field(
        default_factory=list,
        description="Script analysis configurations from Analysis table (Type='script')"
    )
    schedule_time: str = Field(
        default="",
        description="Time to send update in HH:MM format (org timezone). Empty string means manual-only (requires force_send=True)"
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
        self.analysis_table = self.api.table(config.base_id, "Analysis")

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
        logger.info(f"Found {len(records)} Slack Daily records (active_only={active_only})")

        configs = []
        for record in records:
            fields = record["fields"]

            # Get linked organization ID
            org_links = fields.get("Organization", [])
            if not org_links:
                logger.debug(f"Skipping record {record['id']}: no Organization linked")
                continue  # Skip if no org linked

            # Fetch the linked organization record to get the org ID
            org_record_id = org_links[0]
            org_record = self.orgs_table.get(org_record_id)
            org_id = org_record["fields"].get("Organization ID", "")
            org_name = org_record["fields"].get("Organization Name", "Unknown")

            # Fetch linked Analysis records
            analysis_links = fields.get("Analysis", [])
            stage_labels = {}
            script_configs = []

            if analysis_links:
                logger.debug(f"Org {org_name}: found {len(analysis_links)} Analysis links")
                for analysis_record_id in analysis_links:
                    try:
                        analysis_record = self.analysis_table.get(analysis_record_id)
                        analysis_fields = analysis_record["fields"]

                        record_type = analysis_fields.get("Type", "")

                        if record_type == "metrics":
                            # Parse metrics: Name -> stage name, Label -> display label
                            stage_name = analysis_fields.get("Name", "")
                            stage_label = analysis_fields.get("Label", "")

                            if stage_name:
                                stage_labels[stage_name] = stage_label if stage_label else stage_name
                                logger.debug(f"Org {org_name}: added stage '{stage_name}' -> '{stage_labels[stage_name]}'")

                        elif record_type == "script":
                            # Parse script: Name -> query, Group -> match_type, Percentage -> threshold
                            query = analysis_fields.get("Name", "")
                            label = analysis_fields.get("Label", "")
                            match_type = analysis_fields.get("Group", "token_set")
                            threshold = analysis_fields.get("Percentage", 85.0)

                            if query:
                                # Validate match_type
                                if match_type not in ("ratio", "token_set", "partial"):
                                    match_type = "token_set"

                                script_configs.append(ScriptAnalysisConfig(
                                    query=query,
                                    label=label if label else query[:50],
                                    match_type=match_type,
                                    threshold=float(threshold) if threshold else 85.0
                                ))
                                logger.debug(f"Org {org_name}: added script config '{label or query[:50]}'")
                        else:
                            logger.debug(f"Org {org_name}: skipping Analysis record with Type='{record_type}'")
                    except Exception as e:
                        logger.warning(f"Failed to fetch Analysis record {analysis_record_id}: {e}")
            else:
                logger.warning(f"Org {org_name}: no Analysis records linked")

            # Get schedule_time (allow empty - will be skipped in automated runs unless force_send=True)
            schedule_time = fields.get("Schedule Time", "").strip()
            if not schedule_time:
                logger.info(f"Org {org_name}: no Schedule Time set (will only run with force_send=True)")
                schedule_time = ""  # Empty string indicates no schedule

            logger.info(f"Org {org_name}: adding config with {len(stage_labels)} stage labels, {len(script_configs)} script configs")
            configs.append(
                SlackDailyConfig(
                    record_id=record["id"],
                    organization_id=org_id,
                    slack_channel=fields.get("Slack Channel", ""),
                    stage_labels=stage_labels,
                    script_configs=script_configs,
                    schedule_time=schedule_time,
                    active=fields.get("Active", False)
                )
            )

        logger.info(f"Returning {len(configs)} Slack configs")
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
