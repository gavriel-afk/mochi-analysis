"""
JSON export functionality.
"""

from mochi_analytics.core.models import AnalysisResult


def export_json(result: AnalysisResult, indent: int = 2) -> str:
    """
    Export analysis result to JSON string.

    Args:
        result: Analysis result to export
        indent: Number of spaces for indentation (default: 2)

    Returns:
        JSON string
    """
    return result.model_dump_json(indent=indent)


def export_json_dict(result: AnalysisResult) -> dict:
    """
    Export analysis result to dictionary.

    Args:
        result: Analysis result to export

    Returns:
        Dictionary representation
    """
    return result.model_dump()
