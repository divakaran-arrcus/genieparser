"""ArcOS Interface Damping parser using JSON output.

Parser:
    ShowDamping — ``show interface <name> damping``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowDampingSchema(MetaParser):
    schema = {
        Optional("enabled"): bool,
        Optional("max-suppress-time"): int,
        Optional("decay-half-life"): int,
        Optional("suppress-threshold"): int,
        Optional("reuse-threshold"): int,
        Optional("flap-penalty"): int,
        Optional("penalty-count"): int,
        Optional("suppress-state"): bool,
    }


class ShowDamping(ShowDampingSchema):
    """Parser for interface damping state."""

    cli_command = "show interface {interface} damping"

    def cli(self, interface="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show interface {interface} damping | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowDamping: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        intf_container = data.get("openconfig-interfaces:interfaces", {})
        if not intf_container:
            intf_container = data.get("interfaces", {})

        intf_list = intf_container.get("interface", [])
        if not intf_list:
            raise SchemaEmptyParserError("No damping data found")

        intf = intf_list[0] if isinstance(intf_list, list) else intf_list
        damping = intf.get("arcos-damping:damping", intf.get("damping", {}))
        state = damping.get("state", damping.get("config", damping))

        if not state:
            raise SchemaEmptyParserError("No damping data found")

        result = {}
        for k in ("enabled", "max-suppress-time", "decay-half-life",
                   "suppress-threshold", "reuse-threshold", "flap-penalty",
                   "penalty-count", "suppress-state"):
            if k in state:
                result[k] = state[k]

        if not result:
            raise SchemaEmptyParserError("No damping data found")

        return result
