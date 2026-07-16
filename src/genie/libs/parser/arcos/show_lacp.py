"""ArcOS LACP parser using OpenConfig JSON output.

Parser:

ShowLacpInterface
    ``show lacp interface {bond} | display json | nomore``

Returns per-bond LACP state (interval) and per-member state
(synchronization, collecting, distributing, etc.).
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowLacpInterfaceSchema(MetaParser):
    """Schema for ``show lacp interface`` output."""

    schema = {
        "interfaces": {
            Any(): {  # bond name
                "name": str,
                Optional("interval"): str,
                Optional("members"): {
                    Any(): {  # member interface name
                        "interface": str,
                        Optional("timeout"): str,
                        Optional("synchronization"): str,
                        Optional("aggregatable"): bool,
                        Optional("collecting"): bool,
                        Optional("distributing"): bool,
                    }
                },
            }
        }
    }


class ShowLacpInterface(ShowLacpInterfaceSchema):
    """Parser for ArcOS ``show lacp interface`` (JSON format).

    Parses OpenConfig JSON::

        data["openconfig-lacp:lacp"]["interfaces"]["interface"]

    Supports specific bond (``bond1``) or wildcard (``*``).
    """

    cli_command = [
        "show lacp interface {bond}",
        "show lacp interface",
    ]

    def cli(
        self,
        bond: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show lacp interface {bond} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowLacpInterface: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        lacp = data.get("openconfig-lacp:lacp", {})
        intf_container = lacp.get("interfaces", {})
        intf_list = intf_container.get("interface", [])

        if not intf_list:
            raise SchemaEmptyParserError("No LACP interface data found")

        result = {"interfaces": {}}

        for intf in intf_list:
            bond_name = intf.get("name")
            if not bond_name:
                continue

            state = intf.get("state", {})
            entry = {
                "name": bond_name,
            }

            if "interval" in state:
                entry["interval"] = state["interval"]

            # Members
            members_container = intf.get("members", {})
            member_list = members_container.get("member", [])
            if member_list:
                entry["members"] = {}
                for member in member_list:
                    member_intf = member.get("interface")
                    if not member_intf:
                        continue

                    member_state = member.get("state", {})
                    member_entry = {
                        "interface": member_intf,
                    }

                    for key in (
                        "timeout", "synchronization",
                    ):
                        if key in member_state:
                            member_entry[key] = member_state[key]

                    for key in (
                        "aggregatable", "collecting", "distributing",
                    ):
                        if key in member_state:
                            member_entry[key] = member_state[key]

                    entry["members"][member_intf] = member_entry

            result["interfaces"][bond_name] = entry

        return result
