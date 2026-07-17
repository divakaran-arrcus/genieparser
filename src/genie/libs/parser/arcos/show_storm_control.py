"""ArcOS Storm Control parser using JSON output.

Parser:
    ShowStormControl — ``show interface <name> storm-control``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowStormControlSchema(MetaParser):
    schema = {
        Optional("broadcast-kbps"): int,
        Optional("multicast-kbps"): int,
        Optional("unknown-unicast-kbps"): int,
    }


class ShowStormControl(ShowStormControlSchema):
    """Parser for storm control state on an interface."""

    cli_command = "show interface {interface} storm-control"

    def cli(self, interface="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show interface {interface} storm-control | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowStormControl: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        intf_container = data.get("openconfig-interfaces:interfaces", {})
        if not intf_container:
            intf_container = data.get("interfaces", {})

        intf_list = intf_container.get("interface", [])
        if not intf_list:
            raise SchemaEmptyParserError("No storm control data found")

        intf = intf_list[0] if isinstance(intf_list, list) else intf_list
        sc = intf.get("arcos-storm-control:storm-control", intf.get("storm-control", {}))
        state = sc.get("state", sc.get("config", sc))

        if not state:
            raise SchemaEmptyParserError("No storm control data found")

        result = {}
        for k in ("broadcast-kbps", "multicast-kbps", "unknown-unicast-kbps"):
            if k in state:
                result[k] = state[k]

        if not result:
            raise SchemaEmptyParserError("No storm control data found")

        return result
