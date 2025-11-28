"""ArcOS parser utilities.

Shared utility functions for ArcOS parsers.
"""

import json
import re
from typing import Any as TypeAny, Dict


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
    JSON. This helper normalizes those cases.
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

    return json.loads(json_str)
