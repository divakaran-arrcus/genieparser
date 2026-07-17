"""ArcOS sFlow parser using JSON output.

Parser:
    ShowSflow — ``show sflow``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowSflowSchema(MetaParser):
    schema = {
        Optional("counter-sampling-interval"): int,
        Optional("packet-sampling-rate"): int,
        Optional("network-instance"): str,
        Optional("counter-samples"): int,
        Optional("packet-samples"): int,
        Optional("collectors"): {
            Any(): {  # address:port key
                "address": str,
                Optional("port"): int,
            }
        },
        Optional("interfaces"): {
            Any(): {  # interface name key
                "name": str,
                Optional("direction"): str,
                Optional("packet-sampling-rate"): int,
            }
        },
    }


class ShowSflow(ShowSflowSchema):
    """Parser for sFlow state."""

    cli_command = "show sflow"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show sflow | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSflow: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        sflow = data.get("openconfig-sampling:sampling", {})
        if not sflow:
            sflow = data.get("sampling", {})

        sflow_data = sflow.get("sflow", {})
        if not sflow_data:
            sflow_data = sflow

        state = sflow_data.get("state", sflow_data.get("config", {}))

        if not state and not sflow_data.get("collectors") and not sflow_data.get("interfaces"):
            raise SchemaEmptyParserError("No sFlow data found")

        result = {}

        for k in ("counter-sampling-interval", "packet-sampling-rate",
                   "network-instance", "counter-samples", "packet-samples"):
            if k in state:
                result[k] = state[k]

        collectors = sflow_data.get("collectors", {}).get("collector", [])
        if collectors:
            result["collectors"] = {}
            for c in collectors:
                addr = c.get("address", "")
                port = c.get("port", 6343)
                key = f"{addr}:{port}"
                entry = {"address": addr}
                if port:
                    entry["port"] = port
                result["collectors"][key] = entry

        interfaces = sflow_data.get("interfaces", {}).get("interface", [])
        if interfaces:
            result["interfaces"] = {}
            for intf in interfaces:
                name = intf.get("name", "")
                if not name:
                    continue
                i_state = intf.get("state", intf.get("config", {}))
                entry = {"name": name}
                if "direction" in i_state:
                    entry["direction"] = i_state["direction"]
                if "packet-sampling-rate" in i_state:
                    entry["packet-sampling-rate"] = i_state["packet-sampling-rate"]
                result["interfaces"][name] = entry

        if not result:
            raise SchemaEmptyParserError("No sFlow data found")

        return result
