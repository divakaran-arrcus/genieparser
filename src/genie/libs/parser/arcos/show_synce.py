"""ArcOS SyncE parser using JSON output.

Parser:
    ShowSynce — ``show operational-state sync-e``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowSynceSchema(MetaParser):
    schema = {
        Optional("enabled"): bool,
        Optional("holdover"): int,
        Optional("quality-level-enabled"): bool,
        Optional("revertive-enabled"): bool,
        Optional("clock-state"): str,
    }


class ShowSynce(ShowSynceSchema):
    """Parser for SyncE state."""

    cli_command = "show operational-state sync-e"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show operational-state sync-e | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        synce = data.get("arcos-synce:sync-e", data.get("sync-e", {}))

        state = synce.get("state", synce.get("config", synce))
        if not state:
            raise SchemaEmptyParserError("No SyncE data found")

        result = {}
        if "enabled" in state:
            result["enabled"] = state["enabled"]
        if "holdover" in state:
            result["holdover"] = state["holdover"]
        if "quality-level-enabled" in state:
            result["quality-level-enabled"] = state["quality-level-enabled"]
        if "revertive-enabled" in state:
            result["revertive-enabled"] = state["revertive-enabled"]
        if "sync-e-clock-state" in state:
            result["clock-state"] = state["sync-e-clock-state"]

        if not result:
            raise SchemaEmptyParserError("No SyncE data found")

        return result
