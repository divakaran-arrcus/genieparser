"""ArcOS EVPN MPLS parsers using JSON output.

Parsers:
1. ShowEvpnState — ``show evpn state router-ip-selected``
2. ShowEvpnEsiInfo — ``show evpn esi-info esi``
3. ShowL2ribMacEntries — ``show network-instance <ni> l2rib mac-entries``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


# =====================================================================
# ShowEvpnState
# =====================================================================

class ShowEvpnStateSchema(MetaParser):
    schema = {
        Optional("router-ip-selected"): str,
    }


class ShowEvpnState(ShowEvpnStateSchema):
    """Parser for EVPN router-IP state."""

    cli_command = "show evpn state router-ip-selected"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show evpn state router-ip-selected | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        evpn = data.get("arcos-evpn:evpn", data.get("evpn", {}))
        state = evpn.get("state", evpn)

        if not state:
            raise SchemaEmptyParserError("No EVPN state data found")

        result = {}
        rip = state.get("router-ip-selected", state.get("router-ip"))
        if rip:
            result["router-ip-selected"] = rip
        else:
            raise SchemaEmptyParserError("No EVPN router-ip-selected found")

        return result


# =====================================================================
# ShowEvpnEsiInfo
# =====================================================================

class ShowEvpnEsiInfoSchema(MetaParser):
    schema = {
        Optional("esi-entries"): {
            Any(): {  # ESI value as key
                "esi": str,
                Optional("designated-forwarder"): bool,
                Optional("local"): bool,
                Optional("interface"): str,
            }
        }
    }


class ShowEvpnEsiInfo(ShowEvpnEsiInfoSchema):
    """Parser for EVPN ESI information."""

    cli_command = "show evpn esi-info esi"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show evpn esi-info esi | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        evpn = data.get("arcos-evpn:evpn", data.get("evpn", {}))
        esi_info = evpn.get("esi-info", {})
        esi_list = esi_info.get("esi", esi_info.get("esi-entry", []))

        if not esi_list:
            raise SchemaEmptyParserError("No EVPN ESI data found")

        if isinstance(esi_list, dict):
            esi_list = [esi_list]

        result = {"esi-entries": {}}

        for esi_entry in esi_list:
            state = esi_entry.get("state", esi_entry)
            esi_val = state.get("esi", esi_entry.get("esi", ""))
            if not esi_val:
                continue

            entry = {"esi": esi_val}
            if "designated-forwarder" in state:
                entry["designated-forwarder"] = state["designated-forwarder"]
            if "local" in state:
                entry["local"] = state["local"]
            if "interface" in state:
                entry["interface"] = state["interface"]

            result["esi-entries"][esi_val] = entry

        if not result["esi-entries"]:
            raise SchemaEmptyParserError("No EVPN ESI entries found")

        return result


# =====================================================================
# ShowL2ribMacEntries
# =====================================================================

class ShowL2ribMacEntriesSchema(MetaParser):
    schema = {
        Optional("mac-entries"): {
            Any(): {  # MAC address as key
                "mac-address": str,
                Optional("origin"): str,
                Optional("esi"): str,
                Optional("next-hop"): str,
                Optional("label"): int,
            }
        }
    }


class ShowL2ribMacEntries(ShowL2ribMacEntriesSchema):
    """Parser for L2RIB MAC entries."""

    cli_command = "show network-instance {ni} l2rib mac-entries"

    def cli(self, ni="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show network-instance {ni} l2rib mac-entries | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        ni_container = data.get("openconfig-network-instance:network-instances",
                                data.get("network-instances", {}))
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            raise SchemaEmptyParserError("No L2RIB MAC entries found")

        result = {"mac-entries": {}}

        for ni_entry in ni_list:
            l2rib = ni_entry.get("arcos-l2rib:l2rib", ni_entry.get("l2rib", {}))
            mac_entries = l2rib.get("mac-entries", {}).get("mac-entry",
                          l2rib.get("mac-entries", []))

            if isinstance(mac_entries, dict):
                mac_entries = [mac_entries]

            for mac in mac_entries:
                state = mac.get("state", mac)
                mac_addr = state.get("mac-address", mac.get("mac-address", ""))
                if not mac_addr:
                    continue

                entry = {"mac-address": mac_addr}
                if "origin" in state:
                    entry["origin"] = state["origin"]
                if "esi" in state:
                    entry["esi"] = state["esi"]
                if "next-hop" in state:
                    entry["next-hop"] = state["next-hop"]
                if "label" in state:
                    entry["label"] = state["label"]

                result["mac-entries"][mac_addr] = entry

        if not result["mac-entries"]:
            raise SchemaEmptyParserError("No L2RIB MAC entries found")

        return result
