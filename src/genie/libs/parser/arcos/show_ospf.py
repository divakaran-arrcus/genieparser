"""ArcOS OSPFv2 parsers using JSON output.

Parsers:

1. ShowOspfGlobal — ``show network-instance default protocol OSPF default global state``
2. ShowOspfNeighbor — ``show network-instance default protocol OSPF default area <area> interface * neighbor``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


def _navigate_to_ospf(parsed: Dict) -> Dict:
    """Navigate to the OSPF container."""
    data = parsed.get("data", {})
    ni_container = data.get("openconfig-network-instance:network-instances", {})
    ni_list = ni_container.get("network-instance", [])
    if not ni_list:
        return {}
    ni = ni_list[0]
    protocols = ni.get("protocols", {}).get("protocol", [])
    for p in protocols:
        if "arcos-ospf:ospfv2" in p:
            return p["arcos-ospf:ospfv2"]
    return {}


# =====================================================================
# ShowOspfGlobal
# =====================================================================

class ShowOspfGlobalSchema(MetaParser):
    schema = {
        "router-id": str,
        Optional("log-adjacency-changes"): str,
        Optional("max-ecmp-paths"): int,
        Optional("abr-router"): bool,
        Optional("asbr-router"): bool,
        Optional("area-count"): int,
        Optional("neighbor-count"): int,
        Optional("full-neighbor-count"): int,
        Optional("up-interface-count"): int,
    }


class ShowOspfGlobal(ShowOspfGlobalSchema):
    """Parser for OSPF global state."""

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} global state"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"global state | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)
        state = ospf.get("global", {}).get("state", {})

        if not state:
            raise SchemaEmptyParserError("No OSPF global state found")

        result = {
            "router-id": state.get("router-id", ""),
        }

        for k in ("log-adjacency-changes", "max-ecmp-paths",
                   "abr-router", "asbr-router", "area-count",
                   "neighbor-count", "full-neighbor-count",
                   "up-interface-count"):
            if k in state:
                result[k] = state[k]

        return result


# =====================================================================
# ShowOspfNeighbor
# =====================================================================

class ShowOspfNeighborSchema(MetaParser):
    schema = {
        "neighbors": {
            Any(): {  # "area:interface:router-id" key
                "area": int,
                "interface": str,
                "neighbor-router-id": str,
                Optional("neighbor-ip-address"): str,
                Optional("adjacency-state"): str,
                Optional("priority"): int,
            }
        }
    }


class ShowOspfNeighbor(ShowOspfNeighborSchema):
    """Parser for OSPF neighbors (per-area)."""

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} "
        "area {area} interface * neighbor"
    )

    def cli(self, ni="default", instance="default", area="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"area {area} interface * neighbor | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        areas_container = ospf.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPF neighbor data found")

        result = {"neighbors": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            intfs = area_entry.get("interfaces", {}).get("interface", [])

            for intf in intfs:
                intf_id = intf.get("id")
                if not intf_id:
                    continue

                nbrs = intf.get("neighbors", {}).get("neighbor", [])
                for nbr in nbrs:
                    rid = nbr.get("neighbor-router-id")
                    if not rid:
                        continue

                    state = nbr.get("state", {})
                    key = f"{area_id}:{intf_id}:{rid}"

                    entry = {
                        "area": area_id,
                        "interface": intf_id,
                        "neighbor-router-id": rid,
                    }

                    if "neighbor-ip-address" in state:
                        entry["neighbor-ip-address"] = state["neighbor-ip-address"]

                    adj = state.get("adjacency-state", "")
                    if adj:
                        # Strip prefix: "arcos-ospf-types:NEIGHBOR_FULL" → "NEIGHBOR_FULL"
                        entry["adjacency-state"] = adj.split(":")[-1] if ":" in adj else adj

                    if "priority" in state:
                        entry["priority"] = state["priority"]

                    result["neighbors"][key] = entry

        if not result["neighbors"]:
            raise SchemaEmptyParserError("No OSPF neighbors found")

        return result
