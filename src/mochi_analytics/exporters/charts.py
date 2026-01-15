"""Chart generation using Plotly with base64 encoding for database storage."""

from typing import List, Dict, Optional
import plotly.graph_objects as go
import base64
import tomli
from pathlib import Path
from mochi_analytics.core.models import DayStages
import logging

logger = logging.getLogger(__name__)


def load_chart_configs(config_path: str) -> Dict:
    """
    Load chart configurations from TOML file.

    Args:
        config_path: Path to charts.toml file

    Returns:
        Dict with global config and list of chart configs
    """
    with open(config_path, "rb") as f:
        config = tomli.load(f)

    return config


def generate_all_charts(
    time_series_data: List[DayStages],
    config_path: str
) -> Dict[str, str]:
    """
    Generate all charts from configuration.

    Args:
        time_series_data: List of DayStages with stage counts per day
        config_path: Path to charts.toml configuration file

    Returns:
        Dict mapping chart_id to base64-encoded PNG string
    """
    config = load_chart_configs(config_path)
    global_config = config.get("global", {})
    chart_configs = config.get("charts", [])

    results = {}

    for chart_config in chart_configs:
        try:
            chart_id = chart_config["id"]
            png_base64 = generate_chart(time_series_data, chart_config, global_config)
            results[chart_id] = png_base64
            logger.info(f"✓ Generated chart: {chart_id}")
        except Exception as e:
            logger.error(f"✗ Failed to generate chart {chart_config.get('id', 'unknown')}: {e}")

    return results


def generate_chart(
    time_series_data: List[DayStages],
    chart_config: Dict,
    global_config: Dict
) -> str:
    """
    Generate a single PNG chart from time series data.

    Args:
        time_series_data: List of DayStages
        chart_config: Chart-specific configuration
        global_config: Global chart settings

    Returns:
        Base64-encoded PNG string
    """
    fig = go.Figure()

    # Add traces for each line in config
    for line_config in chart_config.get("lines", []):
        stage = line_config["stage"]
        dates = [day.date for day in time_series_data]
        values = [day.stages.get(stage, 0) for day in time_series_data]

        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            name=line_config.get("label", stage),
            mode="lines+markers",
            line=dict(
                color=line_config.get("line_color", "#FFFFFF"),
                width=line_config.get("line_width", 3)
            ),
            marker=dict(
                symbol=line_config.get("marker_shape", "circle"),
                size=line_config.get("marker_size", 30),
                color=line_config.get("marker_fill", "#FFFFFF"),
                line=dict(
                    color=line_config.get("marker_border_color", "#000000"),
                    width=line_config.get("marker_border_width", 3)
                )
            )
        ))

    # Update layout
    fig.update_layout(
        title=dict(
            text=chart_config.get("title", "Chart"),
            font=dict(
                size=global_config.get("title_font_size", 24),
                color=global_config.get("text_color", "#FFFFFF")
            )
        ),
        width=global_config.get("width", 1400),
        height=global_config.get("height", 700),
        plot_bgcolor=global_config.get("background_color", "#0e1117"),
        paper_bgcolor=global_config.get("background_color", "#0e1117"),
        font=dict(
            color=global_config.get("text_color", "#FFFFFF"),
            size=global_config.get("font_size", 14)
        ),
        xaxis=dict(
            showgrid=global_config.get("show_grid", True),
            gridcolor=global_config.get("grid_color", "#2d2d2d"),
            zeroline=False
        ),
        yaxis=dict(
            showgrid=global_config.get("show_grid", True),
            gridcolor=global_config.get("grid_color", "#2d2d2d"),
            zeroline=False
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=global_config.get("legend_font_size", 12))
        ),
        margin=dict(l=60, r=40, t=80, b=60)
    )

    # Export to PNG bytes
    try:
        png_bytes = fig.to_image(
            format="png",
            scale=global_config.get("scale", 2),
            engine="kaleido"
        )
    except Exception as e:
        logger.error(f"Failed to render PNG: {e}")
        raise

    # Encode to base64
    png_base64 = base64.b64encode(png_bytes).decode('utf-8')

    return png_base64


def save_chart_to_file(png_base64: str, output_path: str):
    """
    Save base64-encoded PNG to file.

    Args:
        png_base64: Base64-encoded PNG string
        output_path: Output file path
    """
    png_bytes = base64.b64decode(png_base64)

    with open(output_path, "wb") as f:
        f.write(png_bytes)

    logger.info(f"Saved chart to {output_path}")
