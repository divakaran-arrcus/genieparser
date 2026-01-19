"""ArcOS parser utilities.

Shared utility functions for ArcOS parsers.
"""

import json
import re
import logging
from typing import Any as TypeAny, Dict

logger = logging.getLogger(__name__)


def validate_input(input_str: str, param_name: str) -> None:
    """Validate that input string contains only safe characters.

    Allowed characters: alphanumeric, hyphen, underscore, dot, colon, slash.
    Raises ValueError if input contains invalid characters.
    """
    if not input_str:
        return

    if not isinstance(input_str, str):
        raise ValueError(f"Parameter '{param_name}' must be a string")

    # Allow alphanumeric, -, _, ., :, /, *
    if not re.match(r"^[a-zA-Z0-9\-_\.:/*]+$", input_str):
        raise ValueError(
            f"Invalid characters in parameter '{param_name}': {input_str}"
        )


def load_json_robust(output: TypeAny) -> Dict:
    """Load JSON from CLI output or a pre-decoded dict.

    Some devices or helper layers may return a Python dict instead of a raw
    JSON string. CLI output may also contain prompts or banners around the
    JSON. This helper normalizes those cases and attempts to fix common
    JSON formatting issues from network devices.
    """

    if isinstance(output, dict):
        return output

    if not isinstance(output, str):
        output = str(output)

    start = output.find("{")
    end = output.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = output[start : end + 1]
    else:
        json_str = output

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("Initial JSON parsing failed at position %d: %s", e.pos, e.msg)
        
        # Try to fix common JSON issues
        fixed_json = _fix_json_issues(json_str, e.pos)
        
        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError as e2:
            # If still failing, provide detailed error context
            error_context_start = max(0, e2.pos - 200)
            error_context_end = min(len(fixed_json), e2.pos + 200)
            error_context = fixed_json[error_context_start:error_context_end]
            
            logger.error("JSON parsing failed even after fixes. Context: ...%s...", error_context)
            
            raise json.JSONDecodeError(
                f"{e2.msg}. Context around error position: ...{error_context}...",
                e2.doc,
                e2.pos
            ) from e


def _fix_json_issues(json_str: str, error_pos: int) -> str:
    """Attempt to fix common JSON formatting issues.
    
    Args:
        json_str: The malformed JSON string
        error_pos: Position where the error occurred
        
    Returns:
        Fixed JSON string
    """
    # Common issue: trailing commas before closing brackets/braces
    # Pattern: ,\s*} or ,\s*]
    fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Check if we made any changes
    if fixed != json_str:
        logger.info("Fixed %d trailing comma issues", len(re.findall(r',(\s*[}\]])', json_str)))
    
    return fixed
