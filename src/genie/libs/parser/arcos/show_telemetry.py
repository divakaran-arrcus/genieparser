"""ArcOS Telemetry parser using JSON output.

Parser:
    ShowTelemetry — ``show telemetry-system``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowTelemetrySchema(MetaParser):
    schema = {
        Optional("status"): str,
        Optional("cuid"): str,
        Optional("destination-groups"): {
            Any(): {
                "name": str,
                Optional("destinations"): list,
            }
        },
        Optional("subscriptions"): {
            Any(): {
                "name": str,
                Optional("sensors"): list,
                Optional("destination-group"): str,
            }
        },
    }


class ShowTelemetry(ShowTelemetrySchema):
    """Parser for telemetry system state."""

    cli_command = "show telemetry-system"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show telemetry-system | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        ts = data.get("arcos-telemetry:telemetry-system",
                       data.get("telemetry-system", {}))

        if not ts:
            raise SchemaEmptyParserError("No telemetry data found")

        result = {}

        global_data = ts.get("global", {})
        g_state = global_data.get("state", global_data.get("config", global_data))
        if "status" in g_state:
            result["status"] = g_state["status"]
        if "cuid" in g_state:
            result["cuid"] = g_state["cuid"]

        dg_list = ts.get("destination-group", ts.get("destination-groups", {}).get("destination-group", []))
        if dg_list:
            if isinstance(dg_list, dict):
                dg_list = [dg_list]
            result["destination-groups"] = {}
            for dg in dg_list:
                name = dg.get("group-id", dg.get("name", ""))
                if not name:
                    continue
                entry = {"name": name}
                dests = dg.get("destination", dg.get("destinations", []))
                if dests:
                    if isinstance(dests, dict):
                        dests = [dests]
                    entry["destinations"] = [
                        f"{d.get('address', d.get('destination-address', ''))}:{d.get('port', d.get('destination-port', ''))}"
                        for d in dests
                    ]
                result["destination-groups"][name] = entry

        sub_list = ts.get("persistent-subscription",
                          ts.get("subscriptions", {}).get("persistent-subscription", []))
        if sub_list:
            if isinstance(sub_list, dict):
                sub_list = [sub_list]
            result["subscriptions"] = {}
            for sub in sub_list:
                name = sub.get("subscription-name", sub.get("name", ""))
                if not name:
                    continue
                s_state = sub.get("state", sub.get("config", sub))
                entry = {"name": name}
                sensors = s_state.get("sensors", [])
                if sensors:
                    entry["sensors"] = sensors if isinstance(sensors, list) else [sensors]
                dg = s_state.get("destination-group", "")
                if dg:
                    entry["destination-group"] = dg
                result["subscriptions"][name] = entry

        if not result:
            raise SchemaEmptyParserError("No telemetry data found")

        return result
