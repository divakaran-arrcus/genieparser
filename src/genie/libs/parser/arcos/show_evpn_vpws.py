"""show_evpn_vpws.py

ArcOS parsers for the following show commands:
    * show network-instance default protocol BGP default global afi-safi L2VPN_EVPN vpws
    * show network-instance {ni} l2rib vpws-evi-entries
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import OPENCONFIG_NETWORK_INSTANCES
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowEvpnVpwsSchema(MetaParser):
    schema = {
        Optional("vpws-services"): {
            Any(): {
                "network-instance": str,
                Optional("evi"): int,
                Optional("local-service-id"): int,
                Optional("remote-service-id"): int,
                Optional("control-word"): bool,
                Optional("link-loss-forwarding"): bool,
                Optional("oper-status"): str,
            }
        }
    }


class ShowEvpnVpws(ShowEvpnVpwsSchema):
    """Parser for EVPN VPWS services summary."""

    cli_command = (
        "show network-instance default protocol BGP default "
        "global afi-safi L2VPN_EVPN vpws"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowEvpnVpws: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            raise SchemaEmptyParserError("No VPWS data found")

        result = {"vpws-services": {}}

        for ni in ni_list:
            protocols = ni.get("protocols", {}).get("protocol", [])
            for proto in protocols:
                ident = proto.get("identifier", "")
                if "BGP" not in ident:
                    continue
                bgp = proto.get("bgp", {})
                global_data = bgp.get("global", {})
                afi_safis = global_data.get("afi-safis", {}).get("afi-safi", [])

                for af in afi_safis:
                    vpws = af.get("vpws", af.get("arcos-openconfig-bgp-augments:vpws", {}))
                    services = vpws.get("service", vpws.get("services", []))
                    if isinstance(services, dict):
                        services = [services]

                    for svc in services:
                        state = svc.get("state", svc)
                        ni_name = state.get("network-instance", "")
                        if not ni_name:
                            continue
                        entry = {"network-instance": ni_name}
                        if "evi" in state:
                            entry["evi"] = state["evi"]
                        if "local-service-id" in state:
                            entry["local-service-id"] = state["local-service-id"]
                        if "remote-service-id" in state:
                            entry["remote-service-id"] = state["remote-service-id"]
                        if "control-word" in state:
                            entry["control-word"] = state["control-word"]
                        if "link-loss-forwarding" in state:
                            entry["link-loss-forwarding"] = state["link-loss-forwarding"]
                        if "oper-status" in state:
                            entry["oper-status"] = state["oper-status"]

                        result["vpws-services"][ni_name] = entry

        if not result["vpws-services"]:
            raise SchemaEmptyParserError("No VPWS services found")

        return result


class ShowL2ribVpwsEviEntriesSchema(MetaParser):
    schema = {
        Optional("vpws-evi-entries"): {
            Any(): {
                Optional("evi"): int,
                Optional("ingress-label"): int,
                Optional("esi"): str,
                Optional("control-word"): bool,
            }
        }
    }


class ShowL2ribVpwsEviEntries(ShowL2ribVpwsEviEntriesSchema):
    """Parser for L2RIB VPWS EVI entries."""

    cli_command = "show network-instance {ni} l2rib vpws-evi-entries"

    def cli(self, ni="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show network-instance {ni} l2rib vpws-evi-entries | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowL2ribVpwsEviEntries: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES,
                                data.get("network-instances", {}))
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            raise SchemaEmptyParserError("No VPWS EVI entries found")

        result = {"vpws-evi-entries": {}}

        for ni_entry in ni_list:
            ni_name = ni_entry.get("name", "")
            l2rib = ni_entry.get("arcos-l2rib:l2rib", ni_entry.get("l2rib", {}))
            entries = l2rib.get("vpws-evi-entries", {}).get("vpws-evi-entry", [])
            if isinstance(entries, dict):
                entries = [entries]

            for e in entries:
                state = e.get("state", e)
                evi = state.get("evi", 0)
                key = f"{ni_name}:{evi}"
                entry = {}
                if "evi" in state:
                    entry["evi"] = state["evi"]
                if "ingress-label" in state:
                    entry["ingress-label"] = state["ingress-label"]
                if "esi" in state:
                    entry["esi"] = state["esi"]
                if "control-word" in state:
                    entry["control-word"] = state["control-word"]
                result["vpws-evi-entries"][key] = entry

        if not result["vpws-evi-entries"]:
            raise SchemaEmptyParserError("No VPWS EVI entries found")

        return result
