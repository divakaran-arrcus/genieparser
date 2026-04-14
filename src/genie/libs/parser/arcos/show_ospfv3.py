"""ArcOS OSPFv3 parsers using JSON output.

Parsers:

1. ShowOspfv3Global — ``show network-instance default protocol OSPF3 default global state``
2. ShowOspfv3Neighbor — ``show network-instance default protocol OSPF3 default area <area> interface * neighbor``
3. ShowOspfv3RunningConfig — ``show running-config network-instance {ni} protocol OSPF3 {instance}``
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


# =====================================================================
# Prefix stripping for OSPF types
# =====================================================================

_OSPFV3_VALUE_PREFIXES = [
    "arcos-ospf-types:",
    "openconfig-policy-types:",
]


def _strip_ospfv3_value(value: str) -> str:
    """Strip known OSPF namespace prefixes from a value string."""
    if not isinstance(value, str):
        return value
    for prefix in _OSPFV3_VALUE_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


# =====================================================================
# ShowOspfv3RunningConfig
# =====================================================================

class ShowOspfv3RunningConfigSchema(MetaParser):
    """Schema for OSPFv3 running configuration."""

    schema = {
        Optional("global"): {
            Optional("router-id"): str,
        },
        Optional("areas"): {
            Any(): {  # area ID as str
                Optional("identifier"): int,
                Optional("area-type"): str,
                Optional("stub-default-cost"): int,
                Optional("interfaces"): {
                    Any(): {  # interface name
                        Optional("id"): str,
                        Optional("network-type"): str,
                        Optional("hello-interval"): int,
                        Optional("dead-interval"): int,
                    }
                },
            }
        },
    }


class ShowOspfv3RunningConfig(ShowOspfv3RunningConfigSchema):
    """Parser for OSPFv3 running configuration.

    Command::

        show running-config network-instance {ni} protocol OSPF3 {instance}
    """

    cli_command = (
        "show running-config network-instance {ni} protocol OSPF3 {instance}"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show running-config network-instance {ni} "
                f"protocol OSPF3 {instance} | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        if not ospfv3:
            raise SchemaEmptyParserError(
                "No OSPFv3 running configuration found"
            )

        result: Dict[str, TypeAny] = {}

        # Global config (flatten config{})
        global_data = ospfv3.get("global", {})
        if global_data:
            global_entry: Dict[str, TypeAny] = {}

            cfg = global_data.get("config", {})
            rid = cfg.get("router-id")
            if rid:
                global_entry["router-id"] = rid

            if global_entry:
                result["global"] = global_entry

        # Areas (flatten config{} at area and interface levels)
        areas_container = ospfv3.get("areas", {})
        area_list = areas_container.get("area", [])

        if area_list:
            areas_dict: Dict[str, TypeAny] = {}

            for area_entry in area_list:
                area_id = area_entry.get("identifier", 0)
                area_cfg = area_entry.get("config", {})

                entry: Dict[str, TypeAny] = {}

                if "identifier" in area_cfg:
                    entry["identifier"] = area_cfg["identifier"]

                area_type = area_cfg.get("area-type")
                if area_type:
                    entry["area-type"] = area_type

                stub_cost = area_cfg.get("stub-default-cost")
                if stub_cost is not None:
                    entry["stub-default-cost"] = stub_cost

                # Interfaces
                intfs = area_entry.get("interfaces", {}).get(
                    "interface", []
                )
                if intfs:
                    intfs_dict: Dict[str, TypeAny] = {}
                    for intf in intfs:
                        intf_id = intf.get("id")
                        if not intf_id:
                            continue

                        intf_entry: Dict[str, TypeAny] = {}
                        intf_cfg = intf.get("config", {})

                        if "id" in intf_cfg:
                            intf_entry["id"] = intf_cfg["id"]

                        net_type = intf_cfg.get("network-type")
                        if net_type:
                            intf_entry["network-type"] = (
                                _strip_ospfv3_value(net_type)
                            )

                        timers_cfg = intf.get("timers", {}).get(
                            "config", {}
                        )
                        for tk in ("hello-interval", "dead-interval"):
                            if tk in timers_cfg:
                                intf_entry[tk] = timers_cfg[tk]

                        if intf_entry:
                            intfs_dict[intf_id] = intf_entry

                    if intfs_dict:
                        entry["interfaces"] = intfs_dict

                if entry:
                    areas_dict[str(area_id)] = entry

            if areas_dict:
                result["areas"] = areas_dict

        if not result:
            raise SchemaEmptyParserError(
                "No OSPFv3 running configuration found"
            )

        return result
