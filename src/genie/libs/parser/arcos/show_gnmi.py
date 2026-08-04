"""show_gnmi.py

ArcOS parsers for the following show commands:
    * show system grpc-server
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowGnmiServerSchema(MetaParser):
    schema = {
        Optional("enabled"): bool,
        Optional("transport-security"): bool,
        Optional("port"): int,
        Optional("listen-addresses"): list,
        Optional("clients-connected"): int,
    }


class ShowGnmiServer(ShowGnmiServerSchema):
    """Parser for gNMI gRPC server state."""

    cli_command = "show system grpc-server"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show system grpc-server | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowGnmiServer: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        sys_data = data.get("openconfig-system:system", data.get("system", {}))
        grpc = sys_data.get("arcos-grpc-server:grpc-server",
                            sys_data.get("grpc-server", {}))
        state = grpc.get("state", grpc.get("config", grpc))

        if not state:
            raise SchemaEmptyParserError("No gNMI server data found")

        result = {}
        if "enable" in state:
            result["enabled"] = state["enable"]
        if "transport-security" in state:
            result["transport-security"] = state["transport-security"]
        if "port" in state:
            result["port"] = state["port"]

        addrs = state.get("listen-addresses", [])
        if addrs:
            result["listen-addresses"] = addrs if isinstance(addrs, list) else [addrs]

        clients = grpc.get("clients", {})
        client_list = clients.get("client", [])
        if isinstance(client_list, list):
            result["clients-connected"] = len(client_list)

        if not result:
            raise SchemaEmptyParserError("No gNMI server data found")

        return result
