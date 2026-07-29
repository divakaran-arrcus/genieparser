"""ArcOS LLDP parsers using OpenConfig JSON output.

Two parsers:

1. ShowLldpState — ``show lldp state | display json | nomore``
   Returns global LLDP state: hello-timer, system-name, system-description,
   and counters.

2. ShowLldpInterface — ``show lldp interface {interface} | display json | nomore``
   Returns per-interface LLDP state including counters, mode, and neighbor
   information (system-name, chassis-id, port-id, management-address, etc.).
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


# =====================================================================
# ShowLldpState
# =====================================================================

class ShowLldpStateSchema(MetaParser):
    """Schema for ``show lldp state`` output."""

    schema = {
        "hello-timer": str,
        "system-name": str,
        "system-description": str,
        Optional("counters"): {
            Optional("frame-in"): str,
            Optional("frame-out"): str,
            Optional("frame-error-in"): str,
            Optional("frame-discard"): str,
            Optional("tlv-discard"): str,
            Optional("tlv-unknown"): str,
        },
    }


class ShowLldpState(ShowLldpStateSchema):
    """Parser for ArcOS ``show lldp state`` (JSON format).

    Parses OpenConfig JSON::

        data["openconfig-lldp:lldp"]["state"]
    """

    cli_command = "show lldp state"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowLldpState: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        lldp = data.get("openconfig-lldp:lldp", {})
        state = lldp.get("state", {})

        if not state:
            raise SchemaEmptyParserError("No LLDP state data found")

        result = {
            "hello-timer": state.get("hello-timer", "30"),
            "system-name": state.get("system-name", ""),
            "system-description": state.get("system-description", ""),
        }

        counters = state.get("counters")
        if counters:
            result["counters"] = {}
            for key in [
                "frame-in", "frame-out", "frame-error-in",
                "frame-discard", "tlv-discard", "tlv-unknown",
            ]:
                if key in counters:
                    result["counters"][key] = counters[key]

        return result


# =====================================================================
# ShowLldpInterface
# =====================================================================

class ShowLldpInterfaceSchema(MetaParser):
    """Schema for ``show lldp interface`` output."""

    schema = {
        "interfaces": {
            Any(): {  # interface name
                "name": str,
                Optional("enabled"): bool,
                Optional("mode"): str,
                Optional("counters"): {
                    Optional("frame-in"): str,
                    Optional("frame-out"): str,
                    Optional("frame-error-in"): str,
                    Optional("frame-discard"): str,
                    Optional("tlv-discard"): str,
                    Optional("tlv-unknown"): str,
                    Optional("frame-error-out"): str,
                },
                Optional("neighbors"): {
                    Any(): {  # neighbor id
                        "id": str,
                        Optional("system-name"): str,
                        Optional("system-description"): str,
                        Optional("chassis-id"): str,
                        Optional("chassis-id-type"): str,
                        Optional("age"): str,
                        Optional("port-id"): str,
                        Optional("port-id-type"): str,
                        Optional("port-description"): str,
                        Optional("management-address"): str,
                        Optional("management-address-type"): str,
                        Optional("management-address-ipv6"): str,
                        Optional("management-address-ipv6-type"): str,
                        Optional("capabilities"): {
                            Any(): {  # capability name
                                "name": str,
                                "enabled": bool,
                            }
                        },
                    }
                },
            }
        }
    }


class ShowLldpInterface(ShowLldpInterfaceSchema):
    """Parser for ArcOS ``show lldp interface`` (JSON format).

    Parses OpenConfig JSON::

        data["openconfig-lldp:lldp"]["interfaces"]["interface"]

    Supports wildcard (``*``) or specific interface name.
    """

    cli_command = [
        "show lldp interface {interface}",
        "show lldp interface",
    ]

    def cli(
        self,
        interface: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show lldp interface {interface} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowLldpInterface: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        lldp = data.get("openconfig-lldp:lldp", {})
        interfaces_container = lldp.get("interfaces", {})
        interface_list = interfaces_container.get("interface", [])

        if not interface_list:
            raise SchemaEmptyParserError("No LLDP interface data found")

        result = {"interfaces": {}}

        for intf in interface_list:
            intf_name = intf.get("name")
            if not intf_name:
                continue

            intf_state = intf.get("state", {})
            intf_entry = {
                "name": intf_name,
            }

            if "enabled" in intf_state:
                intf_entry["enabled"] = intf_state["enabled"]

            if "mode" in intf_state:
                intf_entry["mode"] = intf_state["mode"]

            # Counters
            counters = intf_state.get("counters")
            if counters:
                intf_entry["counters"] = {}
                for key in [
                    "frame-in", "frame-out", "frame-error-in",
                    "frame-discard", "tlv-discard", "tlv-unknown",
                    "frame-error-out",
                ]:
                    if key in counters:
                        intf_entry["counters"][key] = counters[key]

            # Neighbors
            neighbors_container = intf.get("neighbors", {})
            neighbor_list = neighbors_container.get("neighbor", [])
            if neighbor_list:
                intf_entry["neighbors"] = {}
                for nbr in neighbor_list:
                    nbr_id = nbr.get("id")
                    if not nbr_id:
                        continue

                    nbr_state = nbr.get("state", {})
                    nbr_entry = {
                        "id": nbr_id,
                    }

                    for key in [
                        "system-name", "system-description",
                        "chassis-id", "chassis-id-type",
                        "age", "port-id", "port-id-type",
                        "port-description",
                        "management-address", "management-address-type",
                    ]:
                        if key in nbr_state:
                            nbr_entry[key] = nbr_state[key]

                    # IPv6 management address (arcOS augment)
                    ipv6_addr = nbr_state.get(
                        "arcos-openconfig-lldp-augments:management-address"
                    )
                    if ipv6_addr:
                        nbr_entry["management-address-ipv6"] = ipv6_addr

                    ipv6_type = nbr_state.get(
                        "arcos-openconfig-lldp-augments:management-address-type"
                    )
                    if ipv6_type:
                        nbr_entry["management-address-ipv6-type"] = ipv6_type

                    # Capabilities
                    caps_container = nbr.get("capabilities", {})
                    caps_list = caps_container.get("capability", [])
                    if caps_list:
                        nbr_entry["capabilities"] = {}
                        for cap in caps_list:
                            cap_name_raw = cap.get("name", "")
                            # Strip OC prefix: "openconfig-lldp-types:ROUTER" → "ROUTER"
                            cap_name = cap_name_raw.split(":")[-1] if ":" in cap_name_raw else cap_name_raw
                            cap_state = cap.get("state", {})
                            nbr_entry["capabilities"][cap_name] = {
                                "name": cap_name,
                                "enabled": cap_state.get("enabled", False),
                            }

                    intf_entry["neighbors"][nbr_id] = nbr_entry

            result["interfaces"][intf_name] = intf_entry

        return result
