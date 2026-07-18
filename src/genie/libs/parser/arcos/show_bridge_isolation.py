"""ArcOS Bridge Isolation parser using JSON output.

Parser:
    ShowBridgeIsolation — ``show interface <name> bridge-isolation``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowBridgeIsolationSchema(MetaParser):
    schema = {
        Optional("isolation-enabled"): bool,
        Optional("isolation-drop-packets"): int,
        Optional("isolation-drop-octets"): int,
    }


class ShowBridgeIsolation(ShowBridgeIsolationSchema):
    """Parser for bridge isolation state on an interface."""

    cli_command = "show interface {interface} bridge-isolation"

    def cli(self, interface="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show interface {interface} bridge-isolation | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowBridgeIsolation: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        intf_container = data.get("openconfig-interfaces:interfaces",
                                  data.get("interfaces", {}))
        intf_list = intf_container.get("interface", [])

        if not intf_list:
            raise SchemaEmptyParserError("No bridge isolation data found")

        intf = intf_list[0] if isinstance(intf_list, list) else intf_list
        bi = intf.get("arcos-bridge-isolation:bridge-isolation",
                      intf.get("bridge-isolation", {}))
        state = bi.get("state", bi)

        if not state:
            raise SchemaEmptyParserError("No bridge isolation data found")

        result = {}
        if "isolation" in state:
            val = state["isolation"]
            result["isolation-enabled"] = val in ("enable", True, "true")
        if "isolation-drop-packets" in state:
            result["isolation-drop-packets"] = state["isolation-drop-packets"]
        if "isolation-drop-octets" in state:
            result["isolation-drop-octets"] = state["isolation-drop-octets"]

        if not result:
            raise SchemaEmptyParserError("No bridge isolation data found")

        return result
