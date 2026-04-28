"""ArcOS OSPFv3 parsers using JSON output.

Parsers:

1. ShowOspfv3Global — ``show network-instance default protocol OSPF3 default global state``
2. ShowOspfv3Neighbor — ``show network-instance default protocol OSPF3 default area <area> interface * neighbor``
3. ShowOspfv3RunningConfig — ``show running-config network-instance {ni} protocol OSPF3 {instance}``
4. ShowOspfv3Area — ``show network-instance default protocol OSPF3 default area <area> state``
5. ShowOspfv3Interface — ``show network-instance default protocol OSPF3 default area <area> interface state``
6. ShowOspfv3SpfThrottle — ``show network-instance default protocol OSPF3 default global spf throttle``
7. ShowOspfv3Lsdb — ``show network-instance default protocol OSPF3 default area <area> lsdb``
8. ShowOspfv3GlobalRib — ``show network-instance default protocol OSPF3 default global rib prefix``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
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
        Optional("route-preference"): {
            Optional("intra-area"): int,
            Optional("inter-area"): int,
            Optional("external"): int,
        },
        Optional("max-lsa"): {
            Optional("lsa-limit"): int,
            Optional("warning-threshold"): int,
            Optional("state"): str,
        },
        Optional("maintenance-mode"): {
            Optional("state"): str,
            Optional("trigger"): str,
        },
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
        global_data = ospfv3.get("global", {})
        state = global_data.get("state", {})

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

        # Optional sub-dicts. Try both layouts:
        #   global.{field}.state.* (nested OpenConfig)
        #   state.{field}.*        (flat under top-level state)
        for field, keys in (
            ("route-preference", ("intra-area", "inter-area", "external")),
            ("max-lsa", ("lsa-limit", "warning-threshold", "state")),
            ("maintenance-mode", ("state", "trigger")),
        ):
            src = (global_data.get(field, {}) or {}).get("state", {}) \
                or state.get(field, {}) or {}
            sub = {k: src[k] for k in keys if k in src}
            if sub:
                result[field] = sub

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


# =====================================================================
# ShowOspfv3Area
# =====================================================================

class ShowOspfv3AreaSchema(MetaParser):
    """Schema for OSPFv3 per-area operational state."""

    schema = {
        "areas": {
            Any(): {  # area ID as str
                Optional("identifier"): int,
                Optional("area-type"): str,
                Optional("advertise-summary-lsas"): bool,
                Optional("stub-default-cost"): int,
                Optional("configured-interface-count"): int,
                Optional("up-interface-count"): int,
                Optional("neighbor-count"): int,
                Optional("exchange-neighbor-count"): int,
                Optional("loading-neighbor-count"): int,
                Optional("full-neighbor-count"): int,
            }
        }
    }


class ShowOspfv3Area(ShowOspfv3AreaSchema):
    """Parser for OSPFv3 area state.

    Command::

        show network-instance {ni} protocol OSPF3 {instance} area {area} state
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} "
        "area {area} state"
    )

    def cli(self, ni: str = "default", instance: str = "default",
            area: str = "*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"area {area} state | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        areas_container = ospfv3.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPFv3 area data found")

        result: Dict[str, TypeAny] = {"areas": {}}
        for area_entry in area_list:
            area_id = area_entry.get("identifier")
            state = area_entry.get("state", {})
            if area_id is None or not state:
                continue

            entry: Dict[str, TypeAny] = {}
            for k in ("identifier", "area-type", "advertise-summary-lsas",
                      "stub-default-cost", "configured-interface-count",
                      "up-interface-count", "neighbor-count",
                      "exchange-neighbor-count", "loading-neighbor-count",
                      "full-neighbor-count"):
                if k in state:
                    val = state[k]
                    if k == "area-type":
                        val = _strip_ospfv3_value(val)
                    entry[k] = val

            if entry:
                result["areas"][str(area_id)] = entry

        if not result["areas"]:
            raise SchemaEmptyParserError("No OSPFv3 areas parsed")

        return result


# =====================================================================
# ShowOspfv3Interface
# =====================================================================

class ShowOspfv3InterfaceSchema(MetaParser):
    """Schema for OSPFv3 per-interface operational state."""

    schema = {
        "areas": {
            Any(): {  # area ID as str
                "interfaces": {
                    Any(): {  # interface name
                        Optional("id"): str,
                        Optional("network-type"): str,
                        Optional("priority"): int,
                        Optional("metric"): int,
                        Optional("passive"): bool,
                        Optional("ignore-mtu"): bool,
                        Optional("interface-up"): bool,
                        Optional("interface-state"): str,
                        Optional("local-ip-address"): str,
                        Optional("mtu"): int,
                        Optional("speed"): Or(str, int),
                        Optional("neighbor-count"): int,
                        Optional("exchange-neighbor-count"): int,
                        Optional("loading-neighbor-count"): int,
                        Optional("full-neighbor-count"): int,
                        # OSPFv3-specific fields
                        Optional("interface-id"): int,
                        Optional("instance-id"): int,
                    }
                }
            }
        }
    }


class ShowOspfv3Interface(ShowOspfv3InterfaceSchema):
    """Parser for OSPFv3 interface state.

    Command::

        show network-instance {ni} protocol OSPF3 {instance}
            area {area} interface state
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} "
        "area {area} interface state"
    )

    def cli(self, ni: str = "default", instance: str = "default",
            area: str = "*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"area {area} interface state | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        areas_container = ospfv3.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPFv3 interface data found")

        result: Dict[str, TypeAny] = {"areas": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            intfs = area_entry.get("interfaces", {}).get("interface", [])
            if not intfs:
                continue

            interfaces_dict: Dict[str, TypeAny] = {}

            for intf in intfs:
                intf_id = intf.get("id")
                if not intf_id:
                    continue

                state = intf.get("state", {})
                entry: Dict[str, TypeAny] = {}

                for k in ("id", "priority", "metric", "passive", "ignore-mtu",
                          "interface-up", "local-ip-address", "mtu", "speed",
                          "neighbor-count", "exchange-neighbor-count",
                          "loading-neighbor-count", "full-neighbor-count"):
                    if k in state:
                        entry[k] = state[k]

                # Strip namespace from network-type / interface-state
                for k in ("network-type", "interface-state"):
                    if k in state:
                        entry[k] = _strip_ospfv3_value(state[k])

                # OSPFv3-specific fields use the arcos-ospfv3: prefix
                v3_iid = state.get("arcos-ospfv3:interface-id")
                v3_instid = state.get("arcos-ospfv3:instance-id")
                if v3_iid is not None:
                    entry["interface-id"] = v3_iid
                if v3_instid is not None:
                    entry["instance-id"] = v3_instid

                if entry:
                    interfaces_dict[intf_id] = entry

            if interfaces_dict:
                result["areas"][str(area_id)] = {"interfaces": interfaces_dict}

        if not result["areas"]:
            raise SchemaEmptyParserError("No OSPFv3 interfaces parsed")

        return result


# =====================================================================
# ShowOspfv3SpfThrottle
# =====================================================================

class ShowOspfv3SpfThrottleSchema(MetaParser):
    """Schema for OSPFv3 SPF throttle timer state (RFC 8405)."""

    schema = {
        Optional("spf-initial-delay"): int,
        Optional("spf-short-delay"): int,
        Optional("spf-long-delay"): int,
        Optional("time-to-learn-interval"): int,
        Optional("holddown-interval"): int,
    }


class ShowOspfv3SpfThrottle(ShowOspfv3SpfThrottleSchema):
    """Parser for OSPFv3 SPF throttle timers.

    Command::

        show network-instance {ni} protocol OSPF3 {instance}
            global spf throttle
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} "
        "global spf throttle"
    )

    def cli(self, ni: str = "default", instance: str = "default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"global spf throttle | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        state = (
            ospfv3.get("global", {})
            .get("spf", {})
            .get("throttle", {})
            .get("timers", {})
            .get("state", {})
        )

        if not state:
            raise SchemaEmptyParserError("No OSPFv3 SPF throttle state found")

        result: Dict[str, TypeAny] = {}
        for k in ("spf-initial-delay", "spf-short-delay", "spf-long-delay",
                  "time-to-learn-interval", "holddown-interval"):
            if k in state:
                result[k] = state[k]

        return result


# =====================================================================
# ShowOspfv3Lsdb
# =====================================================================

class ShowOspfv3LsdbSchema(MetaParser):
    """Schema for OSPFv3 LSDB (per-area)."""

    schema = {
        "areas": {
            Any(): {  # area ID as str
                "lsa-types": {
                    Any(): {  # LSA type name
                        Optional("lsa-type"): str,
                        "lsas": {
                            Any(): {  # "link-state-id:adv-router" key
                                Optional("link-state-id"): str,
                                Optional("advertising-router"): str,
                                Optional("ls-sequence-number"): str,
                                Optional("ls-age"): int,
                                Optional("ls-checksum"): str,
                            }
                        },
                    }
                }
            }
        }
    }


class ShowOspfv3Lsdb(ShowOspfv3LsdbSchema):
    """Parser for OSPFv3 area LSDB.

    Command::

        show network-instance {ni} protocol OSPF3 {instance}
            area {area} lsdb
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} "
        "area {area} lsdb"
    )

    def cli(self, ni: str = "default", instance: str = "default",
            area: str = "*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"area {area} lsdb | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        areas_container = ospfv3.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPFv3 LSDB data found")

        result: Dict[str, TypeAny] = {"areas": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            # LSDB lives under the arcos-ospfv3:lsdb namespace key
            lsdb = (
                area_entry.get("arcos-ospfv3:lsdb")
                or area_entry.get("lsdb")
                or {}
            )
            if not lsdb:
                continue

            lsa_types_container = lsdb.get("lsa-types", {})
            lsa_type_list = lsa_types_container.get("lsa-type", [])

            lsa_types_dict: Dict[str, TypeAny] = {}

            for lt in lsa_type_list:
                raw_type = lt.get("type", "")
                lsa_type_name = _strip_ospfv3_value(raw_type)
                if not lsa_type_name:
                    continue

                lsas_container = lt.get("lsas", {})
                lsa_list = lsas_container.get("lsa", [])

                lsas_dict: Dict[str, TypeAny] = {}
                for lsa in lsa_list:
                    lsi = lsa.get("link-state-id", "")
                    adv = lsa.get("advertising-router", "")
                    if not lsi or not adv:
                        continue

                    key = f"{lsi}:{adv}"
                    lsa_state = lsa.get("state", {})
                    lsa_entry: Dict[str, TypeAny] = {
                        "link-state-id": lsi,
                        "advertising-router": adv,
                    }
                    for k in ("ls-sequence-number", "ls-age", "ls-checksum"):
                        if k in lsa_state:
                            lsa_entry[k] = lsa_state[k]
                    lsas_dict[key] = lsa_entry

                if lsas_dict:
                    lsa_types_dict[lsa_type_name] = {
                        "lsa-type": lsa_type_name,
                        "lsas": lsas_dict,
                    }

            if lsa_types_dict:
                result["areas"][str(area_id)] = {"lsa-types": lsa_types_dict}

        if not result["areas"]:
            raise SchemaEmptyParserError("No OSPFv3 LSDB entries parsed")

        return result


# =====================================================================
# ShowOspfv3GlobalRib
# =====================================================================

# OSPFv3 path-type values mirror v2 (same arcos-ospf-types: enum).
_OSPFV3_PATH_TYPE_MAP = {
    "OSPF_INTRA_AREA_CONNECTED_ROUTE": "intra-area-connected",
    "OSPF_INTRA_AREA_ROUTE": "intra-area",
    "OSPF_INTER_AREA_ROUTE": "inter-area",
    "OSPF_EXTERNAL_TYPE1_REDIST_ROUTE": "external-type-1",
    "OSPF_EXTERNAL_TYPE2_REDIST_ROUTE": "external-type-2",
    "OSPF_EXTERNAL_TYPE1_ROUTE": "external-type-1",
    "OSPF_EXTERNAL_TYPE2_ROUTE": "external-type-2",
}


class ShowOspfv3GlobalRibSchema(MetaParser):
    """Schema for OSPFv3 Global RIB prefix output (IPv6)."""

    schema = {
        "routes": {
            Any(): {  # IPv6 prefix string, e.g. "2001::4/128"
                "prefix": str,
                Optional("path-count"): int,
                Optional("route-flags"): list,
                Optional("path-type"): str,
                Optional("raw-path-type"): str,
                Optional("area"): str,
                Optional("metric"): int,
                Optional("path-flags"): list,
                Optional("received-lsa"): {
                    Optional("lsa-type"): str,
                    Optional("link-state-id"): str,
                    Optional("advertising-router"): str,
                },
                Optional("self-originated-lsa"): {
                    Optional("lsa-type"): str,
                    Optional("link-state-id"): str,
                    Optional("advertising-router"): str,
                },
                Optional("nexthop-set"): {
                    Optional("nexthop-set-id"): int,
                    Optional("nexthop-count"): int,
                    Optional("reference-count"): int,
                },
                # next-hops: list of {interface, address}; declared as
                # plain ``list`` (schemaengine doesn't support per-element
                # dict schemas inside lists).
                Optional("next-hops"): list,
            }
        }
    }


class ShowOspfv3GlobalRib(ShowOspfv3GlobalRibSchema):
    """Parser for OSPFv3 Global RIB prefix output (IPv6).

    Command::

        show network-instance {ni} protocol OSPF3 {instance} global rib prefix
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF3 {instance} "
        "global rib prefix"
    )

    def cli(self, ni: str = "default", instance: str = "default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF3 {instance} "
                f"global rib prefix | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ospfv3 = _navigate_to_ospfv3(parsed)

        rib = ospfv3.get("global", {}).get("rib", {})
        prefixes_container = rib.get("prefixes", {})
        prefix_list = prefixes_container.get("prefix", [])

        if not prefix_list:
            raise SchemaEmptyParserError("No OSPFv3 RIB prefixes found")

        routes: Dict[str, Dict[str, TypeAny]] = {}

        for entry in prefix_list:
            key = entry.get("prefix-key") or \
                entry.get("prefix-identifier", {}).get("prefix-key")
            if not key:
                continue

            route: Dict[str, TypeAny] = {"prefix": key}

            state = entry.get("state", {}) or {}
            if "path-count" in state:
                route["path-count"] = state["path-count"]
            if "route-flags" in state:
                route["route-flags"] = [
                    _strip_ospfv3_value(rf) for rf in state["route-flags"]
                ]

            bestpath = entry.get("bestpath", {}) or {}

            raw_pt = bestpath.get("path-type")
            if raw_pt:
                stripped = _strip_ospfv3_value(raw_pt)
                route["raw-path-type"] = stripped
                route["path-type"] = _OSPFV3_PATH_TYPE_MAP.get(
                    stripped, stripped.lower()
                )

            if "area-id" in bestpath:
                route["area"] = str(bestpath["area-id"])
            if "metric" in bestpath:
                route["metric"] = bestpath["metric"]
            if "path-flags" in bestpath:
                route["path-flags"] = [
                    _strip_ospfv3_value(pf) for pf in bestpath["path-flags"]
                ]

            for lsa_key in ("received-lsa", "self-originated-lsa"):
                lsa = bestpath.get(lsa_key)
                if lsa:
                    lsa_entry: Dict[str, TypeAny] = {}
                    if "lsa-type" in lsa:
                        lsa_entry["lsa-type"] = _strip_ospfv3_value(
                            lsa["lsa-type"]
                        )
                    if "link-state-id" in lsa:
                        lsa_entry["link-state-id"] = lsa["link-state-id"]
                    if "advertising-router" in lsa:
                        lsa_entry["advertising-router"] = (
                            lsa["advertising-router"]
                        )
                    if lsa_entry:
                        route[lsa_key] = lsa_entry

            nh_set = bestpath.get("nexthop-set", {}) or {}
            nh_state = nh_set.get("state", {}) or {}
            nh_set_entry: Dict[str, TypeAny] = {}
            for k in ("nexthop-set-id", "nexthop-count", "reference-count"):
                if k in nh_state:
                    nh_set_entry[k] = nh_state[k]
            if nh_set_entry:
                route["nexthop-set"] = nh_set_entry

            nh_container = nh_set.get("nexthops", {}) or {}
            nh_list = nh_container.get("nexthop", []) or []
            next_hops = []
            for nh in nh_list:
                nh_state2 = nh.get("state", {}) or {}
                interface = (
                    nh_state2.get("outgoing-interface")
                    or nh.get("outgoing-interface")
                )
                address = (
                    nh_state2.get("nexthop-address")
                    or nh.get("nexthop-address")
                )
                nh_entry: Dict[str, TypeAny] = {}
                if interface:
                    nh_entry["interface"] = interface
                if address:
                    nh_entry["address"] = address
                if nh_entry:
                    next_hops.append(nh_entry)
            if next_hops:
                route["next-hops"] = next_hops

            routes[key] = route

        if not routes:
            raise SchemaEmptyParserError("No OSPFv3 RIB prefix entries parsed")

        return {"routes": routes}
