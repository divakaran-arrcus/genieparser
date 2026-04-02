"""ArcOS OSPFv3 parsers using JSON output.

Parsers:

1. ShowOspfv3Global — ``show network-instance default protocol OSPF3 default global state``
2. ShowOspfv3Neighbor — ``show network-instance default protocol OSPF3 default area <area> interface * neighbor``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


def _navigate_to_ospfv3(parsed: Dict) -> Dict:
    """Navigate to the OSPFv3 container.

    Tries ``arcos-ospf:ospfv3`` first (expected), then falls back
    to ``ospfv3`` in case the namespace prefix is stripped.
    """
    data = parsed.get("data", {})
    ni_container = data.get("openconfig-network-instance:network-instances", {})
    ni_list = ni_container.get("network-instance", [])
    if not ni_list:
        return {}
    ni = ni_list[0]
    protocols = ni.get("protocols", {}).get("protocol", [])
    for p in protocols:
        if "arcos-ospf:ospfv3" in p:
            return p["arcos-ospf:ospfv3"]
        if "ospfv3" in p:
            return p["ospfv3"]
    return {}


# =====================================================================
# ShowOspfv3Global
# =====================================================================

class ShowOspfv3GlobalSchema(MetaParser):
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


class ShowOspfv3Global(ShowOspfv3GlobalSchema):
    """Parser for OSPFv3 global state."""

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} global state"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"global state | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)
        state = ospfv3.get("global", {}).get("state", {})

        if not state:
            raise SchemaEmptyParserError("No OSPFv3 global state found")

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
# ShowOspfv3Neighbor
# =====================================================================

class ShowOspfv3NeighborSchema(MetaParser):
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


class ShowOspfv3Neighbor(ShowOspfv3NeighborSchema):
    """Parser for OSPFv3 neighbors (per-area)."""

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} "
        "area {area} interface * neighbor"
    )

    def cli(self, ni="default", instance="default", area="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"area {area} interface * neighbor | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        areas_container = ospfv3.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPFv3 neighbor data found")

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
            raise SchemaEmptyParserError("No OSPFv3 neighbors found")

        return result
