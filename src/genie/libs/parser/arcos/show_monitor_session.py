"""ArcOS Monitor Session (SPAN) parser using JSON output.

Parser:
    ShowMonitorSession — ``show monitor-session``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowMonitorSessionSchema(MetaParser):
    schema = {
        "sessions": {
            Any(): {  # session name
                "name": str,
                Optional("enabled"): bool,
                Optional("source-interfaces"): {
                    Any(): {
                        "name": str,
                        Optional("direction"): str,
                    }
                },
                Optional("destination"): str,
            }
        }
    }


class ShowMonitorSession(ShowMonitorSessionSchema):
    """Parser for monitor session (SPAN) state."""

    cli_command = "show monitor-session"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show monitor-session | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowMonitorSession: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ms = data.get("arcos-monitor-session:monitor-session", {})
        if not ms:
            ms = data.get("monitor-session", {})

        sessions_list = ms.get("session", ms.get("sessions", {}).get("session", []))
        if not sessions_list:
            raise SchemaEmptyParserError("No monitor session data found")

        if isinstance(sessions_list, dict):
            sessions_list = [sessions_list]

        result = {"sessions": {}}

        for sess in sessions_list:
            state = sess.get("state", sess.get("config", sess))
            sess_name = state.get("session-name", sess.get("session-name", ""))
            if not sess_name:
                continue

            entry = {"name": sess_name}

            if "enable" in state:
                entry["enabled"] = state["enable"]

            # Source interfaces
            sources = sess.get("source", sess.get("sources", {}).get("source", []))
            if sources:
                if isinstance(sources, dict):
                    sources = [sources]
                entry["source-interfaces"] = {}
                for src in sources:
                    src_state = src.get("state", src.get("config", src))
                    src_name = src_state.get("interface", src.get("interface", ""))
                    if src_name:
                        src_entry = {"name": src_name}
                        direction = src_state.get("direction", "")
                        if direction:
                            if ":" in direction:
                                direction = direction.split(":")[-1]
                            src_entry["direction"] = direction
                        entry["source-interfaces"][src_name] = src_entry

            # Destination
            dest = sess.get("destination", {})
            if dest:
                dest_state = dest.get("state", dest.get("config", dest))
                dest_intf = dest_state.get("interface", "")
                if dest_intf:
                    entry["destination"] = dest_intf
                elif dest_state.get("cpu"):
                    entry["destination"] = "cpu"

            result["sessions"][sess_name] = entry

        if not result["sessions"]:
            raise SchemaEmptyParserError("No monitor session data found")

        return result
