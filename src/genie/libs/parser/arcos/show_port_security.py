"""ArcOS Port Security parser using JSON output.

Parser:
    ShowPortSecurity — ``show port-security``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowPortSecuritySchema(MetaParser):
    schema = {
        Optional("profiles"): {
            Any(): {
                "name": str,
                Optional("limit"): int,
                Optional("sticky"): bool,
                Optional("violation-policy"): str,
            }
        },
        Optional("interfaces"): {
            Any(): {
                "name": str,
                Optional("enabled"): bool,
                Optional("profile"): str,
                Optional("violation-count"): int,
                Optional("learned-mac-count"): int,
            }
        },
    }


class ShowPortSecurity(ShowPortSecuritySchema):
    """Parser for port-security state."""

    cli_command = "show port-security"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show port-security | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowPortSecurity: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ps = data.get("arcos-port-security:port-security", {})
        if not ps:
            ps = data.get("port-security", {})

        if not ps:
            raise SchemaEmptyParserError("No port-security data found")

        result = {}

        profiles = ps.get("profile", [])
        if profiles:
            if isinstance(profiles, dict):
                profiles = [profiles]
            result["profiles"] = {}
            for p in profiles:
                name = p.get("name", p.get("profile-name", ""))
                if not name:
                    continue
                config = p.get("config", p.get("state", p))
                entry = {"name": name}
                if "limit" in config:
                    entry["limit"] = config["limit"]
                if "sticky" in config:
                    entry["sticky"] = config["sticky"]
                vp = config.get("violation-policy", "")
                if vp:
                    entry["violation-policy"] = vp
                result["profiles"][name] = entry

        interfaces = ps.get("interface", ps.get("statistics", {}).get("interface", []))
        if interfaces:
            if isinstance(interfaces, dict):
                interfaces = [interfaces]
            result["interfaces"] = {}
            for intf in interfaces:
                name = intf.get("name", intf.get("port-name", ""))
                if not name:
                    continue
                state = intf.get("state", intf)
                entry = {"name": name}
                if "security-enable" in state or "enable" in state:
                    entry["enabled"] = state.get("security-enable", state.get("enable", False))
                if "profile" in state:
                    entry["profile"] = state["profile"]
                if "violation-count" in state:
                    entry["violation-count"] = state["violation-count"]
                if "learned-mac-hit-count" in state:
                    entry["learned-mac-count"] = state["learned-mac-hit-count"]
                result["interfaces"][name] = entry

        if not result:
            raise SchemaEmptyParserError("No port-security data found")

        return result
