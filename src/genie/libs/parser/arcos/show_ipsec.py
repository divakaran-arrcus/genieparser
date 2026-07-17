"""ArcOS IPsec parser using JSON output.

Parser:
    ShowIpsecConnEntry — ``show ipsec-ike conn-entry <name>``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowIpsecConnEntrySchema(MetaParser):
    schema = {
        "connections": {
            Any(): {  # connection name
                "name": str,
                Optional("version"): str,
                Optional("autostartup"): str,
                Optional("authalg"): str,
                Optional("encalg"): str,
                Optional("dh-group"): int,
                Optional("rekey-time"): int,
                Optional("spd-entries"): {
                    Any(): {
                        "name": str,
                        Optional("local-subnets"): list,
                        Optional("remote-subnets"): list,
                    }
                },
            }
        }
    }


class ShowIpsecConnEntry(ShowIpsecConnEntrySchema):
    """Parser for IPsec IKE connection entry."""

    cli_command = "show ipsec-ike conn-entry {name}"

    def cli(self, name="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show ipsec-ike conn-entry {name} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowIpsecConnEntry: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ike = data.get("arcos-ipsec-ike:ipsec-ike", {})
        if not ike:
            ike = data.get("ipsec-ike", {})

        conn_list = ike.get("conn-entry", [])
        if not conn_list:
            raise SchemaEmptyParserError("No IPsec conn-entry data found")

        if isinstance(conn_list, dict):
            conn_list = [conn_list]

        result = {"connections": {}}

        for conn in conn_list:
            conn_name = conn.get("name", "")
            if not conn_name:
                continue

            config = conn.get("config", conn.get("state", conn))
            entry = {"name": conn_name}

            if "version" in config:
                entry["version"] = config["version"]
            if "autostartup" in config:
                entry["autostartup"] = config["autostartup"]
            if "authalg" in config:
                val = config["authalg"]
                entry["authalg"] = val[0] if isinstance(val, list) else str(val)
            if "encalg" in config:
                val = config["encalg"]
                entry["encalg"] = val[0] if isinstance(val, list) else str(val)
            if "dh-group" in config:
                entry["dh-group"] = config["dh-group"]

            lifetime = config.get("ike-sa-lifetime-soft", {})
            if "rekey-time" in lifetime:
                entry["rekey-time"] = lifetime["rekey-time"]

            spd_list = conn.get("spd", {}).get("spd-entry", [])
            if spd_list:
                if isinstance(spd_list, dict):
                    spd_list = [spd_list]
                entry["spd-entries"] = {}
                for spd in spd_list:
                    spd_name = spd.get("name", "")
                    if not spd_name:
                        continue
                    spd_config = spd.get("ipsec-policy-config", {})
                    ts = spd_config.get("traffic-selector", {})
                    spd_entry = {"name": spd_name}
                    if "local-subnets" in ts:
                        val = ts["local-subnets"]
                        spd_entry["local-subnets"] = val if isinstance(val, list) else [val]
                    if "remote-subnets" in ts:
                        val = ts["remote-subnets"]
                        spd_entry["remote-subnets"] = val if isinstance(val, list) else [val]
                    entry["spd-entries"][spd_name] = spd_entry

            result["connections"][conn_name] = entry

        if not result["connections"]:
            raise SchemaEmptyParserError("No IPsec conn-entry data found")

        return result
