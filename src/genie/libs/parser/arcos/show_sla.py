"""ArcOS SLA ICMP parser using JSON output.

Parser:
    ShowSlaIcmp — ``show network-instance <ni> sla icmp``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowSlaIcmpSchema(MetaParser):
    schema = {
        Optional("admin-state"): bool,
        Optional("sessions"): {
            Any(): {
                "name": str,
                Optional("admin-state"): bool,
                Optional("target-address"): str,
                Optional("source-address"): str,
                Optional("session-interval"): int,
                Optional("probe-count"): int,
                Optional("probe-interval"): int,
                Optional("payload-size"): int,
            }
        },
    }


class ShowSlaIcmp(ShowSlaIcmpSchema):
    """Parser for SLA ICMP state."""

    cli_command = "show network-instance {ni} sla icmp"

    def cli(self, ni="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show network-instance {ni} sla icmp | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSlaIcmp: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        ni_container = data.get("openconfig-network-instance:network-instances",
                                data.get("network-instances", {}))
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            raise SchemaEmptyParserError("No SLA ICMP data found")

        ni_entry = ni_list[0] if isinstance(ni_list, list) else ni_list
        sla = ni_entry.get("arcos-sla:sla", ni_entry.get("sla", {}))
        icmp = sla.get("icmp", {})

        if not icmp:
            raise SchemaEmptyParserError("No SLA ICMP data found")

        result = {}

        state = icmp.get("state", icmp.get("config", icmp))
        if "admin-state" in state:
            result["admin-state"] = state["admin-state"] in (True, "true")

        sessions = icmp.get("icmp-session", [])
        if isinstance(sessions, dict):
            sessions = [sessions]

        if sessions:
            result["sessions"] = {}
            for sess in sessions:
                name = sess.get("session-name", sess.get("name", ""))
                if not name:
                    continue
                s_state = sess.get("state", sess.get("config", sess))
                entry = {"name": name}
                if "admin-state" in s_state:
                    entry["admin-state"] = s_state["admin-state"] in (True, "true")
                for k in ("target-address", "source-address", "session-interval"):
                    if k in s_state:
                        entry[k] = s_state[k]
                probe = sess.get("probe", {}).get("state", sess.get("probe", {}))
                for k in ("probe-count", "probe-interval", "payload-size"):
                    if k in probe:
                        entry[k] = probe[k]
                result["sessions"][name] = entry

        if not result:
            raise SchemaEmptyParserError("No SLA ICMP data found")

        return result
