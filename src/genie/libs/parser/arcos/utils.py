"""ArcOS parser utilities.

Shared utility functions for ArcOS parsers.
"""

import json
from typing import Any as TypeAny, Dict


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
