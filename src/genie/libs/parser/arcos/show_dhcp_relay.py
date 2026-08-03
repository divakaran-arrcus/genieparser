"""show_dhcp_relay.py

ArcOS parsers for the following show commands:
    * show relay-agent dhcp
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowDhcpRelaySchema(MetaParser):
    schema = {
        Optional("helper-addresses"): list,
        Optional("use-interface-vrf"): bool,
        Optional("agent-information-option"): bool,
        Optional("counters"): {
            Optional("received-requests"): int,
            Optional("received-responses"): int,
            Optional("relayed-requests"): int,
            Optional("relayed-responses"): int,
            Optional("total-drops"): int,
        },
        Optional("interfaces"): {
            Any(): {
                "name": str,
                Optional("enabled"): bool,
                Optional("helper-addresses"): list,
            }
        },
    }


class ShowDhcpRelay(ShowDhcpRelaySchema):
    """Parser for DHCP relay state."""

    cli_command = "show relay-agent dhcp"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show relay-agent dhcp | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowDhcpRelay: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        relay = data.get("arcos-dhcp-relay:relay-agent", {})
        if not relay:
            relay = data.get("relay-agent", {})

        dhcp = relay.get("dhcp", {})
        if not dhcp:
            raise SchemaEmptyParserError("No DHCP relay data found")

        result = {}

        config = dhcp.get("config", dhcp.get("state", {}))
        helpers = config.get("helper-address", [])
        if helpers:
            result["helper-addresses"] = helpers if isinstance(helpers, list) else [helpers]

        use_vrf = config.get("use-interface-vrf")
        if use_vrf is not None:
            result["use-interface-vrf"] = use_vrf

        aio = config.get("agent-information-option", {})
        if aio:
            aio_config = aio.get("config", aio.get("state", aio))
            if "enable" in aio_config:
                result["agent-information-option"] = aio_config["enable"]

        counters = dhcp.get("counters", dhcp.get("state", {}).get("counters", {}))
        if counters:
            result["counters"] = {}
            for k in ("received-requests", "received-responses",
                       "relayed-requests", "relayed-responses", "total-drops"):
                if k in counters:
                    result["counters"][k] = counters[k]

        interfaces = dhcp.get("interface", dhcp.get("interfaces", {}).get("interface", []))
        if interfaces:
            if isinstance(interfaces, dict):
                interfaces = [interfaces]
            result["interfaces"] = {}
            for intf in interfaces:
                name = intf.get("name", intf.get("interface-name", ""))
                if not name:
                    continue
                i_config = intf.get("config", intf.get("state", intf))
                entry = {"name": name}
                if "enable" in i_config:
                    entry["enabled"] = i_config["enable"]
                i_helpers = i_config.get("helper-address", [])
                if i_helpers:
                    entry["helper-addresses"] = i_helpers if isinstance(i_helpers, list) else [i_helpers]
                result["interfaces"][name] = entry

        if not result:
            raise SchemaEmptyParserError("No DHCP relay data found")

        return result
