"""show_vrrp.py

ArcOS parsers for the following show commands:
    * show interface {interface} subinterface {sub_id} {af} address {address} vrrp
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowVrrpSchema(MetaParser):
    """Schema for VRRP show output."""

    schema = {
        "vrrp-groups": {
            Any(): {  # "interface:sub:af:address:vrid" key
                "interface": str,
                "sub-id": int,
                "af": str,
                "address": str,
                "virtual-router-id": int,
                Optional("virtual-address"): list,
                Optional("priority"): int,
                Optional("current-priority"): int,
                Optional("preempt"): bool,
                Optional("accept-mode"): bool,
                Optional("advertisement-interval"): int,
                Optional("vrrp-version"): str,
                Optional("virtual-router-mode"): str,
                Optional("virtual-mac-address"): str,
                Optional("advertisement-sent"): str,
                Optional("advertisement-received"): str,
                Optional("advertisement-dropped"): str,
            }
        }
    }


class ShowVrrp(ShowVrrpSchema):
    """Parser for ArcOS VRRP show command (JSON format).

    Command: show interface <intf> subinterface <sub> <af> address <ip> vrrp

    Returns VRRP group state including virtual-router-id,
    virtual-addresses, priority, mode, and counters.
    """

    cli_command = (
        "show interface {interface} subinterface {sub_id} "
        "{af} address {address} vrrp"
    )

    def cli(
        self,
        interface: str = "*",
        sub_id: int = 0,
        af: str = "ipv4",
        address: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show interface {interface} subinterface {sub_id} "
                f"{af} address {address} vrrp | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowVrrp: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        intf_container = data.get("openconfig-interfaces:interfaces", {})
        intf_list = intf_container.get("interface", [])

        if not intf_list:
            raise SchemaEmptyParserError("No VRRP data found")

        result = {"vrrp-groups": {}}

        for intf in intf_list:
            intf_name = intf.get("name")
            if not intf_name:
                continue

            subintfs = intf.get("subinterfaces", {}).get("subinterface", [])
            for subintf in subintfs:
                sub_idx = subintf.get("index", 0)

                # Check both ipv4 and ipv6
                for af_key, af_name in [
                    ("openconfig-if-ip:ipv4", "ipv4"),
                    ("openconfig-if-ip:ipv6", "ipv6"),
                ]:
                    af_data = subintf.get(af_key, {})
                    addresses = af_data.get("addresses", {}).get("address", [])

                    for addr_entry in addresses:
                        ip = addr_entry.get("ip")
                        if not ip:
                            continue

                        vrrp_container = addr_entry.get("vrrp", {})
                        vrrp_groups = vrrp_container.get("vrrp-group", [])

                        for grp in vrrp_groups:
                            vrid = grp.get("virtual-router-id")
                            if vrid is None:
                                continue

                            state = grp.get("state", {})
                            key = f"{intf_name}:{sub_idx}:{af_name}:{ip}:{vrid}"

                            entry = {
                                "interface": intf_name,
                                "sub-id": sub_idx,
                                "af": af_name,
                                "address": ip,
                                "virtual-router-id": vrid,
                            }

                            if "virtual-address" in state:
                                entry["virtual-address"] = state["virtual-address"]

                            for k in ("priority", "current-priority",
                                      "advertisement-interval"):
                                if k in state:
                                    entry[k] = state[k]

                            for k in ("preempt", "accept-mode"):
                                if k in state:
                                    entry[k] = state[k]

                            # Augmented fields
                            ver = state.get(
                                "arcos-openconfig-if-ip-augments:vrrp-version"
                            )
                            if ver:
                                entry["vrrp-version"] = ver

                            mode = state.get(
                                "arcos-openconfig-if-ip-augments:virtual-router-mode"
                            )
                            if mode:
                                entry["virtual-router-mode"] = mode

                            mac = state.get(
                                "arcos-openconfig-if-ip-augments:virtual-mac-address"
                            )
                            if mac:
                                entry["virtual-mac-address"] = mac

                            for counter in ("advertisement-sent",
                                            "advertisement-received",
                                            "advertisement-dropped"):
                                aug_key = f"arcos-openconfig-if-ip-augments:{counter}"
                                if aug_key in state:
                                    entry[counter] = state[aug_key]

                            result["vrrp-groups"][key] = entry

        if not result["vrrp-groups"]:
            raise SchemaEmptyParserError("No VRRP groups found")

        return result
