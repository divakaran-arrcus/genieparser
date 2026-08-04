"""show_stp.py

ArcOS parsers for the following show commands:
    * show stp global
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowStpGlobalSchema(MetaParser):
    schema = {
        Optional("bridge-assurance"): bool,
        Optional("bpdu-guard"): bool,
        Optional("enabled-protocol"): str,
    }


class ShowStpGlobal(ShowStpGlobalSchema):
    """Parser for STP global state."""

    cli_command = "show stp global"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show stp global | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowStpGlobal: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        stp = data.get("openconfig-spanning-tree:stp", {})
        if not stp:
            stp = data.get("stp", {})

        global_data = stp.get("global", stp)
        config = global_data.get("config", global_data.get("state", {}))

        if not config:
            raise SchemaEmptyParserError("No STP global data found")

        result = {}

        if "bridge-assurance" in config:
            result["bridge-assurance"] = config["bridge-assurance"]
        if "bpdu-guard" in config:
            result["bpdu-guard"] = config["bpdu-guard"]

        ep = config.get("enabled-protocol", [])
        if ep:
            if isinstance(ep, list):
                val = ep[0] if ep else ""
            else:
                val = str(ep)
            if ":" in val:
                val = val.split(":")[-1]
            result["enabled-protocol"] = val

        if not result:
            raise SchemaEmptyParserError("No STP global data found")

        return result
