"""ArcOS SNMP parser using JSON output.

Parser:
    ShowSnmpServer — ``show system snmp-server enable``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowSnmpServerSchema(MetaParser):
    schema = {
        "enabled": bool,
        Optional("active"): bool,
    }


class ShowSnmpServer(ShowSnmpServerSchema):
    """Parser for SNMP server enable state."""

    cli_command = "show system snmp-server enable"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show system snmp-server enable | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSnmpServer: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        sys_data = data.get("openconfig-system:system", {})
        if not sys_data:
            sys_data = data.get("system", {})

        snmp = sys_data.get("arcos-snmp:snmp-server", {})
        if not snmp:
            snmp = sys_data.get("snmp-server", {})

        config = snmp.get("config", snmp.get("state", {}))
        if not config:
            raise SchemaEmptyParserError("No SNMP server data found")

        result = {
            "enabled": config.get("enable", False),
        }

        if "active" in config:
            result["active"] = config["active"]

        return result
